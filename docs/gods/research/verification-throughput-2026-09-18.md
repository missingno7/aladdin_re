# Verification throughput on Gods: where the loop's wall time goes, and a tiered loop

Read-only audit of the recovery/verification pipeline as the Gods grinder ran
it on 16–18 September (ledger rows 2026-09-16 … 2026-09-18, commits
`0a3d3f6` … `4ed0785`).  Every number below is measured: from the existing
artifacts (`artifacts/gods/verify-*/comparison.json` and the mtimes of the
worker outputs, `artifacts/gods/evidence/census-*/report.json`, the git log,
`artifacts/gods/grinder/session.log`) or from the profiling scripts under
`scripts/research/perf_*.py`, whose raw outputs are under
`artifacts/gods/research/perf/`.  Nothing tracked was modified; no
measurement changed a guard, a comparison or an evidence standard.  The
metric throughout is **verified semantic ownership per wall-clock hour**.

Machine: AMD Ryzen 9 7950X3D, 16 cores / 32 threads, 63 GiB RAM.  Native
binary `bb3479af…` (the 16 September rebuild that carried the observation
instant to 757,154).  Concurrent load during the audit: the grinder ran a
five-leaf `tree_verify.py` (10 worker processes, 21:20–21:25) and an
eight-leaf `census_all.py` (8 processes, from ~21:28); the measurements
taken under that load are marked *(loaded)*; the single-process profiles and
the concurrency sweep were taken while the machine was idle (0 other Python
processes, checked before each run).

While this audit ran, two commits landed on `main` from the concurrent
session: `ae2a97d` (`scripts/tree_verify.py`, one cold `history-verify` per
leaf concurrently; `verify_status.py` reading its `tree.json`; a three-tier
protocol in `grinder-protocol.md` with a milestone after up to five sealed
regions; `tests/games/gods/test_boundary_lint.py` for the name-collision
class) and `0413bc2` (`scripts/census_all.py`, one `recovery_census` per
leaf concurrently, made the default census).  They implement §C.1, §C.4's
first half and §G.1 below; their first runs are measured here (§A.4) and
the rest of this report is what they do not yet cover: the reference
stream recomputed on every run (§C.2), mutants that run 81 % of their
frames past their first difference (§C.3), the census key and multi-entry
runs (§C.4), per-gate counters (§C.5), staleness on comment edits (§C.6),
the native hash and the video render that are 42 % of every replay second
(§C.7–8), the perturbation and mutant-visibility tests (§G.2–3), and the
batch-size argument with its hard triggers (§F).

---

## A. The measured bottleneck table

### A.1 What one iteration costs, and where

Six recent iterations reconstructed from artifact creation times, source
mtimes and commit times (`scripts/research/perf_artifact_ledger.py`;
`artifacts/gods/research/perf/verify-runs.csv`):

