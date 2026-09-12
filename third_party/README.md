# Selected source dependencies

The Windows native binding uses a small, explicit closure from the user's local
PortForge checkout. `sources.json` locks 52 individual files by SHA-256. This is
not a vendored PortForge framework and the project does not alter that checkout.
The lock includes the Genesis board, M68000/Z80 interpreters, renderer, snapshot
codec, scheduler, selected test sources, and the required Nuked audio sources.

| Component | Pinned source | Notice and use |
|---|---|---|
| PortForge M68000/Z80, Genesis board, VDP, renderer, scheduler, snapshot codec | `https://github.com/missingno7/port_forge` at `6c971b08c0698cd5fe56ab0ed855df4cbfc0b511` | Compiled through this project's small C ABI. No top-level license was found in the inspected checkout; no public redistribution permission is asserted. |
| Nuked OPN2 | `https://github.com/nukeykt/Nuked-OPN2` at `335747d78cb0abbc3b55b004e62dad9763140115` | The selected PortForge files retain the LGPL-2.1-or-later notice. |
| Nuked PSG / YM7101 | `https://github.com/nukeykt/Nuked-PSG` at `d15a168c676f4669e23660be9225b34ad7c1764e` | The selected PortForge files retain the GPLv2-or-later notice. |

The inspected local root is:

```text
D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge
```

Matching the commit label is insufficient. CMake runs `scripts/check_sources.py`
at configuration and before incremental native compilation. Any byte mismatch in
the locked files stops the build. The resulting native receipt records the lock,
adapter hash, toolchain options, and generated source identity.

## Authorized local source handoff

For an authorized fresh Windows worker, export the focused closure rather than
asking them to reconstruct it or cloning an entire framework:

```powershell
.\.venv\Scripts\python.exe scripts\export_sources.py `
  --source D:\Games\DOS\dos_recosystem\aladdin_sega_forged\port_forge `
  --output D:\work\aladdin-portforge-sources
```

The exporter reads and verifies every selected source file before it creates the
new output directory. It retains each original relative path below `source/` and
writes the exact lock, provenance metadata, and this notice material below
`metadata/`. It refuses to overwrite an existing output directory. It does not
copy the ROM, unrelated PortForge files, a build directory, or a framework-wide
source tree.

This local handoff does not grant a right to publish the bundle, binaries, or
the game. Public distribution and combined-work licensing remain unresolved.
Do not describe this integration as permissively licensed. The ROM is never a
third-party dependency for export and must be supplied separately by its user.

## Native ownership

`native/machine.cpp` is project code. It keeps one native machine allocation,
uses the inspected scheduler's admission order, and exposes a narrow ABI to
Python. The binding's source identity incorporates the adapter and dependency
lock; build identity/receipt data additionally captures relevant toolchain
options. Snapshot admission separately checks the ROM, profile, codec boundary,
and explicit compatibility policy.

Native PCM capture is bounded and checked. Overflow invalidates the run rather
than silently losing samples. Explicit discard is allowed only for presentation;
it never stops chip or Z80 time and cannot produce an all-PCM verification claim.
