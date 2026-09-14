# Recovery ledger

Append-only, one line per qualified leaf or escalation, newest last.  This is
the grinder's only per-leaf record; `docs/STATUS.md` is updated once per
milestone commit, `docs/recovery-cost-log.md` once per meaningful milestone.

Line format (pipe-separated, one line):

    date | entry kind/arm | recipe | semantics function | tests added | cold run (frames, artifacts dir, status) | fallbacks before -> after | commit or blocker

`fallbacks` is the candidate worker's total fallback count from
`comparison.json` of the named cold run; a leaf that does not lower it on the
recorded history was recovered from constructed evidence only and says so.

## Baseline rows

2026-09-14 | baseline of main (44223150b7d6, 82,161 frames) | - | - | 1,631 tests / 154 s | 82,161 frames, artifacts/factory-baseline-main, PASS (parallel, 403 s, 0 restores) | 37,458 fallbacks (72,249 hits) | 4284daf plus the leaves below
2026-09-14 | 1AF590 kind 55 / direct and selected-guard arms (FFF0BE set) | RAM-only leaf | contact_type55_guard, contact_type55_return | tests/test_contact_type55.py (+12) | included in the baseline run above | recorded history hits the FFF0BE-clear arm only; constructed evidence | landed with this batch
2026-09-14 | 1AF590 kind 55 / owned inside the contact scan (both callback maps) | scan ownership | - | test_type55_is_owned_inside_the_complete_contact_scan | included in the baseline run above | scan-slot 1AF590 fallbacks 3 -> 0 on the 26,378-frame node; 0 on main | landed with this batch
2026-09-14 | 1AE64C kind 43 / active, sound-on arm | single sound seam (two native calls inside the seam) | contact_type43_update | tests/test_contact_family.py (+8) | included in the baseline run above | 34 recorded hits: 18 recovered, 16 decline on the inactive arm (type43 inactive early return) | landed with this batch
2026-09-14 | evidence tooling (no leaf) | census retains by executed path; index.json; segment_verify; original caches survive source edits; fallbacks by gate | - | tests/test_segment_verify.py, test_recorded_evidence.py, census/pathfacts/history/recovery/ledger tests | 82,161 frames, artifacts/evidence-tooling-main, PASS (parallel, 537 s alongside tests, 0 restores) | 37,458 -> 37,458 (no leaf) | landed after the replay-evidence study; evidence in artifacts/evidence/main (33 classes, about 190 paths, 385 fixtures)
2026-09-14 | decoupled observation boundary (no leaf) | GenesisRun.step: input at the nominal tick, observation and deadline at OBSERVATION_OFFSET_TICKS; cache contract 2 | - | tests/test_history.py (+1, overshoot test updated) | 82,161 frames, artifacts/decoupled-baseline-main, PASS (parallel, 0 restores) | 37,458 -> 21,840 (scheduler refusals 15,691 -> 103; contact ticks owned 53,342 -> 65,338; instructions replaced 12.64M -> 15.41M) | landed from docs/execution-model-research.md
