# Research tooling (read-only experiments)

Scripts that produced the studies under `docs/gods/research/`.  They read
the product (retained fixtures, histories, the native library) and write
only under `artifacts/gods/research/`; nothing here is part of the
recovery loop, the verification ladder or any game package, and nothing
here is a runtime mode.  The `vp_*` scripts import a `git show HEAD`
export of the source tree (`vp_common.py`) so that a concurrently edited
working tree cannot contaminate a measurement; make that export first
(`artifacts/gods/research/src-at-HEAD/`).  A result worth keeping moves
into a game's tooling with its own tests (`scripts/gods/vblank_slide.py`
came from `vp_slide.py`).

| prefix | study |
|---|---|
| `refusal_classifier.py`, `tick_timing_census.py`, `phase_shift_sweep.py`, `vblank_slide.py`, `slide_batch.py`, `disasm_range.py` | `docs/gods/research/timing-and-verification-2026-09-16.md` |
| `vp_*.py`, `vp_census_all.sh` | `docs/gods/research/timing-verification-pass-2026-09-16.md` |
| `zb_*.py` | `docs/gods/research/z80-bank-guard-2026-09-16.md` |
