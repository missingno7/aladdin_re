"""Recorded evidence: every retained parent state verifies over a short segment.

This is the parent-ownership tier on real recorded states.  It is optional
local evidence: the module skips unless ``artifacts/evidence/main`` holds an
``index.json`` from ``recovery_census.py`` and the ``reference.json`` of the
last PASS cold comparison of the same history (copy it there).  Regenerate
both after a history extension; nothing here is tracked evidence.
"""
import json
from pathlib import Path

import pytest
import segment_verify
from aladdin_sega.profile import ALADDIN

EVIDENCE = Path('artifacts/evidence/main')
pytestmark = pytest.mark.skipif(
    not (EVIDENCE / 'index.json').exists() or not (EVIDENCE / 'reference.json').exists(),
    reason='optional local recorded evidence is absent')


def parent_rows():
    index = json.loads((EVIDENCE / 'index.json').read_text(encoding='utf-8'))
    return [row for row in index['rows'] if row['parent_fixture']]


def test_every_retained_parent_segment_matches_the_reference():
    failures = []
    for row in parent_rows():
        report = segment_verify.check(EVIDENCE / row['parent_fixture'], game=ALADDIN, frames=2, reference=EVIDENCE)
        if report['status'] != 'PASS':
            failures.append((row['entry'], row['branch'], row['path_class'], report.get('first_difference')))
    assert failures == []


def test_recorded_type55_parents_own_the_child():
    rows = [row for row in parent_rows() if row['entry'] == '1AF590']
    if not rows:
        pytest.skip('no recorded Type-55 parent in this evidence')
    for row in rows:
        report = segment_verify.check(EVIDENCE / row['parent_fixture'], game=ALADDIN, frames=2, reference=EVIDENCE)
        assert report['status'] == 'PASS', report
        assert report['ownership'] != 'declined', report
