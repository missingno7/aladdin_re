# Aladdin (USA): status

Current state only, kept short.  How it got here: `convergence.md`.  The
chronological log with every milestone's numbers:
`../archive/aladdin/status-log-2026-09-12-to-16.md`.  Last updated 16
September 2026.

## What runs today

- **The original**, cold from power-on, on the shared machine: every recorded
  history under `history/aladdin/` (24 nodes; the long route `44223150…`
  82,161 frames through levels 1, 2, 3, 0, 4, 5; four shorter cold starts
  `24c70ffc…`, `2dddf860…`, `43ec25b7…`, `e1500d66…`).
- **The candidate `lifecycle`** (`src/aladdin_sega/recovery.py`): the original
  with 62 gates armed over the object lifecycle, collection, contact and spawn
  families and their dispatchers; recovered semantics in
  `src/aladdin_sega/game/objects/`, exact effects in `boundary.py`.
- **The native runtime** (`src/aladdin_sega/native/`): the game with no
  original 68000 execution — power-on, title, options, attract, the main
  loop's 36 steps, the transitions (respawn, continue, level change, story
  pages, game over, pause), a VDP model and renderer, the ROM's Z80 sound
  driver as a platform service.  `play_native.cmd` plays it; histories under
  `history_native/aladdin/`.

## Evidence that passes

| claim | evidence | artifact |
|---|---|---|
| `lifecycle` reproduces the original on the 82,161-frame route: every frame's state, video, PCM equal; **92,588 candidate hits, 137 fallbacks, 18.13M instructions replaced** | `history-verify 44223150… --game aladdin --candidate lifecycle` (two fresh workers, 414 s) | `artifacts/multi-game-aladdin-main` (after the multi-game split; the same count as `artifacts/audit-frontier17` before it); `artifacts/seam-extraction-aladdin-main` (16 September, after the seam runner moved to `genesis_re.seam`: the same 92,588 hits, 137 fallbacks, 703 sound seams entered and returned); `artifacts/abi3-aladdin-main` (16 September, after the adapter began reporting refusal causes, ABI 3, and the replay cache key gained the observation instant: PASS, the same 137 fallbacks) |
| the native runtime runs the whole 82,161-frame route from its first main-loop frame to the end, byte- and sound-exact (aligned clock) | `scripts/aladdin/native_diff.py --cold 44223150 82161` | `native-frontier.md` §3c |
| cold start from power-on reproduces the four cold recordings; the boot's VDP port-write stream is identical (307,570 words on `43ec25b7`) | `native_diff.py --native-boot`, `verify_ports.py --boot` | `native-frontier.md` §3b–3e |
| independent mode (no oracle feedback) holds to frame 26,798 of the long route, then the declined-continue → title gap | `native_diff.py --independent` | `native-frontier.md` §1, §3 |
| the suite: `scripts/run_tests.py aladdin` (common + Aladdin), about 90 s | 2,822 tests | — |

## Where the frontier is

- **Candidate path (gates + plans):** the bounded frontier on the long
  recording is exhausted.  The 137 remaining fallbacks are 106 scheduler
  refusals concentrated in about thirty long frames (the spawn walker's batch
  straddling a VBlank) and about 31 command-stream engine ticks (1,000 to
  8,000 instructions with an interrupt inside).  Neither is a leaf; the
  ledger does not move again without a longer recording or a decision about
  the command-stream engine (`1ACD54`/`1B249E`/`1B263C`) and the unarmed
  game loop.  Open blocker packages: `blockers/`.
- **Native path:** the gaps are missing game logic, listed and classified in
  `native-frontier.md` §2–3 (the level-8 attract demo, the hidden
  button-sequence completion, the demo-table wrap, the remaining transition
  and title paths); no alignment machinery is planned.

## Is grinding active?

No.  The gate-based grind stopped on 15 September at the exhausted bounded
frontier; the native runtime phase followed and then the multi-game split.
Resuming either path: `recovery-playbook.md` (candidate grind, recipes and
escalation codes) or `native-frontier.md` §4 (the native loop).  The grinder
prompt for the candidate grind is `grinder-goal.md`; its first targets
section is historical (those leaves are recovered) and must be re-derived from
a current frontier ledger before use.

## Where things are

| what | where |
|---|---|
| recovered semantics | `src/aladdin_sega/game/` (`objects/`, `player.py`, `scroll.py`, `level.py`, …); `recovered.py` is a facade |
| exact boundary, dispatcher | `src/aladdin_sega/boundary.py`, `recovery.py` |
| native runtime | `src/aladdin_sega/native/` (`boot`, `frame`, `sequences`, `title`, `vdp`, `render`, `sound_service`, `oracle`) |
| tools | `scripts/aladdin/` (witnesses, `native_replay`, `native_diff`, `verify_step`, `verify_sequence`, `verify_ports`, `route_census`, `transition_witness`, `play_native`, `leaf_review`, `cartography/`) |
| tests | `tests/games/aladdin/` (`scripts/run_tests.py aladdin`) |
| histories | `history/aladdin/` (original), `history_native/aladdin/` (native runtime) |
| evidence | `artifacts/evidence/main` (census index + reference for `44223150…`), `artifacts/evidence/frames` (frame states), verification directories named in `ledger.md` |
| per-leaf record | `ledger.md` |
| the recording's semantic map | `semantic-map.md` |
