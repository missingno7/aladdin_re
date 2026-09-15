# Evidence model

The words the repository uses for what it knows, so that a claim never
outruns its evidence.  These distinctions are enforced by tools where they can
be (receipts, provenance fields, candidate names); the rest is discipline.

## Kinds of input

| kind | what it is | what it can support |
|---|---|---|
| **player history** | controller input recorded by a person playing through `play.cmd`, kept as an immutable cold-start node under `history/<game>/` | every claim about recovered behaviour; the census; the reference for segments |
| **constructed input** | `history-capture` paths, test fixtures, `--vary` sweeps, poked RAM | API and mechanism checks, reaching arms a recording never took, negative controls; never described as gameplay |
| **retained state** | a machine snapshot captured on a cold run of a player history at a known frame or entry (`*.state` + `.json` with the history id, frame, entry) | the local witness and the segment check; only as real as the history it came from |

## Kinds of execution

| kind | what runs | what it shows |
|---|---|---|
| **original** | the ROM alone on the shared machine | the oracle; determinism (`history-verify --candidate original`) |
| **candidate** | the original with recovered regions substituted at gates, the rest original | that the substituted regions leave the machine exactly as the original would (`history-verify --candidate NAME`) |
| **cached continuation** | a run resumed from a disposable player cache | acceleration; equal to the cold run by construction (checked), never evidence on its own |
| **fresh cold reconstruction** | a new process, power-on, the same inputs | that nothing in the live process was carrying the result |
| **independent native execution** | recovered code running the game with no original CPU, the oracle consulted only for timing alignment or not at all (Aladdin's native runtime) | that the recovered game is a game, not a set of patches; the strongest tier and the only one that is a port |

"Oracle-assisted" means the original was consulted during the run (aligned
clocks, per-step comparison); "independent" means it was not.  The Aladdin
native runtime reports both modes separately (`../aladdin/native-frontier.md`).

## Kinds of comparison

| comparison | granularity | tool |
|---|---|---|
| immediate equality | the effects of one activation on one state | `factcheck check` |
| strict machine-effect equality | every fact: writes, registers, CCR incl. X, cost, last PC | `factcheck check` (MATCH means all of them) |
| future continuation | N frames after a retained state, every frame's state/video/PCM against the reference | `segment_verify` |
| complete recorded history | every canonical frame from power-on, two fresh workers | `history-verify` |
| tree | every branch of the history DAG | `history-verify --tree` |
| negative control | a deliberately wrong candidate diverges at the first affected frame | `history-verify --candidate <mutant>`, `segment_verify --candidate <mutant>` |

## Claims and their limits

- A **MATCH** covers the retained fixtures it ran on: the path classes the
  census found in the recordings, not the routine.
- A **PASS** covers one history (or tree), one candidate, the native binary and
  source tree in its receipt.  It says nothing about arms no recording entered.
- **Coverage** is stated in path classes and hits (`6 paths, 6,678 hits`),
  never as a percentage of the game.
- **Fallbacks** are the honest remainder: counted per gate and reason in every
  PASS report; a candidate with zero hits is `NOT_EXERCISED`.
- A **full-route** recording establishes that everything on that route is
  reproduced; it does not establish the routes not taken, the inputs not
  pressed, or hardware accuracy.
- **Caches** (player caches, native boundary caches) are keyed by game, ROM,
  profile, native binary, state contract and, for candidates, the source
  tree; they accelerate reconstruction and are never identity or proof.

## Provenance that must travel with a result

Every verification report carries a receipt: the native source id and binary
hash, the Python module hashes of the shared package and the game's package,
the game and profile hash, the candidate name, the history id.  `verify_status`
reports `STALE_EVIDENCE` when a PASS was produced by a different source or
binary than the checkout.  Artifacts under `artifacts/` are local evidence,
not tracked; a document quoting a number names the artifact directory it came
from.
