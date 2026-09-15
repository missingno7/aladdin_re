"""Concrete Genesis execution/cache adapter for canonical frame histories."""
from __future__ import annotations

from pathlib import Path

from . import artifacts
from .history import digest, encoded, natural
from .machine import Machine
from .receipt import execution_receipt


EMPTY_PCM = digest(b"")


def safe_state(machine):
    """Capture raw implementation state only at a recovery-safe boundary."""
    if getattr(machine, "in_sound_call", False):
        raise ValueError("Checkpoint unavailable inside synchronous sound call")
    return machine.snapshot()


class GenesisRun:
    """One game's cartridge stepping in canonical frames, original or with a candidate armed."""
    def __init__(self, game, rom, candidate="original"):
        self.game = game
        self.frame_ticks = game.board.frame_ticks
        self.observation_offset_ticks = game.observation_offset_ticks
        self.machine = Machine(rom)
        if self.machine.profile is not None and self.machine.profile is not game:
            raise ValueError(f"These bytes are the {self.machine.profile.title} cartridge, not {game.title}")
        self.frame, self.buttons = 0, 0
        self.pcm_digest, self.pcm_bytes = EMPTY_PCM, 0
        self.candidate = None
        if candidate != "original":
            if game.candidate is None:
                raise ValueError(f"{game.title} has no recovered code; only the original runs")
            self.candidate = game.candidate(candidate)
            self.candidate.arm(self.machine)
        receipt = execution_receipt(game, candidate=candidate)
        self.implementation = {"backend": "genesis", "cache_contract": 3, "game": game.id,
                               "native": receipt["native_binary_sha256"],
                               "source": receipt["python_modules_sha256"],
                               "state_version": self.machine.state_version,
                               "rom": self.machine.rom_sha256, "profile": game.profile_sha256,
                               "candidate": candidate}
        # The original's trajectory is fixed by the ROM, the native binary, the
        # profile and the state contract; recovered Python source never runs in
        # it, so an edit below src must not discard its caches.  A candidate's
        # cache stays bound to the exact source that produced it.
        self.cache_implementation = {key: value for key, value in self.implementation.items()
                                     if not (candidate == "original" and key == "source")}
        self.implementation_id = digest(encoded(self.cache_implementation))

    def close(self):
        self.machine.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _run_to(self, target, deadline):
        """Run to ``target``; recovered operations may run on until ``deadline``."""
        parked = 0
        while self.machine.info["tick"] < target:
            before = self.machine.info
            reason = self.machine.run(target=target)
            if reason == "gate":
                if self.candidate is None:
                    raise RuntimeError("Unexpected original execution gate")
                self.candidate.on_gate(self.machine, deadline)
            elif reason != "limit":
                raise RuntimeError("Unexpected Genesis stop")
            after = self.machine.info
            if (after["tick"], after["pc"]) == (before["tick"], before["pc"]):
                raise RuntimeError("History execution made no progress")
            parked = parked + 1 if after["tick"] <= before["tick"] else 0
            if parked > 8:
                raise RuntimeError("History execution remained parked")

    def step(self, buttons):
        if type(buttons) is not int or not 0 <= buttons <= 255:
            raise ValueError("Invalid input mask")
        wrap = self.frame * self.frame_ticks
        observed = wrap + self.observation_offset_ticks
        # The controller mask for interval [frame, frame + 1) is set at the
        # first operation boundary at or after the interval's nominal tick, as
        # it always was.  The interval is observed, and recovered operations
        # are deadlined, at the idle instant half a frame later, where the game
        # waits for the next VBlank.  An operation admitted before the wrap may
        # therefore end after it; recovered regions contain no controller read,
        # so the game cannot observe whether the mask changed one instruction
        # or one operation after the wrap.  This keeps recorded inputs exact
        # and stops refusing recovered work that merely straddles the wrap.
        self._run_to(wrap, observed)
        if buttons != self.buttons:
            self.machine.pad(buttons)
            self.buttons = buttons
        self._run_to(observed, observed)
        # The adapter finishes the native operation crossing the observation
        # instant.  That physical tick is a receipt fact, never an input-history
        # timestamp.
        pcm = self.machine.audio()
        self.pcm_digest = digest(bytes.fromhex(self.pcm_digest) + pcm)
        self.pcm_bytes += len(pcm)
        self.frame += 1
        return pcm

    def advance(self, end_frame, events, observe=None):
        natural(end_frame)
        if end_frame < self.frame:
            raise ValueError("Cannot run history backwards")
        changes = {event["frame"]: event["buttons"] for event in events}
        while self.frame < end_frame:
            self.step(changes.get(self.frame, self.buttons))
            if observe is not None:
                observe(self)

    def observable(self):
        # No video frame exists at power-on before the VDP is configured.
        video = digest(self.machine.frame()[2]) if self.frame else None
        return {"frame": self.frame, "buttons": self.buttons,
                "state_sha256": digest(self.machine.snapshot()),
                "frame_sha256": video,
                "pcm_sha256": self.pcm_digest, "pcm_bytes": self.pcm_bytes,
                **self.machine.info}

    def save(self):
        return (safe_state(self.machine), self.frame, self.buttons, self.pcm_digest, self.pcm_bytes)

    def restore(self, saved):
        state, frame, buttons, pcm_digest, pcm_bytes = saved
        # Native import validates before mutation. Keep the logical clock at
        # its previous position too if an incompatible state is rejected.
        self.machine.restore(state)
        self.frame, self.buttons = frame, buttons
        self.pcm_digest, self.pcm_bytes = pcm_digest, pcm_bytes
        if self.candidate:
            self.candidate.arm(self.machine)

    def _cache_path(self, store, node_id):
        return store.path / "caches" / "genesis" / self.implementation_id / (node_id + ".cache")

    def cache(self, store, node_id):
        node = store.node(node_id)
        if (node["end_frame"], node["buttons"]) != (self.frame, self.buttons):
            raise ValueError("Cache position differs from history node")
        state = self.save()[0]
        meta = {"node": node_id, "implementation": self.cache_implementation,
                "frame": self.frame, "buttons": self.buttons,
                "pcm_sha256": self.pcm_digest, "pcm_bytes": self.pcm_bytes,
                "state_sha256": digest(state)}
        meta["checksum"] = digest(encoded(meta))
        path = self._cache_path(store, node_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(artifacts.pack({"cache.json": encoded(meta), "state.bin": state}))
        temporary.replace(path)

    def restore_cache(self, store, node_id):
        path = self._cache_path(store, node_id)
        if not path.exists():
            return False
        try:
            parts = artifacts.unpack(artifacts.read_bounded(path), {"cache.json", "state.bin"}, {"cache.json", "state.bin"})
            meta = artifacts.decode_json(parts["cache.json"])
            checksum = meta.pop("checksum", None)
            if checksum != digest(encoded(meta)):
                return False
            node = store.node(node_id)
            if (meta["implementation"] != self.cache_implementation or meta["node"] != node_id
                    or meta["state_sha256"] != digest(parts["state.bin"])
                    or (meta["frame"], meta["buttons"]) != (node["end_frame"], node["buttons"])):
                return False
            self.restore((parts["state.bin"], meta["frame"], meta["buttons"],
                          meta["pcm_sha256"], meta["pcm_bytes"]))
            return True
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            return False


class Session:
    """One live authority, with implicit input journaling and natural branching."""
    def __init__(self, game, store, rom, node=None):
        if store.root != game.history_root:
            raise ValueError(f"History store {store.path} is not a {game.title} original-machine history")
        self.store = store
        self.parent = store.resolve(node) if node else store.root_id
        self.run = GenesisRun(game, rom)
        self.machine = self.run.machine
        self.events = []
        self.used_cache = False
        try:
            if self.parent != store.root_id:
                self.used_cache = self.run.restore_cache(store, self.parent)
                if not self.used_cache:
                    path = store.flatten(self.parent)
                    self.run.advance(path["end_frame"], path["events"])
                    self.run.cache(store, self.parent)
        except BaseException:
            self.run.close()
            raise

    @property
    def frame(self):
        return self.run.frame

    def step(self, buttons):
        if buttons != self.run.buttons:
            self.events.append({"frame": self.frame, "buttons": buttons})
        return self.run.step(buttons)

    def checkpoint(self, reason="manual", label=None):
        node = self.store.append(self.parent, self.events, self.frame)
        width, height, rgb = self.machine.frame() if self.frame else (320, 224, bytes(320 * 224 * 3))
        self.store.present(node, rgb=rgb, width=width, height=height, reason=reason, label=label)
        self.run.cache(self.store, node)
        self.store.set_main(node)
        self.parent, self.events = node, []
        return node

    def __enter__(self):
        return self

    def __exit__(self, error_type, *_):
        try:
            if error_type is None:
                self.checkpoint(reason="session_exit")
        finally:
            self.run.close()
