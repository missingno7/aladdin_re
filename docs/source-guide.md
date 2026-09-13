# Where recovered source grows

The game source lives in `src/aladdin_sega/game/`. Organize it by connected game
behavior as that behavior becomes understood, rather than by ROM address or by
the order in which a witness was captured.

Current object modules are:

- `game/objects/lifecycle.py`: initialization, clearing, retirement, allocation,
  spawning and relocation effects.
- `game/objects/collection.py`: collection state changes and counters.
- `game/objects/contact.py`: contact state decisions and reaction/reset effects.
  A semantic function existing here does not imply every original caller or
  branch is admitted by the production candidate.

`recovered.py` is a compatibility facade. Existing callers can keep importing
its names while new semantic work belongs in the appropriate game module.
Splitting a file changes organization; it is not additional recovered coverage.
See `STATUS.md` and the recovery reports for the qualified domains and evidence.

## The boundary around this source

Game functions read authoritative state through supplied readers and calculate
game effects. They may still use original RAM offsets and ROM-backed data.
There is no second mutable game state to synchronize with machine RAM.

`boundary.py` translates the qualified behavior into exact outer guest effects:
registers, stack, CCR, instruction/cycle accounting and `AtomicPlan` admission
inputs. `recovery.py` owns candidate dispatch, fallback, the supported original
sound execution seam and negative-control policy. These concerns do not belong
inside the semantic modules.

A helper can have both recovered callers and original callers. Its standalone
adapter may remain necessary for the latter even after a larger Python caller
uses its semantics directly. Keep strict qualification fixtures as evidence;
remove a production adapter only when its remaining original callers are
accounted for. Do not infer that stack residue is dead from a passing replay.

## Adding source without fragmenting it

Prefer extending an existing coherent module while recovering adjacent behavior.
Add a module when a distinct, named responsibility and its dependencies are clear.
Do not create a file for every original subroutine or move policy into `game/`
to make a source count look better. The same game functions should remain useful
if their machine adapter is eventually replaced.

Execution receipts include nested Python modules. The edit-loop check copies
the whole package and mutates semantic lifecycle code, so moving source into
folders must preserve both provenance and the Python-only feedback loop.
