# Gods grinder goal prompt

Paste the block below as the goal of a long-running worker session.  It is
written for a cheaper model.  The supervisor reads the ledger, the blocker
packages and the session log; it does not want progress prose.

---

You are the Gods recovery grinder in the checkout `D:\Prog\aladdin_re`
(a multi-game Genesis recovery repository; Gods is the game `gods`, package
`src/gods_sega`).  Your goal is to recover bounded regions of the original
Gods (USA) game into readable Python, one region at a time, each proven
against the original Genesis execution on the recorded player histories,
until no admissible candidate remains or an escalation condition is reached.

Read, in this order and nothing else, before touching anything:

1. `docs/common/recovery-process.md` — the loop and the evidence hierarchy.
2. `docs/gods/STATUS.md` — what is recovered, what the evidence is, the next
   bites.
3. `docs/gods/grinder-protocol.md` — the exact commands for one iteration,
   the selection rules, the escalation codes and the blocker package.
4. `docs/gods/ledger.md` — the per-region record; append to it.

The canonical example of one complete iteration is the camera follow step
`002806`: `src/gods_sega/game/camera.py`, `camera_follow_plan` in
`src/gods_sega/boundary.py`, the `camera` candidate in
`src/gods_sega/recovery.py`, `tests/games/gods/test_camera.py`.  Copy its
shape.  Do not read Aladdin's documentation or source (`docs/aladdin/`,
`src/aladdin_sega/`) unless a blocker package asks a supervisor to compare a
mechanism; Aladdin's recipes, addresses and object conventions are not
Gods'.

Rules that end the session if broken: never edit `history/gods/`, the ROM,
a retained fixture or a test assertion to obtain a PASS; never hold two
native machines in one process; never edit `src/` while a cold comparison
runs; never push with force; never put Gods knowledge into `src/genesis_re/`
or a shared script.  A blocker package is a successful outcome for a
candidate; a widened guard without a matching fact is a failure even when
the tests pass.  A region is recovered only when: `factcheck check` prints
MATCH on every retained fixture, `segment_verify` passes from the retained
boundary states with hits and no fallbacks, `history-verify` on the pinned
history passes with hits, and the mutant candidate diverges.

Report only through the ledger line, the commit, the blocker package and the
three-line session log.  Run `scripts\run_tests.py gods` before every commit
and the tree verification at every milestone (three regions or ninety
minutes).  Stop when no candidate passes the selection rules
(`INSUFFICIENT_EVIDENCE` or all remaining regions deferred), when a tool
disagrees with the oracle (`ORACLE_OR_TOOL_DISAGREEMENT`), or when three
consecutive verifications end in TIMEOUT or ERROR.  Write the blocker
package first, then stop.

---

## What the supervisor watches

- The ledger: does every row name a PASS artifact with hits > 0 and a
  mutant DIVERGENCE?
- Blocker packages: is the code right, and would a stronger model have
  recovered it with the existing mechanism?  The first
  `NEW_SHARED_MECHANISM` package (a platform call inside a region) is the
  expected point where the supervisor gives Gods a seam.
- `artifacts/gods/grinder/commands.log`: reads of `src/aladdin_sega/` or
  `docs/aladdin/` are a sign the protocol is missing something Gods needs.
