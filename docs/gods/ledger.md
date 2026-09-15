# Gods recovery ledger

Append-only, one line per recovered region or escalation, newest last.  The
grinder's only per-region record; `STATUS.md` is updated once per milestone.

Line format (pipe-separated, one line):

    date | entry / arms | shape | semantics | tests | cold run (node, frames, artifacts dir, status) | hits, fallbacks | commit or blocker

`hits` and `fallbacks` are the candidate worker's `candidate_stats` from the
named cold run's `comparison.json`.  A region whose hits are zero on the
recorded histories is `NOT_EXERCISED` and does not belong here.

## Rows

2026-09-15 | baseline (no region) | - | - | tests/games/gods/test_boot.py, test_recording.py | f0ac19738f19 (main at the time), 15,148 frames, artifacts/gods/verify-main-2026-09-15, PASS (original vs original); tree of two recordings 29,731 frames, artifacts/gods/verify-tree-2026-09-15, PASS | - | b117d68
2026-09-15 | 002806 camera follow step / hold, right, left x arms; y clamp; the x-negative, x-limit, y-negative clamps declined (unwitnessed) | RAM-only leaf returning to its caller | gods_sega.game.camera.camera_follow; plan gods_sega.boundary.camera_follow_plan; candidate 'camera' | tests/games/gods/test_camera.py (17) | f0ac19738f19, 15,148 frames, artifacts/gods/verify-camera-main, PASS; tree 29,731 frames, artifacts/gods/verify-camera-tree, PASS; mutant camera-mutant-result DIVERGENCE at frame 329 (artifacts/gods/verify-camera-mutant) | 6,678 hits, 0 fallbacks (tree: 11,448 hits) | 708404e
2026-09-16 | 002806 camera follow step / the x-limit clamp arm (00282C), witnessed by f40d7bcc9dda (three path classes, 1,130 hits on the tree) | RAM-only leaf, one more arm | camera.camera_follow unchanged; boundary._LIMIT_ARMS / WITNESSED_CLAMPS | tests/games/gods/test_camera.py over every census directory (61 fixtures MATCH) | f40d7bcc9dda, 17,620 frames, artifacts/gods/verify-camera-f40d7bcc, PASS; tree of eight recordings 107,519 frames, artifacts/gods/verify-camera-tree-2026-09-16b, PASS; mutant DIVERGENCE at frame 1,540 (artifacts/gods/verify-camera-mutant-f40d7bcc) | tree: 41,109 hits, 0 fallbacks (was 39,979 hits, 1,130 fallbacks) | this commit
