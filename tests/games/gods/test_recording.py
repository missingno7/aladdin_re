"""Recorded evidence: the retained states of the player-recorded Gods history verify against its reference.

Optional local evidence, like Aladdin's: the module skips unless
``artifacts/gods/evidence/main`` holds ``reference.json`` (the reference
worker's observations of the last PASS cold comparison of ``main``) and the
``boundary-*.state`` fixtures captured on a cold run of the same history.
Nothing here is tracked; regenerate both after a history extension.
"""
import json
from pathlib import Path

import pytest
import segment_verify

from genesis_re.history import HistoryStore
from gods_sega.profile import GODS

EVIDENCE = Path('artifacts/gods/evidence/main')
FIXTURES = sorted(EVIDENCE.glob('boundary-*.state'))
pytestmark = pytest.mark.skipif(
    not (EVIDENCE / 'reference.json').exists() or not FIXTURES or not GODS.history_path().is_dir(),
    reason='optional local recorded Gods evidence is absent')


def test_reference_belongs_to_the_current_main_recording():
    reference = json.loads((EVIDENCE / 'reference.json').read_text(encoding='utf-8'))
    store = HistoryStore(GODS.history_path(), GODS.history_root)
    assert reference['game'] == 'gods' and reference['history_id'] in store.nodes()
    assert reference['implementation']['rom'] == GODS.rom_sha256


@pytest.mark.parametrize('fixture', FIXTURES, ids=lambda p: p.stem)
def test_each_retained_boundary_state_matches_the_reference(fixture):
    report = segment_verify.check(fixture, game=GODS, frames=60, candidate='original', reference=EVIDENCE)
    assert report['status'] == 'PASS', report
    assert report['first_frame_pcm'] == 'compared'