| region (commit) | iteration wall | census | history-verify | mutant | tree | verification, sequential | share of iteration |
|---|---|---|---|---|---|---|---|
| `0075D6` player tail (`40aaf70`) | 87 min | 120 + 79 s | 192 s | 82 s | 688 s | 16.0 min | 18 % |
| `008222` contact search (`de06a50`) | 62 min | 8 × 39–86 s (7.9 min, sequential) | 232 s | 238 s | 841 s | 21.9 min | 35 % |
| `012DA0`/`012E5A` contact-consume (`69303fa`) | 56 min | 2 × 88 s | 216 + 221 s | 239 + 220 s | 528 s | 23.7 min | 42 % |
| `0044C0` trail check + composition (`7ff13e6`) | 92 min | 8 × 36–91 s (7.7 min) | 236 + 236 s | 231 + 230 s | 772 s | 28.4 min | 31 % |
| `007282` state 1 (`1eaf78e`) | 63 min | 132 s (state 0's, overlapping) | 236 s | 236 s | 835 s | 21.8 min | 35 % |
| `006FFE` state 0 (`b86fc2a`) | 43 min | — | 206 s | 206 s | 716 s | 18.8 min | 44 % |
| `006DA6` state 14 (`4ed0785`) | 114 min | 90 s | 198 s | 187 s | 708 s | 18.2 min | 16 % |

Every verification in every iteration ran **one after the other**:
`history-verify` (200–240 s on the 34,904-frame history), then the mutant
(the same again), then the tree (520–840 s), then the suite.  Censuses over
several recordings also ran one after the other (7.7–7.9 min for eight).
The grinder's own reading/writing/fixture-iteration time is the rest of an
iteration (≈ 35–80 min) and is not tooling; but the ~20–28 min of
sequential seals per region is, and it sits at the end of every iteration
where nothing else can happen.

Over the whole span (15 Sep 23:25 → 17 Sep 21:15, 45.8 h, 183 verification
directories, 238 census directories):

| activity | runs | wall | of which the **reference (original) worker** | notes |
|---|---|---|---|---|
| `history-verify --tree` (camera-sprites, eight recordings, 107,519 frames) | 54 | **10.52 h** | 9.29 h | 520–840 s each, typically ~700 s; 62 % of all verification wall |
| `history-verify` single history | 129 | 5.02 h | 4.97 h | 60–240 s each |
| of which mutant runs | 63 | 2.46 h | — | 81 % of their frames run **after** the first difference (§A.5) |
| `recovery_census` | 238 | 4.93 h | 4.66 h (94.5 % is the original's replay) | 16 censuses of `00FEC0`/`00FF54` found 0 occurrences: 17 min for no fixtures |
| all verification + census | | **20.5 h of the 45.8 h span** | **14.0 h of identical oracle re-execution** | the reference of `fb408bc75597` was recomputed 62 times (median 200 s), `f0ac19738f19` 61 times (83 s), the tree's 54 times (≈ 600 s) |

The original's observation stream for one (node, native binary, profile,
observation instant) is immutable.  It was computed 62 times for the main
history.  `history-verify` never reuses it: `compare_history` always
launches a fresh reference worker (`verification.compare_history`, roles
`("reference","original")`), and `execute_history` is called without
`use_cache` (the player caches are explicitly "not evidence" and the tree
mode forbids them).  The only tier that reuses the oracle is
`segment_verify` (`reference.json` beside the fixtures).

### A.2 Where a replay second goes (per frame, single process, idle machine)

`scripts/research/perf_frame_costs.py --node fb408bc75597 --skip 3000 --frames 600`
(`artifacts/gods/research/perf/frame-costs-original.json`, `…-camera-sprites.json`):

| layer | original worker | candidate worker (`camera-sprites`, 10.6 gate stops/frame: 9.5 `atomic` + seam resumes) |
|---|---|---|
| emulation only (`advance` without observer: what a census pays) | 2.44 ms/frame, **409 fps** | 3.55 ms/frame, 282 fps (gate stop + `registers` + planner + `atomic` + the `_run_to` bookkeeping = 1.11 ms/frame, ≈ 105 µs per gate stop, of which the planner itself is < 10 µs (§A.3) and the `registers`/`info`/`gates` crossings ≈ 10 µs; the remainder — the native `GateYield` stop and restart and `al_atomic`'s own admission run of the staged operation — was not split further) |
| + per-frame observation (`observable()`: what `history-run` pays) | 5.25 ms/frame, **191 fps** | 6.01 ms/frame, **166 fps** |
| observation overhead | **2.80 ms/frame = 53 % of the worker's time** | 2.46 ms/frame = 41 % |

The observation decomposed (`parts_ms_per_frame`, both runs agree within 0.1 ms):

| part | ms/frame | what it is |
|---|---|---|
| native `al_export` (snapshot) | **1.12** | the PortForge field codec over the whole machine (162,169 bytes) **plus two native SHA-256 passes** (inner PFGENS02 digest + outer ALNAT digest) |
| native `al_frame` (render + RGB copy) | **1.10** | render 320×224 from the VDP, convert to 215,040 RGB bytes |
| Python `sha256(snapshot)` | 0.07 | OpenSSL, 2.5 GB/s |
| Python `sha256(frame)` | 0.09 | |
| PCM drain + chained digest | 0.01 | 3.5 KiB/frame |
| `info` reads (9/frame) | 0.01 | |

Bytes hashed per frame: 705 KiB (162 KiB × 3 passes for the snapshot,
215 KiB frame, 3.5 KiB PCM) = **134 MB/s at 191 fps**.  The hashing itself is
not the cost — the *native* SHA-256 is: `perf_snapshot.py` measures the two
native passes alone (`al_snapshot_tick`, which only re-hashes) at **771 µs
for 324 KiB = 421 MB/s**, against 2,530 MB/s for `hashlib` on the same
bytes; the codec + copy is the remaining 318 µs.  So 71 % of the snapshot
export is a slow hash implementation, and `restore` (`al_import`, 1,255 µs)
pays the same two passes again plus the decoder.

Frame-hash redundancy, from the evidence: in **all 62 DIVERGENCE reports
in `artifacts/gods`, `state_sha256` differs at the first differing frame;
`frame_sha256` was never the first or the only differing field** (54 were
state-only; the rest state + counters/PCM).  The rendered frame is a
function of VDP state that the snapshot already contains, so 1.10 ms/frame
(21 % of a worker's time) has produced no discriminating evidence in 183
runs.  It remains valuable as a *diagnosis* field ("video bit-identical"
in the d3 report).

Startup is not a cost: import + DLL load + ROM + `GenesisRun` (which hashes
the 1 MB DLL and every Python module for the receipt) = 0.18 s; time to
first frame 5 ms; `Machine.__init__` 6–8 ms (the 1 MB ROM copy dominates).

### A.3 The cheap tiers, measured

| tool | cost | dominated by |
|---|---|---|
| `pathfacts.trace` on a retained fixture (state 14, 30–60 instructions to the handoff; contact search ~90) | 8–10 ms in-process | `Machine` open 6 ms + `restore` 1.3 ms; the stepping itself is **~30 µs/instruction** (3 crossings/instruction: `run`, `info`, `registers`; the 64 KiB RAM copy is a 1 µs `string_at` and the compare a memcmp — not pathological) |
| a planner call (`state14_plan`, `state1_plan`, `contact_search_plan`, `player_tail_plan`, `trail_check_plan`) | < 0.1 ms; 8–15 `peek_ram` crossings of 2–4 bytes (0.2 µs each) | the `Machine` open around it (6 ms) |
| `factcheck check` **per CLI invocation** | **0.22 s** (0.06 s interpreter + 0.11 s imports of capstone and the 6,917-line boundary, then two machines) | process startup; the protocol's `foreach` loop over 1,171 state-1 fixtures is 4.3 min of which 4.1 min is startup |
| `factcheck facts --path` | 0.20 s | same |
| `segment_verify … --frames 300` | 1.65 s (candidate) / 1.95 s wall | 300 observed frames at ~190 fps + the 6.4 MB `reference.json` parse |
| `run_tests.py gods` | ~68 s wall, 8 workers (STATUS; not re-measured: the run attempted here was aborted by the collection race in §A.6) | 5,925 of 6,735 tests are fixture-parametrized traces (88 %) at ~10–20 ms each ≈ 100 CPU-s; the segment tests ≈ 2 s per module |
| `recovery_census` (one node) | 31–243 s, 94.5 % replay | the original at ~480 fps (≈ 2.1 ms/frame) plus stepping every occurrence; a 0-occurrence entry still costs the full replay |
| `history-verify` single (34,904 frames) | 200–240 s | two workers at 160–185 fps, the candidate the long pole by 5–15 % |
| `history-verify --tree` (107,519 frames) | 520–840 s | one tree walk per worker at 150–180 fps |

`peek_ram` of a large span *is* pathological (64 KiB: 700 µs, a Python
list round trip through the ctypes slice) but no planner does it; the
tracer uses `ctypes.string_at`.

### A.4 Concurrency and saturation

`scripts/research/perf_concurrency.py --frames 1500 --workers 1,2,4,8,16,24`
(fresh processes, each replaying 1,500 observed frames of `fb408bc75597`;
`artifacts/gods/research/perf/concurrency-original.json`):

| concurrent workers | fps per worker | aggregate fps | startup per process |
|---|---|---|---|
| 1 | 225 | 225 | 0.18 s |
| 2 (= today's `history-verify`) | 189 | 378 | 0.19 s |
| 4 | 179 | 718 | 0.21 s |
| 8 | 177 | 1,416 | 0.28 s |
| 16 | 155 | 2,474 | 0.48 s |
| 24 | 139 | **3,333** | 0.73 s |

Today's two-worker verification uses **11 % of the machine's measured
replay capacity** (378 of ≥ 3,333 fps); a tree walk keeps 2 of 32 threads
busy for 12 minutes.  Memory is not a limit (65–70 MB RSS per worker).

The grinder's own five-leaf `tree_verify.py` run (10 processes, 21:20:31 →
21:24:45, *loaded* with nothing else) confirms it on the real workload:
reference workers 158–160 fps, candidate workers 128–138 fps on every leaf,
and the whole tree **PASS in 253.7 s against 700 s for the single walk**
(the longest leaf, `fb408bc75597`, 219 s reference / 253 s candidate).  The
history is five chains with no shared prefixes (every internal node has one
child; edges total 107,519 = the sum of the leaves' end frames), so per-leaf
cold runs duplicate nothing and make the same claim leaf by leaf.

### A.5 Mutants

63 mutant runs, 2.46 h.  The first difference is at the **first frame the
region is exercised** (median frame 2,261; median 6.5 % of the history), yet
the run continues to the end: **81.1 % of all mutant frames (1.23 M of
1.52 M) were executed after the first difference**.  Two mutants ended in
`CANDIDATE_ERROR` (a machine fault downstream of the divergence) and one in
`PASS` (blind), each costing a full run before the mutant was redesigned.

### A.6 Repeated setup and duplicated evidence

- **Identical censuses**: `census-00470C`, `census-00470C-fb408bc75597`,
  `census-00470C-fresh` (same node, entry, classifier; 88 + 100 + 88 s);
  `census-014084` / `-fresh`; `census-00BA8E` / `-fresh`; `census-006AD8` /
  `-entry`; `census-002806-fb408bc7` and, as this audit ran, `census-002806-all-*`.
  A census is a pure function of (node, entries, classifier, `--max-classes`,
  ROM, native binary, profile/instant, tracer + census source), and
  `report.json` already records all but the tracer's own hash.
- **Family entries censused one at a time**: the seven action-table handlers
  (`004A0A`, `004ACA`, `004D04`, `004E1C`, `004E74`, `005024`, `0048E4`) and the
  `00FEC0`/`00FF54` pair were censused as separate replays (7 × 73 s on one
  node; 16 × 43–99 s for the pair, all 0 occurrences).  `recovery_census`
  already accepts several `--entry` values in one replay.
- **Tree re-runs after non-executable edits**: consecutive tree runs with
  identical hits *and* fallbacks (`16`/`16b`, `18d`/`18e`, `18h`/`18i`,
  `18j`/`18k`, `walker`/`walker-b`) — five runs, ~1 h — were forced by
  `STALE_EVIDENCE`, whose receipt hashes whole module files: a docstring or
  comment edit re-seals the tree.  Only `18k` had a byte-identical receipt.
- **Collection race**: `run_tests.py gods` uses `pytest -n 8`, and each
  worker globs `artifacts/gods/evidence/census-*/…state` at collection; a
  concurrent census (the `census-002806-all-*` run at 21:28) made workers
  collect different fixture lists and pytest aborted ("Different tests were
  collected between gw0 and gw6").  Any FAST-tier test run during a census
  can fail this way.

---

## B. The proposed loop: FAST → REGION SEAL → MILESTONE SEAL

Tiers are defined by *what claim each produces* (`docs/common/evidence-model.md`),
and the time budgets are what the measurements above make possible.

### FAST (every edit; target < 60 s wall; no claim beyond the fixtures)

Inputs: the region's fixtures over **every recording** (`census_all.py`,
once per region; 90 s wall for eight leaves concurrently instead of
7.8 min sequential), the retained boundary states and `reference.json`.

1. `factcheck check` over all of the region's fixtures **in one process**
   (§E.4: 1,171 fixtures ≈ 12 s instead of 4.3 min through the CLI loop), or
   the module's fixture-parametrized test alone (`run_tests.py gods -- -k
   <concern>`, ~10–20 s).  Every fixture MATCH or DECLINED by name; the
   count of declines per named reason is the region's "declined arms"
   evidence, the same classes the tree will report.
2. The upper-half perturbation check on every fixture (§G.2; ~2× the check).
3. `segment_verify` from the retained boundary state nearest the region's
   first occurrence, 300 frames, candidate **and** mutant (4 s).
4. The focused tests of the concern.

What FAST cannot claim: temporal interaction beyond the segment window,
occurrences the census cap discarded (`overflow` must be 0), arms no
recording entered.

### REGION SEAL (once per region or per tightly-coupled pair; target ≈ 4–5 min wall)

Run **concurrently** (the machine has the headroom, §A.4): the region's own
candidate on the longest history that exercises it (cold, 200–240 s), its
mutant with stop-at-first-difference (§E.3: ~15 s instead of 200 s), and —
for a composition that changed a shared helper (`_evaluator_resolve`,
`_state14_main_dispatch`, `_tile_scan_cost`) — the composite `camera-sprites`
on that same history.  With the reference cached (§E.1) each of these is
one process.  Wall = the longest candidate run ≈ 240 s.  The standalone run
stays the attribution instrument (the ledger's "N hits, M fallbacks" for
the region's own candidate name) and the cleanest divergence diagnosis.

### MILESTONE SEAL (per family / batch of adjacent regions, before push; target ≈ 5 min wall)

`run_tests.py gods` (68 s) in parallel with the per-leaf tree
(`tree_verify.py`: 254 s measured; ≈ 140 s of candidate-only work once the
reference is cached and the longest leaf's candidate is the only long pole),
then the ledger/STATUS lines and the push.  Today the same claim costs
68 + 700 s sequentially.

Batching argument (§F): the tree caught three defects in 54 runs, every one
of them a path class a single-history census had not retained; with
`census_all` as FAST's input the tree's residual catch rate on leaves falls
to what the segment tier cannot see (temporal interaction), which in this
ledger it has never caught for a single-class RAM-only leaf.

---

## C. Implementation changes, ranked by expected throughput gain

Gain is estimated on the metric (regions verified per wall-clock hour),
taking the median iteration above (≈ 63 min, of which ≈ 22 min sequential
seals) as the baseline.  Risks name the proof contract each change must
keep (§D).

| rank | change | expected effect on the metric | risk / contract |
|---|---|---|---|
| **1** | **Per-leaf concurrent tree** (`tree_verify.py`, landed in `ae2a97d`) as the milestone seal | tree 700 s → 254 s; with (2) and the mutant leaf concurrent, the whole seal chain 22 min → ~5 min: **≈ +35–40 % regions/hour** on its own | none to the claim: each leaf is a full cold `history-verify` with its own receipts; `verify_status` reads `tree.json` (`ae2a97d`). Keep `--tree` for a divergence's diagnosis (it names the node in one report) |
| **2** | **Cache the reference observation stream** per oracle key (§E.1) | removes 14 h of identical work per 46 h; halves each run's CPU so (1), the mutant and the standalone run fit side by side; tree seal ≈ 140–250 s; enables (3) | key must be exactly the oracle's: native binary, ROM, profile hash, observation instant, state version, `genesis_re` modules, the game's `profile.py` — **not** the game's recovered modules; cached only from a determinism-checked run (original-vs-original PASS at that key exists: `verify-original-tree-instant`); `verify_status` checks the cache's receipts as it checks a PASS |
| **3** | **Stop the mutant at its first difference** (§E.3) | 200 s → ~15 s per mutant; the mutant then runs inside FAST as well as the seal; removes the downstream-fault tooling limit (`player-tail-mutant`, `next-random-mutant`, `pickup-probe-mutant`) | a DIVERGENCE claim needs only its first frame; PASS is unchanged (full stream required); `_validate_execution` must accept a truncated candidate stream *only* when it ends at a mismatch |
| **4** | **`census_all` as the FAST tier's input** (landed in `0413bc2`) + **multi-entry censuses** + **a census key lookup** (§E.6) | eight censuses 7.8 min → 90 s; families in one replay; duplicates skipped; and — the larger effect — the three tree-caught defect classes move from a 700 s discovery to a 15 s fixture check (§G) | none: the census is oracle-side; the key must include the tracer's and the census tool's source hash and `--max-classes` |
| **5** | **`hits_by_gate` and `fallback_reasons_by_gate` in `Candidate.stats`** (§E.2) | lets the composite per-leaf run stand in for the standalone run's ledger numbers when a region is a plain leaf (saves 200–240 s per leaf region), and makes the last PASS the cache of refusal classes per gate (§2) | none; additive counters |
| **6** | **Executable-identity staleness** (§E.5) | no re-seal after a comment/docstring edit: 5 of 54 tree runs (~1 h) | the receipt keeps the file hashes as provenance; STALE_EVIDENCE compares the AST-normalised identity; a change in any executable statement still re-seals |
| **7** | **Native SHA-256 replaced by an optimised implementation** in the snapshot codec (§E.7; a native change, needs a rebuild and one re-seal) | export 1.12 → ~0.45 ms, import 1.26 → ~0.6 ms: worker +13–18 % fps; census `Machine.restore` and every fixture test faster too | digests byte-identical (verify by diffing a fresh original run against a retained `reference.json`); the binary hash changes so every PASS re-seals once |
| **8** | **Frame render cadence** (§E.8: `frame_sha256` every Nth frame and at every endpoint, state every frame) | worker +20 % fps | **a contract change** (`contract` string must change; supervisor's decision): video is a function of the snapshot and has never been the first differing field, but the per-frame video statement would become per-Nth-frame |
| 9 | `factcheck check` over many fixtures per process (§E.4) | 1,171 checks: 4.3 min → 12 s, every time the grinder runs the protocol's `foreach` | none |
| 10 | Deterministic fixture globs under concurrent censuses (§E.9) | removes the collection race that aborts FAST during a census | none |
| 11 | Seed a standalone run from a retained original checkpoint before the region's first gate (§4) | 6.5–13 % on hot regions (the level-1 prologue), 30–99 % on rare ones (`004790` 58 %, `0091BC` 84 %, `0048E4` 43 %) | a different claim ("from frame N under the same inputs"); needs a gate-count proof that no gate of the candidate fires before N (an original replay with the gates armed and bypassed, recorded once per key); worth it only for rare regions, and only after (1)–(3) |
| 12 | `pathfacts.trace` cache per (fixture sha, ROM, native, tracer source, stop, cap) | the suite's 5,925 traces ≈ 100 CPU-s → seconds; ~20 s of the 68 s wall | none (pure function); low priority |

Combined estimate for (1)–(6): the sequential seal chain of ~22 min becomes
~5 min, and the three late-discovery classes become FAST-tier catches; on
the median iteration that is **1.4–1.6× regions per hour**, more on the
iterations the tree caught something (state 14: 114 min).  (7)–(8) add
another ~1.3× on every replay second.

---

## D. Proof obligations that must not be weakened

1. **Cold start is the claim.**  A PASS is "from power-on, every canonical
   frame, two fresh processes".  A seeded run (§C.11) is a different claim
   and must say so in `comparison.json` (`mode`) and in `verify_status`.
2. **Every canonical frame's full native state is compared** for a PASS.
   Any cadence change applies to the *video* field only, never to
   `state_sha256`, the PCM chain, the counters or the endpoints.
3. **The oracle is executed, never assumed.**  A cached reference is
   admissible only from a run at an identical oracle key whose determinism
   was itself verified (original-vs-original PASS at that key), and the key
   must include everything that can execute in an original run: native
   binary, ROM, profile hash, observation instant, state contract, the
   `genesis_re` package's modules, the game's `profile.py`.
4. **Receipts pin the evidence.**  Provenance keeps the exact file hashes;
   only the *staleness* test may use an executable identity (§E.5).
5. **The negative control must DIVERGE, not fault, not pass**, at the first
   frame the region is exercised; a mutant that PASSes a tier is a
   `FACTORY_DEFECT` regardless of how cheap the tier is.
6. **Fixtures are never adjusted**, and every retained fixture of every
   recording MATCHes or DECLINEs by name; a census with `overflow > 0` is
   incomplete evidence.
7. **Declines are counted by name**; refusals are exact by construction
   and are reported per reason; neither is silently folded.
8. **A seam's suffix identity is checked on every retained path.**
9. **A tree PASS precedes every push**, and a composition that edits a
   shared helper re-seals every gate that shares it (a batch boundary,
   §F).
10. **Constructed input is labelled** as such; a perturbed fixture (§G.2)
    is a mechanism check, never gameplay evidence.

---

## E. Concrete low-risk patches (described, not applied)

### E.1 Reference reuse in `compare_history` (`src/genesis_re/verification.py`)

- `compare_history(..., reference_cache=None)`: before `_run_workers`,
  compute the oracle key: `GenesisRun.cache_implementation` of an original
  run (already excludes the game's recovered `source`; add the SHA-256 of
  `genesis_re/*.py` and `<game>/profile.py` explicitly, since
  `cache_implementation` drops the whole `source` map) plus `selected`,
  `tree`.  Look for `artifacts/<game>/reference-cache/<key-sha>/<node-or-tree>.json`.
- If present and its embedded `receipt.native_binary_sha256` equals the
  current one, copy it to `output/reference.json`, skip the `reference`
  role in `_run_workers` (run only `candidate`), and record
  `report["reference_source"] = {"cached": path, "key": key}`.
- After any original-vs-original PASS (`candidate == "original"`), write the
  reference payload into the cache under its key (this is the only writer:
  a cached reference is always determinism-checked).
- `_validate_execution` runs unchanged on the cached payload (it validates
  shape and receipts; the `python_modules_sha256` check must, for the cached
  reference, compare only the `genesis_re/` and `<game>/profile.py` keys —
  the original never executes recovered modules, exactly the reasoning
  `cache_implementation` already encodes).
- `scripts/verify_status.py::classify`: a PASS whose `reference_source` is
  cached is PASS only if the cache's native hash and `genesis_re`/profile
  hashes match the checkout; otherwise `STALE_EVIDENCE` naming the
  reference.
- `scripts/tree_verify.py` and `segment_verify` need no change
  (`reference.json` lands where it always did).

### E.2 Per-gate hit and reason counters (`src/gods_sega/recovery.py`)

In `Candidate.stats` add `'hits_by_gate': {}` and
`'fallback_reasons_by_gate': {}`; in `on_gate`, when `_admit`/`_run_seam`
returns `True`, `self.stats['hits_by_gate'][f'{pc:06X}'] += 1`; in
`_fallback`, also `self.stats['fallback_reasons_by_gate'][gate][reason] += 1`.
`frontier_ledger.py` and the ledger lines can then quote a region's hits from
the composite run.  Aladdin's dispatcher is untouched.

### E.3 Stop at the first difference (`verification.py`, `cli.py`)

- `history-run --expect PATH`: `execute_history(..., expect=None)`; when
  given, load the expected observations (a `reference.json` payload), and in
  the per-frame `observe` callback compare `r.observable()` to
  `expected[node][index]`; on the first mismatch stop the edge (raise a
  private `_Stop`), record `result["stopped_at"] = {"node", "frame"}` and
  the truncated stream, and still emit `status: COMPLETED, compared: False`.
- `compare_history(..., stop_at_first_difference=False)`: pass `--expect
  output/reference.json` to the candidate command only when the reference
  is already on disk (E.1) and the flag is set.  `_validate_execution`
  accepts a candidate stream shorter than the node's frame count only when
  `stopped_at` is present **and** the last observation differs from the
  reference at that index; the report is then `DIVERGENCE` with the usual
  `first_difference`.  A PASS still requires the full stream.
- `dev.py history-verify --stop-at-first-difference`; the protocol's step
  11 uses it; `verify_status` prints DIVERGENCE as today.

### E.4 `factcheck check` over many fixtures in one process (`scripts/factcheck.py`)

`p.add_argument('fixture', nargs='+')` for `check` and `facts`; in
`command_check`, loop over `args.fixture` (expanding globs on Windows with
`glob.glob`), print one line per fixture prefixed by its name, exit with the
worst status, and add `--summary` (MATCH / MISMATCH / DECLINED counts by
reason).  The per-fixture logic (`_check_state`) is unchanged.  Also: when
the plan's `pc` is not the caller return and `--stop` was not given, use the
plan's `pc` as the stop (today the NOTE is printed but the exit is 1, which
misleads on handoff regions such as the state handlers).

### E.5 Executable identity for staleness (`src/genesis_re/receipt.py`, `scripts/verify_status.py`)

`source_modules()` gains a sibling `executable_modules()`: for each module,
`ast.parse`, drop docstring `Expr` nodes (module, class, function), and hash
`ast.dump(tree, include_attributes=False)`.  The receipt carries both
(`python_modules_sha256`, `python_executable_sha256`); `_validate_execution`
and `verify_status.classify` compare the executable map for
`STALE_EVIDENCE`, and `execute_history`'s "Implementation changed during
history execution" check uses it too.  The ledger keeps quoting the file
hashes.

### E.6 Census key and multi-entry protocol (`scripts/recovery_census.py`, `docs/gods/grinder-protocol.md`)

- Before replaying, compute `key = sha256(json(node id, sorted entries,
  classifier spec, max_classes, retain, parent, rom sha, native sha,
  profile sha, observation, sha256(pathfacts.py), sha256(recovery_census.py)))`
  and write it into `report.json`; add `--reuse`: if any
  `artifacts/<game>/evidence/census-*/report.json` carries the same key,
  print its directory and exit 0 without replaying.
- Protocol §3: census a family's entries in one run (`--entry A --entry B …`)
  and every recording at once (`census_all.py`); never census the same
  (node, entry) twice without a tracer change.

### E.7 Native SHA-256 (`native/`, the PortForge `pf::Sha256`) — not for the grinder

Replace the reference implementation with a SHA-NI / OpenSSL-backed one in
the snapshot encode/validate path only.  Acceptance: a fresh
`history-run f0ac19738f19 --candidate original` whose `observations` equal
`artifacts/gods/evidence/main/reference.json` byte for byte (same digests
⇒ same format), then one determinism PASS at the new binary hash, then the
tree re-seal.  Expected: `al_export` 1.12 → ~0.45 ms, `al_import` 1.26 →
~0.6 ms.

### E.8 Video cadence (contract change; supervisor's decision)

`GenesisRun.observable(video=True)`; `execute_history(..., video_every=1)`
renders and hashes the frame when `frame % video_every == 0` or at an
endpoint, else stores `None`; the report's `contract` becomes
`strict-genesis-every-canonical-frame-video-every-N`; `compare_observations`
treats `None` as "not observed" only when both sides agree it was not.  The
per-frame state claim is untouched.  Do not apply without the decision.

### E.9 Deterministic fixture globs (`tests/games/gods/*.py`)

A census writes its fixtures before `report.json`; the modules glob
`census-<PC>*/…state` directly.  Add a shared helper (a small
`tests/games/gods/evidence.py`, imported by the modules) that globs only
directories containing `report.json`, so a census in progress is invisible to
collection; each module's `FIXTURES = evidence.fixtures('006DA6')`.

### E.10 `tree_verify.py` (`ae2a97d`) — two additions

`--mutant NAME` runs the mutant on the longest leaf as one more concurrent
job; with E.1 the leaves share the cached reference; and `executed_frames`
should be reported from the leaves' `comparison.json` rather than recomputed
from the store, so a truncated or failed leaf cannot inflate it.

---

## F. Recommendation for the Gods grinder: batch size between seals

**Region seal every region (cheap once concurrent), milestone tree seal per
family of 3–6 adjacent regions, with three hard triggers that force an
immediate tree seal.**

The argument from the evidence:

- The tree caught three defects in 54 runs (≈ 7 % of the region increments):
  the `013264` write-order cue on the found-sound arm (16 Sep), the d3
  upper-half carry (18c), and state 14's five arm/store bugs (the cycle-only
  divergence on `7251bbd0ecf7`).  **All three were path classes or entry
  values that the single-history census had not retained**; two were then
  found and fixed by censusing the other recordings and re-running
  `factcheck check` — i.e. by the FAST tier once it had the right fixtures.
  Nothing the tree caught was a temporal interaction invisible to fixtures
  and segments.
- Adapter refusals are a constant background: across the 25 tree runs after
  the instant moved, `z80 bank guard` 4,214 → 4,621, `observation deadline`
  335 → 353, `vblank in span` 298 → 305, `machine admission` 27 → 27, `seam
  deadline` 443 → 503 — each new gate adds a handful; a candidate revision
  never changes them.  On the latest tree (`18o`): 5,809 of 6,827 fallbacks
  (85 %) are these exact refusals, 1,018 (15 %) are declines by name, and
  every declined reason on the tree corresponds to a DECLINED fixture count
  the FAST tier already reports.
- Cost model with per-leaf trees (254 s) and a bisect on divergence of ≈ 250 s
  (each region has its own candidate name, so the diverging leaf is re-run
  per region concurrently): per-region seal cost ≈ 254/N + 0.07 × 250 s.
  N = 1: 272 s; N = 4: 81 s; N = 6: 60 s; N = 8: 49 s.  Beyond 4–6 the
  saving is small and the rework of dependent compositions (a region
  composed over an unsealed sibling) grows.

Hard triggers for an immediate tree seal regardless of batch position:
(a) an edit to a shared boundary helper or cost fragment another sealed
gate uses (`_evaluator_resolve`, `_state14_main_dispatch`, `_tile_scan_cost`,
`_WR_*`, `_proximity_resolve`); (b) a seam or a composition that changes an
already-sealed plan's arms; (c) any FAST-tier DECLINED count on a recording
that was not part of the batch's censuses.  Plain leaves (one or few path
classes, RAM-only, every recording's fixtures MATCH, zero declines) may
batch to six; compositions and state handlers to three.

---

## G. Turning the expensive discoveries into cheap regression tests

| defect (ledger) | caught by | class | cheap catch now |
|---|---|---|---|
| `013264` award cue re-applied after the composition's write set; final byte wrong on the found-sound arm, visible only through the Z80/PCM (16 Sep, tree `16u`, frame 6,840) | tree | arm not among retained fixtures (the found-sound class was beyond the 32-class cap) | `census_all` + `--max-classes 400` + `overflow == 0` asserted; `factcheck check` then sees the double write (last-write-wins is what `check_plan` compares) — **fixture tier** |
| `_SC_` / `_TE_` cost-constant prefix collisions rebinding another region's constants (17–18 Sep) | the other region's tests | flat module namespace | **lint**: a test that parses `boundary.py` with `ast` and asserts no top-level name is assigned twice (dry-run here: 1,171 top-level names, 0 duplicates today; both historical collisions were duplicate `Assign` targets) — G.1 |
| d3 upper half carried from entry on the decrease band (`moveq` clears it) (18 Sep, tree `18c`, frame 9,661, state-only) | tree | every fixture had a zero upper half at entry — the plan's "preserve the upper half" was never exercised | **upper-half perturbation check** (G.2): for each fixture, poke a sentinel into the upper halves of d0–d7 at entry (`Machine.atomic` with `registers=`, as `factcheck.poke` pokes RAM), re-plan and re-trace; the plan must still MATCH.  Catches the whole "assumed preserved" class in ~2× a fixture check |
| state 14: arm B's nibble sub-test, `F1A4` clear, arm B's retry counter, D0 nibble clobber, D7 on rejoin, exit SR (18 Sep, cycle-only tree divergence on `7251bbd0ecf7`) | tree | five arms/values only other recordings reach | `census_all` before the seal; all five were then found by `factcheck check` — **fixture tier** |
| `00722C` `ble` not-taken cost (2 cycles) | `factcheck check` | cost | already cheap |
| `conditions` register mutant blind (dead residue); `grid-cell` register mutant blind; `pickup-probe` byte mutant crashed | full-history mutant (PASS / CANDIDATE_ERROR) | mutant visibility | the segment-tier mutant assertion each module already has (`mutant['status'] == 'DIVERGENCE'`), made generic: one test over every `MUTATIONS` entry asserting DIVERGENCE (not ERROR, not PASS) within 300 frames of a fixture that exercises it — G.3; plus E.3 so a full-history mutant never runs past its first frame |
| walker counter-off mutant drove the original into a cartridge write; player-tail STATE_COUNTER mutant faulted `001312`; `next-random` cursor mutant odd-address fault | full-history mutant (fault) | mutant safety | same G.3 (ERROR is a failure of the control, reported in seconds) |
| `record-id-scan` D0 mutant would index a VDP table out of range | reasoning before the run | mutant safety | G.3 |
| MOVEQ sign-extension and CCR (`0047DA`) | `factcheck check` | register model | already cheap; G.2 also exercises it |

G.1 (landed as `tests/games/gods/test_boundary_lint.py` in `ae2a97d`; the description stands as its specification) `ast.parse` of
`src/gods_sega/boundary.py`; collect top-level `Assign`/`AnnAssign` target
names and `def`/`class` names; assert each occurs once; also assert every
`_XX_*` cost constant's prefix maps to exactly one region comment block
(optional).  Runs in milliseconds.

G.2 `factcheck check --perturb-upper-halves` (and the same in the
fixture-parametrized tests as a second parametrization): after `restore`,
park at the entry with a one-instruction gate as `poke` does, admit an
`atomic` with `registers={f'd{i}': (regs[f'd{i}'] & 0xFFFF) | 0x5A5A0000}`
(only for data registers whose upper half the plan claims to preserve) and
`writes=[]`, snapshot, then run the ordinary check on that state.  A plan
that carries the entry upper half where the original clears it now
MISMATCHes on `register dN`.  Constructed input; never a gameplay claim.

G.3 `tests/games/gods/test_mutants.py`: for every `(name, (base, fn))` in
`recovery.MUTATIONS`, find one retained fixture of `base`'s gate whose
segment window exercises it (`segment_verify.check(..., candidate=base)`
with `candidate_hits > 0`), then assert the mutant's report is
`DIVERGENCE` (a `RuntimeError`/`NativeError` or `PASS` fails the test with
the mutant's name).  ≈ 2–4 s per mutant, 44 mutants, parallel under `-n 8`.

---

## Appendix: the numbers' provenance

- `artifacts/gods/research/perf/verify-runs.csv`, `census-runs.csv`,
  `tree-refusals.csv`, `mutants.csv`, `summary.json` —
  `scripts/research/perf_artifact_ledger.py` (no machine opened).
- `frame-costs-original.json`, `frame-costs-camera-sprites.json` —
  `scripts/research/perf_frame_costs.py` (idle machine; the `-smoke` file
  was taken under the ten-process tree run and shows the same split at
  173 fps).
- `snapshot.json` — `scripts/research/perf_snapshot.py` (idle).
- `tracer-state14.json`, `tracer-state1.json`, `tracer-contact-search.json`,
  `tracer-trail.json`, `tracer-player-tail.json` —
  `scripts/research/perf_tracer.py` (idle; includes a cProfile of one trace).
- `concurrency-original.json` — `scripts/research/perf_concurrency.py` (idle).
- The per-leaf tree measurement is the grinder's own
  `artifacts/gods/verify-camera-sprites-leaves-2026-09-18a/tree.json`
  (253.7 s, PASS) and its leaf directories' file mtimes.
- Iteration timelines: directory creation times under `artifacts/gods`,
  source mtimes under `src/gods_sega` and `tests/games/gods`, commit times
  from `git log`.
- Not measured here: the suite's own duration (STATUS: ~68 s; the attempt
  during this audit hit the collection race of §A.6 under the concurrent
  census and was not retried on the loaded machine).
