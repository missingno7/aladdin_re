# Selected source dependencies

This initial integration depends on the user's local PortForge sources instead
of copying its framework or changing the old repositories. The CMake build uses
only the include closure for the Genesis board, interpreter, renderer, snapshot
codec, audio cores and seven selected test executables: 52 files, individually
pinned in `sources.json`. No third-party source changes were made.

| Component | Exact source | Notice / integration |
|---|---|---|
| PortForge M68000, Z80, board, VDP, renderer, snapshot codec and scheduler | `https://github.com/missingno7/port_forge`, commit `6c971b08c0698cd5fe56ab0ed855df4cbfc0b511` | Existing C++ components compiled into this project's local shared library. No top-level license was found in the inspected checkout; no public redistribution license is asserted. |
| Nuked OPN2 | `https://github.com/nukeykt/Nuked-OPN2`, revision `335747d78cb0abbc3b55b004e62dad9763140115` | Actual upstream notice: LGPL-2.1-or-later; unmodified sources under PortForge `third_party/nuked_opn2`, notices retained there. |
| Nuked PSG / YM7101 | `https://github.com/nukeykt/Nuked-PSG`, revision `d15a168c676f4669e23660be9225b34ad7c1764e` | Actual upstream notice: GPLv2-or-later; unmodified sources under PortForge `third_party/nuked_psg`, notices retained there. |

Inspected local root:
`D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge`.
The configured directory must match the locked file bytes; matching a commit
label alone is insufficient. Public distribution remains a separate licensing
decision; the locally built package must not be described as permissively licensed.

The C ABI adapter is new project code. It retains the inspected machine's
instruction-granular recognition/admission order and native sound batching. Its
pre-instruction gate uses the existing executor region boundary: pending IRQ
admission precedes the gate; a local C++ yield is caught by the engine and
translated only when this adapter's explicit gate flag was set. No exception or
longjmp crosses ctypes. No guest opcode is patched. The gate configuration is
debugger policy and is not serialized; armed bypass requests cannot be captured.

The native source identity is a digest of `native/machine.cpp` and the dependency
lock. Snapshot compatibility also requires the ROM/profile digest and explicit
codec version. This identity is independent of DLL layout, but that alone does
not establish cross-platform numerical equivalence.
