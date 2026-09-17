# Input history

**Every replay is a deterministic cold-start path through one immutable
input-history DAG. Checkpoints do not define replay beginnings. They are
visual navigation points with optional implementation-specific state caches.**

The player keeps an immutable history of controller input, not a saved machine
state.  A history begins at the fixed cold root and advances in canonical
simulation frames.  Every input event is normalized to a `frame` and an
eight-bit three-button-pad mask.  Nodes embed only the input segment since
their parent, so their ancestry reconstructs one complete cold-start path.

The root, ordered input digest, and ending frame determine a node ID.
Checkpoint placement, labels, screenshots, cache files, and the current `main`
reference do not.  Nodes are never edited: continuing from a checkpoint makes
a child branch.  `main` is only a movable convenience reference.

Every history replay reconstructs from this cold root.  It never begins from an
embedded machine snapshot.

Event frame `n` means set the controller mask at the first operation boundary
at or after the interval's nominal tick `n * 896,040` (53,693,175 Hz, about
59.92 intervals/second); there is no sub-frame event format.  Each interval is
observed, and recovered operations are deadlined, at the game's
*observation instant* inside the frame (`GameProfile.observation_offset_ticks`;
for Aladdin `n * 896,040 + 448,020`, raster line 131, the middle of the window
in which that game idles waiting for the next VBlank — measured in
`../archive/project/execution-model-research-2026-09-14.md`; for Gods
`n * 896,040 + 757,154`, raster line ~221, the parity wait just before the
vertical interrupt, measured in `../gods/research/`).  The instant is part
of the replay cache key (`cache_contract` 4): the original's trajectory is
the same at any instant, its observations are not.  A recovered operation admitted
before the nominal tick may therefore end after it; recovered regions contain
no controller read, so the game cannot observe whether the mask changed one
instruction or one operation after the tick, and the recorded trajectory is
unchanged to the instruction.  Genesis
execution completes the native operation that crosses either instant, so the
resulting tick can pass the nominal one; that machine detail is observable in
verification but is not history identity, whose clock is the completed frame
count.  A future native port must implement these logical input intervals, not
instruction-boundary ticks.  The overshoot, input-instant and PCM-drain checks
are covered by executable history tests.

Recovery caches are allowed only between completed steps, outside an active
synchronous legacy sound call. No Python activation is serialized. If a
candidate falls back to original execution before a step ends, the original
machine owns the remainder and the next completed step is safe to cache.

## Player

`play.cmd` launches from this source checkout and opens the history panel.
The panel shows each checkpoint at horizontal position proportional to its
completed frame and separates branch leaves into lanes.  Hovering or selecting
a point previews its optional screenshot; clicking a checkpoint starts that
branch.  **New** starts at the cold root and **Main** starts the current main
reference.

While playing, each completed frame journals the current held-button mask.
F5 and F6 both create manual checkpoints.  A normal session exit makes the
same kind of checkpoint automatically.  Resuming a branch begins with no host
keys held, so the next stepped frame records a zero mask if the saved branch
ended with a held button; the existing node remains unchanged.

Screenshots are presentation metadata below `history/<game>/screenshots/`.  Genesis
caches are disposable implementation-specific accelerators below
`history/<game>/caches/`; they are checked against the game, ROM, profile, native binary, state
contract and (for candidate runs) the Python source before use.  An original
run's cache survives a source edit, because recovered Python never executes
in it.  Removing either does not alter a history node or
prevent cold reconstruction.

## Commands

All examples use the source runner, which pins `src` and
`build/libgenesis_native.dll` without reinstalling a package:

Every store belongs to one game: `history/<game>/` (`history/aladdin`,
`history/gods`), with the game's root record in its manifest.  Commands take
`--game`; `--history` overrides the store directory.

```powershell
.\play.cmd
.\play.cmd --game gods --new
.\play.cmd --game aladdin --node main
.\.venv\Scripts\python.exe scripts\dev.py history-validate --game aladdin
.\.venv\Scripts\python.exe scripts\dev.py history-export main --game aladdin --output artifacts\history.json
```

`history-run` executes a selected path cold by default.  `--cache` permits a
compatible player cache as an optimization; it is not verification evidence.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py history-run main --game aladdin --candidate lifecycle
.\.venv\Scripts\python.exe scripts\dev.py history-run main --game aladdin --cache
```

`history-verify` starts separate fresh workers and compares strict state,
frame, PCM, and terminal observations.  `--tree` verifies every current branch
from cold root, using only prefix states calculated during that invocation.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --game aladdin --candidate lifecycle --output artifacts\history-verify
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --game aladdin --candidate lifecycle --tree --output artifacts\history-tree
```

`history-capture` creates a constructed smoke scenario.  It is useful for API
and test checks, but it is not a user-gameplay recording or recovery evidence.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py history-capture --game gods --history artifacts\history-smoke --frames 3 --input 0:8 --input 2:0 --checkpoint 2
```

Constructed histories can qualify the candidate paths they actually exercise;
they must never be described as user recordings or a completed playthrough.
Fresh user input histories are required for recorded-gameplay coverage.

## The oracle cache

The original's observation stream of a history depends on the shared
package, the native binary and source, the cartridge profile, the
observation instant, the cache contract, the ROM and the history's inputs
— never on a game's recovered code, which the original does not execute.
`compare_history` hashes those into an *oracle key* and stores the
reference worker's validated stream under it
(`artifacts/<game>/oracle/<key>.json`, or `$GENESIS_ORACLE_CACHE/<game>/`);
a later comparison of any candidate on the same history runs only the
candidate worker, validates the cached stream's shared-module and native
receipts, and compares.  The candidate's receipt — what evidence is judged
by — is always fresh; the report records the key and whether the stream
was cached; `--refresh-oracle` executes the original again.  The original
is deterministic run against run (checked on every Gods recording before
the cache existed), which is what makes the stream reusable.

## Portability boundary

`history-export` requires neither a native DLL nor a ROM. Its root, end frame
and full input stream suffice for another implementation to reproduce a node.
It can ignore the entire Genesis cache directory and attach its own caches to
the same node IDs. Changing code or the native build changes cache keys and
execution receipts, never history identity. A whole-game path has no different
format or length limit imposed by an M68000 instruction counter.

Current verification remains deliberately Genesis-specific: exact complete
native snapshot, frame pixels, ordered PCM hash chain and byte count, CPU/device
timing counters, PC/SR and terminal state at every logical frame. Registers and
RAM are contained in the native snapshot. Shared-prefix verification computes
its own states independently for each worker; continuous cold verification
restores none. Neither mode treats an unverified player cache as evidence.

## Historical artifacts

Earlier replay and snapshot reports (`.alreplay`, `.alsnap`; `../archive/`)
are retained as frozen recovery evidence, including their ROM observations
and strict comparison results.  The current player and verification commands
cannot load those formats.  They are not identity inputs to the input-history
DAG.
