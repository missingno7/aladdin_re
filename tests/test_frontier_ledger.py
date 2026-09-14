"""The frontier ledger classifies fallback reasons and joins refusals to their boundary site."""
import json
from pathlib import Path

import frontier_ledger

BOUNDARY = Path(__file__).resolve().parents[1] / 'src' / 'aladdin_sega' / 'boundary.py'


def test_ledger_classifies_targets_arms_scheduler_and_deadline(tmp_path):
    report = {'status': 'PASS', 'history_id': 'abc123', 'candidate_receipt': {
        'executed_frames': 26378, 'candidate_stats': {'fallbacks': 30, 'candidate_hits': 9000, 'fallback_reasons': {
            'unsupported domain: collection dispatch target 1AF228 is not recovered': 13,
            'unsupported domain: contact scan callback at slot 19: 1AF590 unresolved/device-or-sound': 3,
            'unsupported domain: type46 capped return arm is not recovered': 2,
            'scheduler admission': 1,
            'legacy deadline': 11,
            'unsupported domain: something new': 1}}}}
    (tmp_path / 'comparison.json').write_text(json.dumps(report), encoding='utf-8')
    summary = frontier_ledger.ledger(tmp_path / 'comparison.json', BOUNDARY)
    rows = {row['reason']: row for row in summary['rows']}
    assert summary['rows'][0]['count'] == 13
    target = rows['collection dispatch target 1AF228 is not recovered']
    assert (target['kind'], target['target'], target['site']) == ('UNRECOVERED_TARGET', '1AF228', None)
    scan = rows['contact scan callback at slot 19: 1AF590 unresolved/device-or-sound']
    assert (scan['kind'], scan['target']) == ('UNRECOVERED_TARGET', '1AF590')
    arm = rows['type46 capped return arm is not recovered']
    assert arm['kind'] == 'UNSUPPORTED_ARM'
    assert arm['site'].startswith('boundary.py:') and arm['site'].endswith(' begin_contact_family_type46_sound_seam')
    assert rows['scheduler admission']['kind'] == 'SCHEDULER'
    assert rows['legacy deadline']['kind'] == 'DEADLINE'
    assert rows['something new']['kind'] == 'OTHER'
    text = frontier_ledger.render(summary)
    assert 'unrecovered targets by fallback count: 1AF228 (13), 1AF590 (3)' in text
    assert 'begin_contact_family_type46_sound_seam' in text


def test_census_rows_join_counts_fixtures_and_parents(tmp_path):
    census = tmp_path / 'census'
    census.mkdir()
    (census / 'report.json').write_text(json.dumps({
        'history_id': 'abc123', 'counts': {'1AF228:kind3A': 13, '1AE64C:kind43': 4},
        'first': {'1AF228:kind3A': [{}, {}, {}], '1AE64C:kind43': [{}, {}, {}]},
        'parents': {'1AF228:kind3A': [{}, {}]}}), encoding='utf-8')
    rows = frontier_ledger.census_rows([census])
    assert [(row['entry'], row['count'], row['fixtures'], row['parents']) for row in rows] == [
        ('1AF228', 13, 3, 2), ('1AE64C', 4, 3, 0)]
    assert frontier_ledger.census_rows([tmp_path / 'absent']) == []


def test_every_literal_refusal_in_the_boundary_has_a_site():
    sites = frontier_ledger.refusal_sites(BOUNDARY.read_text(encoding='utf-8'))
    assert len(sites) > 100
    assert all(function for _, function in sites.values())
    line, function = sites['type55 transition arm is not recovered']
    assert function == 'begin_contact_family_type55' and line > 0


def test_cli_needs_a_comparison(tmp_path, capsys):
    assert frontier_ledger.main([str(tmp_path)]) == 1
    assert 'run history-verify first' in capsys.readouterr().out
