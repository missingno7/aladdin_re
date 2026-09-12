# Aladdin RE

Python-hosted original-ROM Aladdin, reusing the inspected PortForge Genesis
components through a small C ABI. The current Windows build reaches the initial
Agrabah level and supports recording, snapshots and headless replay. Game
replacements are disabled. See [docs/STATUS.md](docs/STATUS.md) for evidence and gaps.

## Play on this checkout

The Python 3.12 environment and native package have been installed locally:

```powershell
.\play.cmd
# Or:
.\.venv\Scripts\python.exe -m aladdin_sega play
```

You can also double-click `play.cmd` in Explorer. The launcher works from any
working directory and does not require PowerShell script execution to be enabled.
Use `play.cmd --mute` to mute playback. The older `play.ps1` is optional.

To record the entire cold boot, launch with:

```powershell
.\play.cmd --record-from-start
```

Recording starts at reset, before the first instruction or controller input.
Play normally, then press **F5** to stop and save, or close the game to save
automatically. The `.alreplay` file appears in `recordings/` and includes the
initial snapshot. F5 during an ordinary launch starts a mid-session recording.

To continue from a saved snapshot:

```powershell
.\play.cmd --snapshot "recordings\20260912T210633.203951Z.alsnap"
```

Add `--record-from-start` to record this resumed session from its snapshot anchor.
The new recording is labeled as a snapshot continuation, and the old files are
preserved. Held buttons from the save are released when you take control.

Audio now uses continuous PCM playback with a short startup buffer. For playback
diagnostics, add `--audio-report artifacts/audio.json`; it writes buffer counts,
underruns and startup-buffer silence on exit. Muting never freezes sound-chip state.

The ROM defaults to `assets/Aladdin (USA).md`. This `.md` is a binary cartridge,
not Markdown. Its exact SHA-256 is checked before execution. Supply your own ROM;
the cartridge, recordings and derived artifacts are ignored by Git.

| Key | Action |
|---|---|
| Arrows | D-pad |
| Z / X / C | Genesis A / B / C |
| Enter | Start |
| F5 | Start/stop original-mode recording, including a mid-session anchor |
| F6 | Save a snapshot |
| F7 | Pause/resume |
| F8 | Step one video frame while paused |
| F9 | Add a recording bookmark |

Captures go to `recordings/` with unique UTC filenames. Closing the player seals
an active recording. Focus loss releases all held buttons through the recording
path. The window title shows pause/recording state. `--mute` discards presentation
audio while both sound chips and the Z80 continue to execute.

## Build

Requirements: Python 3.12 x64, a C++17 compiler, and the pinned PortForge checkout
listed in [third_party/README.md](third_party/README.md). The source checkout is
read-only during the build. No whole PortForge application is built or launched.

Windows, using the existing MSYS2 toolchain (run from this repository):

```powershell
# Use your Python 3.12 executable to create .venv on a new checkout.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install cmake==4.4.3 ninja==1.13.2 scikit-build-core==1.0.3 pygame==2.6.1 pytest==9.1.1
$env:CMAKE_GENERATOR = 'Ninja'
$env:CMAKE_ARGS = '-DPORTFORGE_ROOT=D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge -DCMAKE_C_COMPILER=C:/msys64/mingw64/bin/gcc.exe -DCMAKE_CXX_COMPILER=C:/msys64/mingw64/bin/g++.exe -DBUILD_TESTING=OFF'
.\.venv\Scripts\python.exe -m pip install . --no-build-isolation --no-deps
.\.venv\Scripts\python.exe -m aladdin_sega doctor
```

Adapt the paths on another machine. All 52 dependency files are checked against
the committed SHA-256 lock before compilation. Native DLLs are loaded from the
installed package, with the MinGW runtime linked statically. Gameplay never
invokes a compiler or downloads dependencies. Reinstall after editing the Python
package; editable installs have not been qualified yet.

Headless Linux build is intended to use the same CMake project and source lock,
with a Linux compiler and `PORTFORGE_ROOT` path. Linux execution and Windows/Linux
artifact interchange remain unverified; do not infer support from the file format.

## Checks

```powershell
.\.venv\Scripts\python.exe -m aladdin_sega boot-check --frames 1800
.\.venv\Scripts\python.exe -m aladdin_sega replay recordings/your.alreplay --headless
.\.venv\Scripts\python.exe -m aladdin_sega snapshot-check recordings/your.alreplay --fresh-process
```

Append `--snapshot recordings/your.alsnap` (repeatable) to `snapshot-check` to
compare a separately saved live snapshot against the recording at its exact
timestamp and verify its remaining input sequence in a fresh process.

`boot-check` writes derived results and a PPM image under `artifacts/boot/`.
`snapshot-check` resumes an intermediate recording suffix in a new Python
process and compares complete serialized state, the final frame and every PCM
sample produced in that suffix. Neither command initializes pygame.

Run Python tests against the built library:

```powershell
$env:ALADDIN_NATIVE_LIBRARY = "$PWD/build/libaladdin_native.dll"
.\.venv\Scripts\python.exe -m pytest -q
```

To compile the seven selected upstream regression executables:

```powershell
.\.venv\Scripts\cmake.exe -S . -B build -G Ninja -DPORTFORGE_ROOT=D:/Games/DOS/dos_recosystem/aladdin_sega_forged/port_forge -DCMAKE_C_COMPILER=C:/msys64/mingw64/bin/gcc.exe -DCMAKE_CXX_COMPILER=C:/msys64/mingw64/bin/g++.exe -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
.\.venv\Scripts\cmake.exe --build build -j 4
.\.venv\Scripts\ctest.exe --test-dir build --output-on-failure
```

Set `Python_EXECUTABLE` and `CMAKE_MAKE_PROGRAM` to the corresponding `.venv`
executables if CMake finds a different Python or Ninja. Tests preserve assertions
in release builds. Synthetic tests and same-model replay equality are distinct
from independent hardware validation or a human gameplay corpus.
