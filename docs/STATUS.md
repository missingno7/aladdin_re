# Status — 13 September 2026

The project now has an immutable cold-start input-history model for player
sessions and verification.  It replaces the current play/replay/snapshot
workflow; machine snapshots are disposable Genesis cache material, never
history identity.  Python recovery remains selective.  No claim is made that
the game, its dispatcher, or the recovery task is complete.

## Current player and history model

Each history begins at one fixed cold root.  A node stores an immutable embedded
input segment with normalized frame/button events.  Its ID depends on the root,
input digest, and end frame, not on checkpoint placement, a label, screenshot,
cache, or `main` reference.  Continuing a checkpoint creates a new child.

The Genesis runner may complete the native instruction that crosses the logical
frame boundary; resulting ticks are observable execution details, not part of
the history identity.  Caches remain separately keyed by compatible ROM, native
binary, Python source, and state contract and can be discarded safely.

The pygame player opens a timeline before gameplay.  It exposes cold **New**,
the `main` reference, and checkpoint branches; F5/F6 make manual checkpoints
and a clean exit checkpoints automatically.  Every ordinary step journals its
held input mask.  A resumed branch releases saved held input through the next
canonical zero-mask frame instead of modifying prior history.

`history-run` executes a path cold by default.  `--cache` is an explicit player
optimization only.  `history-verify` uses fresh workers; `--tree` calculates
its own prefix states and compares every current branch.  `history-export`,
`history-validate`, and `history-capture` provide export, integrity, and
constructed-smoke operations.  Details and examples are in [history.md](history.md).

The redesign's source-pinned suite passed **681 tests** in 31.25 seconds. A constructed
4,200-frame continuous cold comparison matches original and lifecycle execution
at every frame: **205 candidate activations**, **zero restores**. Result,
continuation and timing controls each diverge on the 70-frame cold witness.
The disposable semantic edit check takes about **1.9 seconds per verdict**, with
no rebuild or reinstall. Native code and its binary are unchanged.

History tests cover checkpoint-independent identity, branching/autosave,
screenshots, incompatible/corrupt cache regeneration, fresh-process cold/cache
state/frame/PCM equality, shared-prefix traversal, and export without ROM/DLL.
Constructed raw-ROM witnesses retain strict allocator and dispatcher callback
qualification plus 150 original instructions and fresh-process continuation.
Receipts: [final audit](../artifacts/history-redesign/final-audit.json),
[full suite](../artifacts/history-redesign/final-suite.xml),
[cold comparison](../artifacts/history-redesign/verified-final/comparison.json).
Those redesign fixtures are constructed paths, not a recorded playthrough.

The subsequent user history through reported level 3 is now qualified on this
source: **9 checkpoints, 26,378 frames (440.20 seconds), 2,090 input changes**.
Both fresh-worker checkpoint traversal and uninterrupted cold original/lifecycle
comparison pass at every frame. All nine player caches and screenshots match
cold reconstruction; 480 recorded continuation frames after cache restore match,
and the latest cache matches in a fresh process. The candidate executes 3,846
activations, 5,299 direct Python calls and 199 legacy sound spans. Its 720
fallbacks preserve original execution and the strict comparison remains equal.
History/UI/verification tests (31) and machine/audio/carrier tests (34) pass.
The history was not modified. This qualifies the recorded path, not the whole
game. See the [level-3 operational report](../artifacts/level3-check/report.json).

Observation transfer now avoids the per-pixel Python list and exports each
snapshot only once into reusable 4 MiB scratch storage (the existing native
import limit). Returned snapshots remain independent bytes. No native API,
binary, state format or comparison contract changed. **683 tests pass** in
28.83 seconds. A controlled three-sample benchmark improves from 2.230 to
1.303 seconds per 300 observed original frames (**1.71x**), with identical
state/pixels/PCM. The complete 26,378-frame original/lifecycle cold comparison
passes in **230.74 seconds**; every original observation also equals the
pre-optimization run. The previous full comparison took approximately 405
seconds while another verification ran concurrently, so the controlled sample
is the cleaner speedup measurement. Evidence:
[benchmark](../artifacts/observation-speed/benchmark.json),
[full comparison](../artifacts/observation-speed/full/comparison.json),
[suite](../artifacts/observation-speed/suite.xml).

## Recovery remains in progress

The working tree contains mixed uncommitted recovery work around spawn dispatch
and known callback composition.  Its previous replay receipts are source-version
specific and must be regenerated after a source freeze.  Existing fallback,
strict state/PCM/future, fresh-process, alias, and mutation requirements remain
the acceptance bar for any admitted region.

Earlier collection, contact, selector, type-13, allocator, and spawn milestones
are retained as historical evidence.  They describe the ROM facts, constructed
fixtures, and recordings that existed at their freeze points; they do not assert
that legacy replay or snapshot loaders are available in the current player.
See [archive/STATUS-pre-history-2026-09-13.md](archive/STATUS-pre-history-2026-09-13.md)
and the retained subsystem reports for that evidence.

## Boundaries

The repository is a Windows x64 development environment for one verified USA
ROM revision.  It does not distribute a ROM, promise hardware accuracy, or turn
a comparison result into independent-console proof.  The native binding still
owns Genesis CPU/device execution; editable Python owns history, orchestration,
and recovered semantic islands.  Dependency and license details remain in
[third_party/README.md](../third_party/README.md).
