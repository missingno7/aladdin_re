"""Bounded, versioned archives; user recordings are written exclusively once."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

from .profile import FRAME_TICKS, PROFILE_SHA256
from . import __version__ as PROJECT_VERSION

LIMIT = 16 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def decode_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON value")))


def uint(value, bits=64):
    if type(value) is not int or not 0 <= value < 2**bits:
        raise ValueError(f"Expected uint{bits}")
    return value


def pack(parts):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return stream.getvalue()


def unpack(data, allowed, required):
    if len(data) > LIMIT:
        raise ValueError("Archive exceeds size limit")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [entry.filename for entry in infos]
            if len(names) != len(set(names)) or not set(names) <= allowed or not required <= set(names):
                raise ValueError("Unexpected, duplicate or missing archive member")
            if sum(entry.file_size for entry in infos) > LIMIT:
                raise ValueError("Archive expands beyond size limit")
            if any(entry.flag_bits & 1 for entry in infos):
                raise ValueError("Encrypted archives are unsupported")
            return {name: archive.read(name) for name in names}
    except zipfile.BadZipFile as e:
        raise ValueError("Corrupt archive") from e


def write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves existing recordings, including on name collision.
    with path.open("xb") as out:
        out.write(data)


def read_bounded(path):
    with Path(path).open("rb") as source:
        data = source.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("Artifact exceeds size limit")
    return data


def snapshot_bytes(machine):
    if getattr(machine, "in_sound_call", False):
        raise ValueError("Recovery snapshot unavailable during the synchronous sound call")
    state = machine.snapshot()
    manifest = {
        "format": "alsnap", "version": 2, "rom_sha256": machine.rom_sha256,
        "profile_sha256": PROFILE_SHA256, "source_id": machine.source_id,
        "machine_state_version": machine.state_version, "project_version": PROJECT_VERSION,
        "boundary": "completed-native-operation", "tick": machine.info["tick"],
        "sections": {"machine.bin": {"size": len(state), "sha256": digest(state)}},
    }
    return pack({"manifest.json": json_bytes(manifest), "machine.bin": state})


def load_snapshot(data, *, rom_sha256, state_version):
    parts = unpack(data, {"manifest.json", "machine.bin"}, {"manifest.json", "machine.bin"})
    meta = decode_json(parts["manifest.json"])
    if meta.get("format") != "alsnap" or type(meta.get("version")) is not int or meta["version"] != 2:
        raise ValueError("Unsupported snapshot format; current version is 2, regenerate the snapshot")
    if (meta.get("rom_sha256"), meta.get("profile_sha256")) != (rom_sha256, PROFILE_SHA256):
        raise ValueError("Snapshot ROM/profile identity mismatch")
    if meta.get("machine_state_version") != state_version or type(meta.get("machine_state_version")) is not int:
        raise ValueError("Unsupported machine state contract; regenerate artifacts")
    if not isinstance(meta.get("source_id"), str) or len(meta["source_id"]) != 64:
        raise ValueError("Invalid source provenance")
    if meta.get("boundary") != "completed-native-operation":
        raise ValueError("Unsupported snapshot boundary")
    uint(meta["tick"])
    state = parts["machine.bin"]
    if meta.get("sections") != {"machine.bin": {"size": len(state), "sha256": digest(state)}}:
        raise ValueError("Snapshot section integrity mismatch")
    return meta, state


def restore_snapshot(machine, data):
    meta, state = load_snapshot(data, rom_sha256=machine.rom_sha256, state_version=machine.state_version)
    if machine.snapshot_tick(state) != meta["tick"]:
        raise ValueError("Snapshot timestamp disagrees with native state")
    machine.restore(state)


class Recorder:
    def __init__(self, machine, *, origin="user", reset_provenance="unknown"):
        if origin not in {"user", "synthetic"}:
            raise ValueError("Invalid recording origin")
        self.initial = snapshot_bytes(machine)
        self.start = machine.info["tick"]
        self.source_id, self.rom_sha256 = machine.source_id, machine.rom_sha256
        self.state_version = machine.state_version
        self.origin, self.reset_provenance = origin, reset_provenance
        self.events, self.bookmarks = [], []

    def apply_pad(self, machine, buttons):
        before = machine.info
        if buttons == before["buttons"]:
            return
        machine.pad(buttons)
        self.events.append({"tick": before["tick"], "seq": len(self.events), "kind": "pad_state", "port": 0, "buttons": buttons})

    def finish(self, machine, *, terminal_status="completed", failure=None, terminal_tick=None):
        terminal = machine.info["tick"] if terminal_tick is None else uint(terminal_tick)
        if terminal < self.start:
            raise ValueError("Recording time moved backwards")
        if terminal_status not in {"completed", "failed"}:
            raise ValueError("Invalid terminal status")
        if terminal_status == "failed" and not isinstance(failure, dict):
            raise ValueError("Failed capture must describe its failure")
        if any(event["tick"] > terminal for event in self.events):
            raise ValueError("Events extend past the valid recording prefix")
        events = b"".join(json_bytes(e) + b"\n" for e in self.events)
        meta = {"format": "alreplay", "version": 2, "rom_sha256": self.rom_sha256,
                "profile_sha256": PROFILE_SHA256, "source_id": self.source_id,
                "machine_state_version": self.state_version, "project_version": PROJECT_VERSION,
                "mode": "original", "origin": self.origin, "reset_provenance": self.reset_provenance,
                "initial_sha256": digest(self.initial), "events_sha256": digest(events), "terminal_tick": terminal,
                "terminal_status": terminal_status}
        if failure is not None:
            meta["failure"] = failure
        return pack({"manifest.json": json_bytes(meta), "initial.alsnap": self.initial,
                     "events.jsonl": events, "bookmarks.json": json_bytes(self.bookmarks)})


def load_replay(data, *, rom_sha256, state_version):
    parts = unpack(data, {"manifest.json", "initial.alsnap", "events.jsonl", "bookmarks.json"}, {"manifest.json", "initial.alsnap", "events.jsonl"})
    meta = decode_json(parts["manifest.json"])
    if meta.get("format") != "alreplay" or type(meta.get("version")) is not int or meta["version"] != 2:
        raise ValueError("Unsupported replay format; current version is 2, record or regenerate the replay")
    if (meta.get("rom_sha256"), meta.get("profile_sha256")) != (rom_sha256, PROFILE_SHA256):
        raise ValueError("Replay ROM/profile identity mismatch")
    if meta.get("machine_state_version") != state_version or type(meta.get("machine_state_version")) is not int:
        raise ValueError("Unsupported machine state contract; regenerate artifacts")
    if not isinstance(meta.get("source_id"), str) or len(meta["source_id"]) != 64:
        raise ValueError("Invalid source provenance")
    if meta.get("mode") != "original" or meta.get("origin") not in {"user", "synthetic"}:
        raise ValueError("Unsupported replay mode/origin")
    if digest(parts["initial.alsnap"]) != meta.get("initial_sha256") or digest(parts["events.jsonl"]) != meta.get("events_sha256"):
        raise ValueError("Replay section integrity mismatch")
    initial_meta, _ = load_snapshot(parts["initial.alsnap"], rom_sha256=rom_sha256, state_version=state_version)
    if initial_meta["source_id"] != meta["source_id"]:
        raise ValueError("Replay and initial snapshot capture identities disagree")
    if meta.get("terminal_status", "completed") not in {"completed", "failed"}:
        raise ValueError("Invalid capture terminal status")
    if meta.get("terminal_status") == "failed" and not isinstance(meta.get("failure"), dict):
        raise ValueError("Failed capture must describe its failure")
    start, terminal = initial_meta["tick"], uint(meta["terminal_tick"])
    if terminal < start:
        raise ValueError("Replay terminal precedes initial state")
    events = []
    previous = start
    for line in parts["events.jsonl"].splitlines():
        event = decode_json(line)
        if set(event) != {"tick", "seq", "kind", "port", "buttons"} or event["kind"] != "pad_state":
            raise ValueError("Unsupported input event")
        tick = uint(event["tick"])
        uint(event["buttons"], 8)
        if uint(event["seq"]) != len(events) or type(event["port"]) is not int or event["port"] != 0 or not previous <= tick <= terminal:
            raise ValueError("Invalid event order, port or interval")
        events.append(event)
        previous = tick
    return meta, parts["initial.alsnap"], events


def play_events(machine, events, terminal, *, audio_sink=None, on_gate=None, on_checkpoint=None):
    checkpoint_period = FRAME_TICKS * 60
    next_checkpoint = (machine.info["tick"] // checkpoint_period + 1) * checkpoint_period
    def advance(target):
        nonlocal next_checkpoint
        parked = 0
        while machine.info["tick"] < target:
            current = machine.info["tick"]
            deadline = min(target, (current // FRAME_TICKS + 1) * FRAME_TICKS)
            reason = machine.run(target=deadline)
            info = machine.info
            diagnostic = {"pc": info.get("pc"), "tick": info["tick"], "target": deadline,
                          "stop_reason": reason, "candidate": getattr(machine, "candidate_identity", "original")}
            if reason == "gate":
                if on_gate is None:
                    raise RuntimeError("Unexpected replay gate: " + json.dumps(diagnostic))
                before = (info["tick"], info.get("pc"))
                # The frame limit only batches PCM drains. A carrier may own
                # that interval, but must stop for input, observation or terminal.
                on_gate(machine, min(target, next_checkpoint))
                after = machine.info
                parked = parked + 1 if after["tick"] <= current else 0
                if (after["tick"], after.get("pc")) == before or parked > 8:
                    raise RuntimeError("Candidate made no progress: " + json.dumps(diagnostic))
            elif reason != "limit" or info["tick"] <= current:
                raise RuntimeError("Replay made no progress: " + json.dumps(diagnostic))
            else:
                parked = 0
            pcm = machine.audio()
            if audio_sink:
                audio_sink(pcm)
            if machine.info["tick"] >= next_checkpoint:
                if on_checkpoint:
                    on_checkpoint(machine, next_checkpoint // checkpoint_period, next_checkpoint)
                next_checkpoint += checkpoint_period

    for event in events:
        tick = event["tick"]
        if machine.info["tick"] < tick:
            advance(tick)
        if machine.info["tick"] != tick:
            raise ValueError("Recorded input tick is not reachable at this instruction boundary")
        machine.pad(event["buttons"])
    if machine.info["tick"] < terminal:
        advance(terminal)
    if machine.info["tick"] != terminal:
        raise ValueError("Replay terminal tick is not reachable")
