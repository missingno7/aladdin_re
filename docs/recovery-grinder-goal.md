# Grinder goal prompt

Paste the block below as the goal of a long-running worker session.  It is
written for a cheaper model.  The supervising session watches the ledger and
the blocker packages; it does not need progress prose.

---

You are the recovery grinder for the Aladdin (USA) Genesis recovery in
`D:\Prog\aladdin_re`.  Your goal is to keep recovering bounded branches of the
original game into Python, one leaf at a time, proven against the original
machine, until the ledger has no admissible row left or you hit an
escalation condition.  Follow `docs/recovery-grinder-protocol.md` exactly;
it defines the environment, the tools, the step loop, the cadence, the commit
rules, the escalation codes and the blocker package.  Nothing in this prompt
overrides it.

Start by reading, in this order and nothing else: the protocol, the current
section of `docs/STATUS.md`, and the last twenty lines of
`docs/recovery-ledger.md`.  Then run the frontier ledger on the newest PASS
artifacts named in the ledger and pick the next row as section 3 says.

Work rules that end a session if broken: never edit `history/`, the ROM, a
fixture or a test assertion to obtain a PASS; never hold two machines in one
process; never edit `src/` while a cold comparison runs; never push with
force.  A blocker package is a successful outcome for a row; a widened guard
without a matching fact is a failure even when the tests pass.

Report only through the ledger line, the commit, the blocker package and the
three-line session log.  Do not ask for permission for anything the protocol
already allows.  Stop when: the ledger is empty (`EMPTY_FRONTIER`), the
verifier has failed three milestone runs in a row (`VERIFIER_BLOCKED`), or a
tool disagrees with the oracle (`FACTORY_DEFECT`).  In each case write the
blocker package first, then stop.

---

## First supervised targets

Chosen from the frontier ledger of `artifacts/factory-baseline-main` and the
census in `artifacts/census-main-top` (82,161-frame `main`, fixtures and
retained parent states for every row).  The first three are RAM-only callback
children that return through `1AE6B4` to `1ABCA0`, the Type-55 recipe shape;
the fourth is an escalation drill.

1. `1AF5F0` (kind 58, 3,337 recorded hits, 6,668 fallbacks): seven path
   classes in `artifacts/evidence/main` (`1AF5F0-kind58-p0..p6.state`); the
   dominant one, p3 (2,748 hits), is 15 instructions, one write (`FF7DFC`),
   D0/D2/D7 residue, the Type-55 distance-guard shape with limit `0xC`; p4
   is the 6-instruction direct return.
2. `1AFA84` (kinds 74 and 75, 1,415 hits, 2,829 fallbacks): 13 instructions,
   one write, the same shape.
3. `1AFB36` (kinds 6E to 73, 3,172 hits, 6,277 fallbacks): 34 instructions,
   nine writes (motion, script and three flags), returns from `1AFBF2`; a
   larger RAM-only leaf, run `branches` over the record kind first.
4. `1AE796` kind 21 (the command-stream path, about 7,900 instructions, 234
   recorded hits): the expected outcome is a `NEW_MACHINE_MECHANISM` blocker
   package within a handful of tool calls, not a recovery.

## What the supervisor watches

- Reads per step: the number of `boundary.py` reads in `commands.log`.  If
  it stays at a handful of named functions, the file split can wait.
- Every `guards` line of `leaf_review.py` that is not `0 ... 0`.
- Any ledger line whose fallback count did not fall.
- Any blocker package: is the code right, and would a stronger model have
  recovered it with an existing recipe?  That is the factory defect to fix.
