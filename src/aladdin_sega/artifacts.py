"""Bounded, versioned archives; user recordings are written exclusively once."""
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

from .profile import FRAME_TICKS, PROFILE_SHA256

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
    state = machine.snapshot()
    manifest = {
        "format": "alsnap", "version": 1, "rom_sha256": machine.rom_sha256,
        "profile_sha256": PROFILE_SHA256, "source_id": machine.source_id,
        "boundary": "completed-native-operation", "tick": machine.info["tick"],
        "sections": {"machine.bin": {"size": len(state), "sha256": digest(state)}},
    }
    return pack({"manifest.json": json_bytes(manifest), "machine.bin": state})


def load_snapshot(data, *, rom_sha256, source_id):
    parts = unpack(data, {"manifest.json", "machine.bin"}, {"manifest.json", "machine.bin"})
    meta = decode_json(parts["manifest.json"])
    if meta.get("format") != "alsnap" or type(meta.get("version")) is not int or meta["version"] != 1:
        raise ValueError("Unsupported snapshot format")
    if (meta.get("rom_sha256"), meta.get("profile_sha256"), meta.get("source_id")) != (rom_sha256, PROFILE_SHA256, source_id):
        raise ValueError("Snapshot ROM/profile/source identity mismatch")
    if meta.get("boundary") != "completed-native-operation":
        raise ValueError("Unsupported snapshot boundary")
    uint(meta["tick"])
    state = parts["machine.bin"]
    if meta.get("sections") != {"machine.bin": {"size": len(state), "sha256": digest(state)}}:
        raise ValueError("Snapshot section integrity mismatch")
    return meta, state


def restore_snapshot(machine, data):
    meta, state = load_snapshot(data, rom_sha256=machine.rom_sha256, source_id=machine.source_id)
    # Timestamp is checked in native serialized fields before applying state.
    # Pinned pf-genesis-snapshot-v2 tail: master, CPU cycles, instructions,
    # VINT frame, VINT count (u64), standing PC (u32), then two ASCII hashes.
    tail = struct.Struct("<QQQQQI")
    if len(state) < 17 + tail.size + 128:
        raise ValueError("Truncated native snapshot")
    native_tick = tail.unpack_from(state, len(state) - 128 - tail.size)[0]
    if native_tick != meta["tick"]:
        raise ValueError("Snapshot timestamp disagrees with native state")
    machine.restore(state)


class Recorder:
    def __init__(self, machine, *, origin="user", reset_provenance="unknown"):
        if origin not in {"user", "synthetic"}:
            raise ValueError("Invalid recording origin")
        self.initial = snapshot_bytes(machine)
        self.start = machine.info["tick"]
        self.source_id, self.rom_sha256 = machine.source_id, machine.rom_sha256
        self.origin, self.reset_provenance = origin, reset_provenance
        self.events, self.bookmarks = [], []

    def apply_pad(self, machine, buttons):
        before = machine.info
        if buttons == before["buttons"]:
            return
        machine.pad(buttons)
        self.events.append({"tick": before["tick"], "seq": len(self.events), "kind": "pad_state", "port": 0, "buttons": buttons})

    def finish(self, machine):
        terminal = machine.info["tick"]
        if terminal < self.start:
            raise ValueError("Recording time moved backwards")
        events = b"".join(json_bytes(e) + b"\n" for e in self.events)
        meta = {"format": "alreplay", "version": 1, "rom_sha256": self.rom_sha256,
                "profile_sha256": PROFILE_SHA256, "source_id": self.source_id,
                "mode": "original", "origin": self.origin, "reset_provenance": self.reset_provenance,
                "initial_sha256": digest(self.initial), "events_sha256": digest(events), "terminal_tick": terminal}
        return pack({"manifest.json": json_bytes(meta), "initial.alsnap": self.initial,
                     "events.jsonl": events, "bookmarks.json": json_bytes(self.bookmarks)})


def load_replay(data, *, rom_sha256, source_id):
    parts = unpack(data, {"manifest.json", "initial.alsnap", "events.jsonl", "bookmarks.json"}, {"manifest.json", "initial.alsnap", "events.jsonl"})
    meta = decode_json(parts["manifest.json"])
    if meta.get("format") != "alreplay" or type(meta.get("version")) is not int or meta["version"] != 1:
        raise ValueError("Unsupported replay format")
    if (meta.get("rom_sha256"), meta.get("profile_sha256"), meta.get("source_id")) != (rom_sha256, PROFILE_SHA256, source_id):
        raise ValueError("Replay ROM/profile/source identity mismatch")
    if meta.get("mode") != "original" or meta.get("origin") not in {"user", "synthetic"}:
        raise ValueError("Unsupported replay mode/origin")
    if digest(parts["initial.alsnap"]) != meta.get("initial_sha256") or digest(parts["events.jsonl"]) != meta.get("events_sha256"):
        raise ValueError("Replay section integrity mismatch")
    initial_meta, _ = load_snapshot(parts["initial.alsnap"], rom_sha256=rom_sha256, source_id=source_id)
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


def play_events(machine, events, terminal, *, audio_sink=None):
    def advance(target):
        while machine.info["tick"] < target:
            current = machine.info["tick"]
            machine.run(target=min(target, (current // FRAME_TICKS + 1) * FRAME_TICKS))
            pcm = machine.audio()
            if audio_sink:
                audio_sink(pcm)

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
