"""Typed C ABI. One native machine owns all memory; calls are single-threaded."""
import ctypes as C
import hashlib
import os
from pathlib import Path
import sys

from .profile import PROFILE_SHA256

U8, U32, U64 = C.c_uint8, C.c_uint32, C.c_uint64
P8, P32, P64 = C.POINTER(U8), C.POINTER(U32), C.POINTER(U64)


class NativeError(RuntimeError):
    pass


def library_path():
    override = os.environ.get("ALADDIN_NATIVE_LIBRARY")
    if override:
        return Path(override).resolve()
    name = "libaladdin_native.dll" if sys.platform == "win32" else "libaladdin_native.so"
    path = Path(__file__).parent / name
    if not path.is_file():
        raise NativeError("Native library missing. Build/install the package as described in README.md, or set ALADDIN_NATIVE_LIBRARY to the built library.")
    return path


def load_library():
    lib = C.CDLL(str(library_path()))
    signatures = {
        "abi": (U32, []), "error": (C.c_char_p, []), "source_id": (C.c_char_p, []),
        "create": (C.c_int, [P8, U64, C.c_char_p, C.POINTER(C.c_void_p)]),
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
    }
    for name, (result, args) in signatures.items():
        f = getattr(lib, "al_" + name)
        f.restype, f.argtypes = result, args
    if lib.al_abi() != 1:
        raise NativeError("Unsupported native ABI")
    return lib


class Machine:
    def __init__(self, rom: bytes):
        self.lib = load_library()
        self.handle = C.c_void_p()
        self.rom_sha256 = hashlib.sha256(rom).hexdigest()
        data = (U8 * len(rom)).from_buffer_copy(rom)
        self._check(self.lib.al_create(data, len(data), PROFILE_SHA256.encode(), C.byref(self.handle)))
        self._ram_pointer, size = P8(), U64()
        self._call("ram", C.byref(self._ram_pointer), C.byref(size))
        self._ram = (U8 * size.value).from_address(C.addressof(self._ram_pointer.contents))

    def _check(self, code):
        if code:
            raise NativeError(self.lib.al_error().decode("utf-8", errors="replace"))

    def _call(self, name, *args):
        if not self.handle:
            raise NativeError("Machine is closed")
        self._check(getattr(self.lib, "al_" + name)(self.handle, *args))

    def close(self):
        if self.handle:
            self._call("destroy")
            self.handle = C.c_void_p()
            self._ram = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @property
    def source_id(self):
        return self.lib.al_source_id().decode()

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

    def peek_ram(self, offset, size=1):
        if not self.handle:
            raise NativeError("Machine is closed")
        if offset < 0 or size < 0 or offset + size > 65536:
            raise ValueError("RAM range out of bounds")
        return bytes(self._ram[offset:offset+size])

    @property
    def ram_address(self):
        if not self.handle:
            raise NativeError("Machine is closed")
        return C.addressof(self._ram)

    def snapshot(self):
        size = U64()
        self._call("export", None, 0, C.byref(size))
        buf = (U8 * size.value)()
        self._call("export", buf, len(buf), C.byref(size))
        return bytes(buf)

    def restore(self, data):
        buf = (U8 * len(data)).from_buffer_copy(data)
        self._call("import", buf, len(buf))

    def frame(self):
        buf = (U8 * (320 * 240 * 3))()
        width, height = U32(), U32()
        self._call("frame", buf, len(buf), C.byref(width), C.byref(height))
        return width.value, height.value, bytes(buf[:width.value * height.value * 3])

    def audio(self):
        count = U64()
        self._call("audio", None, 0, C.byref(count))
        buf = (C.c_int16 * count.value)()
        self._call("audio", buf, len(buf), C.byref(count))
        return bytes(buf)  # supported Windows/Linux x64: little-endian PCM
