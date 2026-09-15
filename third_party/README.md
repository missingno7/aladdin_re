# Source dependencies and notices

The project compiles Nuked OPN2 and Nuked PSG directly from the adjacent vendored
source directories. These are byte-exact copies of the pinned independent
upstream sources already present in the inspected donor checkout. No local
patches are applied. [upstream.json](upstream.json) records revisions, licenses
and SHA-256 for sources, headers, README and LICENSE. Git preserves their bytes.

| Component | Upstream and revision | Notice |
|---|---|---|
| Nuked OPN2 | https://github.com/nukeykt/Nuked-OPN2 · `335747d78cb0abbc3b55b004e62dad9763140115` | LGPL-2.1-or-later; original LICENSE and source notices retained |
| Nuked PSG | https://github.com/nukeykt/Nuked-PSG · `d15a168c676f4669e23660be9225b34ad7c1764e` | GPL-2.0-or-later; original LICENSE and source notices retained |
| Retained Genesis components | https://github.com/missingno7/port_forge · `07b147619f75f8a1fc570efd961c4c0c1e93ba3f` | No top-level license found in the inspected donor; no public redistribution permission asserted |

`sources.json` separately locks 27 runtime donor headers and 19 additional
native-test files. The board's two borrowed sound wrappers still include donor
copies of the core declaration headers. The build verifies that these declarations
are byte-identical to the direct upstream headers. There is only one compiled
copy of each sound core. Absorbing the wrappers is a future integration task,
not a completed claim of direct ownership of every sound-related file.

The inspected read-only donor root is
`D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge`.
[dependencies.json](dependencies.json) is generated from actual compiler records,
with active build objects and relative paths; the
[component ledger](../docs/archive/aladdin/component-migration.md) explains every dependency group.
System compiler headers are excluded from that focused graph.

CMake checks selected donor files and all direct upstream bytes at configure
time and before every incremental build. `BUILD_TESTING=OFF` requires only the
runtime closure. Receipts record adapter and dependency hashes, exact upstream
revisions, compiler options and source identity. A changed locked file stops the
build before native compilation.

## Focused local source handoff

An authorized local worker can export the runtime donor closure:

```powershell
.\.venv\Scripts\python.exe scripts\export_sources.py `
  --source D:\Games\DOS\dos_recosystem\aladdin_sega_forged\port_forge `
  --output D:\work\aladdin-portforge-sources
```

Add `--tests` to include the 19 additional native-test files. The exporter
validates selected hashes before creating a new directory, preserves original
relative paths under `source/`, and writes lock/provenance/notices under
`metadata/`. Existing output paths are refused. Point `PORTFORGE_ROOT` at the
resulting `source/`; disable native tests for a runtime-only export. Direct sound
cores are already included in this repository and are not copied from the donor
by this exporter. ROMs and unrelated framework files are never included.

This local handoff does not establish permission to publish the donor bundle,
binaries, or game. Combined-work distribution remains unresolved. Do not describe
the integration as permissively licensed. Each user supplies the ROM separately.

## Native ownership

`native/machine.cpp` is project code. It owns the machine allocation and uses
the retained scheduler for bounded admission, with a small project ABI for
Python. Snapshot identity uses a behavioral profile and explicit state contract;
build hashes remain provenance. Native state layouts never leak into Python.

Native PCM capture is bounded and checked. Overflow invalidates the run.
Explicit presentation discard advances chips and Z80 normally but cannot support
an all-PCM verification claim.
