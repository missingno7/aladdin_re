"""Typed C ABI. One native machine owns all memory; calls are single-threaded."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys

from .profile import NTSC

U8, U32, U64 = C.c_uint8, C.c_uint32, C.c_uint64
P8, P32, P64 = C.POINTER(U8), C.POINTER(U32), C.POINTER(U64)


class NativeError(RuntimeError):
    pass


def library_path():
    override = os.environ.get("GENESIS_NATIVE_LIBRARY")
    if override:
        return Path(override).resolve()
    name = "libgenesis_native.dll" if sys.platform == "win32" else "libgenesis_native.so"
    path = Path(__file__).parent / name
    if not path.is_file():
        built = Path(__file__).resolve().parents[2] / "build" / name    # a source checkout's own build
        if built.is_file():
            return built
        raise NativeError("Native library missing. Build/install the package as described in README.md, or set GENESIS_NATIVE_LIBRARY to the built library.")
    return path


def load_library():
    lib = C.CDLL(str(library_path()))
    signatures = {
        "abi": (U32, []), "state_version": (U32, []), "error": (C.c_char_p, []), "source_id": (C.c_char_p, []),
        "build_info": (C.c_char_p, []),
        "create": (C.c_int, [P8, U64, C.c_char_p, C.c_char_p, C.POINTER(C.c_void_p)]),
        "destroy": (C.c_int, [C.c_void_p]),
        "run": (C.c_int, [C.c_void_p, U64, U64, P32]),
        "gate": (C.c_int, [C.c_void_p, U32, U32]),
        "info": (C.c_int, [C.c_void_p, P64, U64]),
        "pad": (C.c_int, [C.c_void_p, U32]),
        "ram": (C.c_int, [C.c_void_p, C.POINTER(P8), P64]),
        "export": (C.c_int, [C.c_void_p, P8, U64, P64]),
        "import": (C.c_int, [C.c_void_p, P8, U64]),
        "frame": (C.c_int, [C.c_void_p, P8, U64, P32, P32]),
        "audio": (C.c_int, [C.c_void_p, C.POINTER(C.c_int16), U64, P64]),
        "audio_policy": (C.c_int, [C.c_void_p, U32]),
        "snapshot_tick": (C.c_int, [C.c_void_p, P8, U64, P64]),
        "gates": (C.c_int, [C.c_void_p, P32, U64]),
        "registers": (C.c_int, [C.c_void_p, P32, U64]),
        "atomic": (C.c_int, [C.c_void_p, U64, U64, U64, U32, P32, P8, U64, P32, P32, U64, P32]),
    }
    for name, (result, args) in signatures.items():
        try:
            f = getattr(lib, "al_" + name)
        except AttributeError as error:
            raise NativeError("Native library predates the required review API; rebuild/install the current adapter then regenerate artifacts if their contract changed.") from error
        f.restype, f.argtypes = result, args
    if lib.al_abi() != 2:
        raise NativeError("Unsupported native ABI")
    return lib


class Machine:
    """One Genesis with one cartridge.

    The snapshot identity the adapter embeds is the ROM's hash plus a profile
    id and hash: the registered game's when the cartridge is a supported
    revision (``genesis_re.games``), otherwise the board's.  A state from
    another cartridge or profile is refused natively.  ``profile`` may be
    given explicitly; it must then be the game these bytes are.
    """
    def __init__(self, rom: bytes, profile=None):
        self._rom = bytes(rom)  # Immutable cartridge diagnostics; no mutable shadow state.
        if profile is None:
            from .games import registered
            profile = registered(rom)
        elif hashlib.sha256(rom).hexdigest() != profile.rom_sha256:
            raise ValueError(f"These bytes are not the {profile.title} cartridge")
        self.profile = profile
        self.board = NTSC if profile is None else profile.board
        identity = (self.board.id, self.board.sha256) if profile is None else (profile.profile_id, profile.profile_sha256)
        self.candidate_identity = "original"
        self.in_sound_call = False
        self.calls = {}  # Diagnostic API counts, not emulated or persisted state.
        self._snapshot_buffer = None
        self.lib = load_library()
        self.handle = C.c_void_p()
        self.rom_sha256 = hashlib.sha256(rom).hexdigest()
        data = (U8 * len(rom)).from_buffer_copy(rom)
        self._check(self.lib.al_create(data, len(data), identity[0].encode(), identity[1].encode(), C.byref(self.handle)))
        self._ram_pointer, size = P8(), U64()
        self._call("ram", C.byref(self._ram_pointer), C.byref(size))
        self._ram = (U8 * size.value).from_address(C.addressof(self._ram_pointer.contents))

    def _check(self, code):
        if code:
            raise NativeError(self.lib.al_error().decode("utf-8", errors="replace"))

    def _call(self, name, *args):
        if not self.handle:
            raise NativeError("Machine is closed")
        self.calls[name] = self.calls.get(name, 0) + 1
        self._check(getattr(self.lib, "al_" + name)(self.handle, *args))

    def close(self):
        if self.handle:
            self._call("destroy")
            self.handle = C.c_void_p()
            self._ram = None
            self._snapshot_buffer = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @property
    def source_id(self):
        return self.lib.al_source_id().decode()

    @property
    def state_version(self):
        return self.lib.al_state_version()

    @property
    def info(self):
        values = (U64 * 8)()
        self._call("info", values, len(values))
        return dict(zip(("tick", "m68k_instructions", "m68k_cycles", "z80_instructions", "pc", "sr", "buttons", "vblanks"), values))

    def run(self, *, target=0, instructions=0):
        if type(target) is not int or type(instructions) is not int or not 0 <= target < 2**64 or not 0 <= instructions < 2**64:
            raise ValueError("Run limits must be nonnegative uint64 values")
        reason = U32()
        self._call("run", target, instructions, C.byref(reason))
        return "gate" if reason.value else "limit"

    def gate(self, pc=None, *, bypass_once=False):
        if pc is not None and (type(pc) is not int or not 0 <= pc <= 0xffffff):
            raise ValueError("Gate address out of range")
        self._call("gate", 0xffffffff if pc is None else pc, int(bypass_once))

    def pad(self, buttons):
        if type(buttons) is not int or not 0 <= buttons <= 255:
            raise ValueError("Invalid pad mask")
        self._call("pad", buttons)

    def gates(self, pcs):
        if any(type(pc) is not int or not 0 <= pc <= 0xffffff for pc in pcs):
            raise ValueError("Gate address out of range")
        values = (U32 * len(pcs))(*pcs)
        self._call("gates", values, len(values))

    def registers(self):
        values = (U32 * 18)()
        self._call("registers", values, len(values))
        return dict(zip([f"d{i}" for i in range(8)] + [f"a{i}" for i in range(8)] + ["pc", "sr"], values))

    def atomic(self, *, target, cycles, instructions, last_pc, writes, registers):
        names = [f"d{i}" for i in range(8)] + [f"a{i}" for i in range(8)] + ["pc", "sr"]
        for value in (target, cycles, instructions):
            if type(value) is not int or not 0 <= value < 2**64:
                raise ValueError("Invalid atomic limit")
        if type(last_pc) is not int or not 0 <= last_pc <= 0xffffff:
            raise ValueError("Invalid last PC")
        if any(type(a) is not int or type(b) is not int or not 0xff0000 <= a <= 0xffffff or not 0 <= b < 256 for a, b in writes):
            raise ValueError("Atomic writes require work RAM bytes")
        if any(k not in names or type(v) is not int or not 0 <= v < 2**32 for k, v in registers.items()):
            raise ValueError("Invalid register effects")
        addresses = (U32 * len(writes))(*(a for a, _ in writes))
        data = (U8 * len(writes))(*(b for _, b in writes))
        fields = (U32 * len(registers))(*(names.index(k) for k in registers))
        values = (U32 * len(registers))(*registers.values())
        accepted = U32()
        self._call("atomic", target, cycles, instructions, last_pc, addresses, data, len(writes),
                   fields, values, len(fields), C.byref(accepted))
        return bool(accepted.value)

    def peek_ram(self, offset, size=1):
        if not self.handle:
            raise NativeError("Machine is closed")
        if offset < 0 or size < 0 or offset + size > 65536:
            raise ValueError("RAM range out of bounds")
        return bytes(self._ram[offset:offset+size])

    def peek_rom(self, offset, size=1):
        if not self.handle:
            raise NativeError("Machine is closed")
        if type(offset) is not int or type(size) is not int or offset < 0 or size < 0 or offset + size > len(self._rom):
            raise ValueError("ROM range out of bounds")
        return self._rom[offset:offset + size]

    @property
    def ram_address(self):
        if not self.handle:
            raise NativeError("Machine is closed")
        return C.addressof(self._ram)

    def snapshot(self):
        # Native import bounds this state contract at 4 MiB. A reusable output
        # buffer avoids a sizing export, which itself serializes and hashes the
        # entire machine. This is scratch storage; callers receive owned bytes.
        if self._snapshot_buffer is None:
            self._snapshot_buffer = (U8 * (4 * 1024 * 1024))()
        size = U64()
        buf = self._snapshot_buffer
        self._call("export", buf, len(buf), C.byref(size))
        return C.string_at(buf, size.value)

    def restore(self, data):
        buf = (U8 * len(data)).from_buffer_copy(data)
        self._call("import", buf, len(buf))

    def snapshot_tick(self, data):
        buf = (U8 * len(data)).from_buffer_copy(data)
        tick = U64()
        self._call("snapshot_tick", buf, len(buf), C.byref(tick))
        return tick.value

    def audio_policy(self, policy):
        if policy not in {"capture", "discard"}:
            raise ValueError("Unknown audio policy")
        self._call("audio_policy", int(policy == "discard"))

    def frame(self):
        buf = (U8 * (320 * 240 * 3))()
        width, height = U32(), U32()
        self._call("frame", buf, len(buf), C.byref(width), C.byref(height))
        return width.value, height.value, C.string_at(buf, width.value * height.value * 3)

    def audio(self):
        count = U64()
        self._call("audio", None, 0, C.byref(count))
        buf = (C.c_int16 * count.value)()
        self._call("audio", buf, len(buf), C.byref(count))
        return bytes(buf)  # supported Windows/Linux x64: little-endian PCM
