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

Genesis execution completes the native instruction that crosses a frame
boundary.  Its resulting tick can therefore pass the nominal frame tick.  That
machine-detail is observable in verification, but it is not part of history
identity; the canonical clock is the completed frame count.

Event frame `n` means set the controller mask before advancing interval
`[n, n+1)`. The Genesis adapter uses 896,040 master ticks per interval at
53,693,175 Hz (about 59.92 intervals/second). Inputs are sampled by the host at
these boundaries; there is no sub-frame event format. A future native port
must implement these logical input intervals, not instruction-boundary ticks.
The overshoot and PCM-drain checks are covered by executable history tests.

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

Screenshots are presentation metadata below `history/screenshots/`.  Genesis
caches are disposable implementation-specific accelerators below
`history/caches/`; they are checked against the ROM, native binary, state
contract and (for candidate runs) the Python source before use.  An original
run's cache survives a source edit, because recovered Python never executes
in it.  Removing either does not alter a history node or
prevent cold reconstruction.

## Commands

All examples use the source runner, which pins `src` and
`build/libaladdin_native.dll` without reinstalling a package:

```powershell
.\play.cmd
.\play.cmd --new
.\play.cmd --node main
.\.venv\Scripts\python.exe scripts\dev.py history-validate --history history
.\.venv\Scripts\python.exe scripts\dev.py history-export main --history history --output artifacts\history.json
```

`history-run` executes a selected path cold by default.  `--cache` permits a
compatible player cache as an optimization; it is not verification evidence.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py history-run main --history history --candidate lifecycle
.\.venv\Scripts\python.exe scripts\dev.py history-run main --history history --cache
```

`history-verify` starts separate fresh workers and compares strict state,
frame, PCM, and terminal observations.  `--tree` verifies every current branch
from cold root, using only prefix states calculated during that invocation.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --history history --candidate lifecycle --output artifacts\history-verify
.\.venv\Scripts\python.exe scripts\dev.py history-verify main --history history --candidate lifecycle --tree --output artifacts\history-tree
```

`history-capture` creates a constructed smoke scenario.  It is useful for API
and test checks, but it is not a user-gameplay recording or recovery evidence.

```powershell
.\.venv\Scripts\python.exe scripts\dev.py history-capture --history artifacts\history-smoke --frames 3 --input 0:8 --input 2:0 --checkpoint 2
```

Constructed histories can qualify the candidate paths they actually exercise;
they must never be described as user recordings or a completed playthrough.
Fresh user input histories are required for recorded-gameplay coverage.

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

Earlier replay and snapshot reports are retained as frozen recovery evidence,
including their ROM observations and strict comparison results.  The current
player and verification commands cannot load those formats. They
are not identity inputs to the input-history DAG.
