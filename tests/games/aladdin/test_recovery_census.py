"""Census hooks must preserve canonical frame-zero input and machine execution."""
import pytest
import recovery_census
from genesis_re.history import HistoryStore
from aladdin_sega.profile import ROOT_ID
from genesis_re.history_runtime import GenesisRun
from genesis_re.machine import Machine
from aladdin_sega.profile import read_rom
from aladdin_sega.profile import ALADDIN


def test_census_preserves_frame_zero_input_and_original_terminal(tmp_path):
    events = [{'frame': frame, 'buttons': 1 << frame} for frame in range(4)]
    store = HistoryStore(tmp_path / 'history', ALADDIN.history_root)
    node = store.append(ROOT_ID, events, 4)
    rom = read_rom()
    entry = int.from_bytes(rom[4:8], 'big')
    with Machine(rom) as machine:
        machine.pad(1)
        machine.gates([entry])
        assert machine.run(instructions=1) == 'gate'
        expected_entry = machine.snapshot()
    with GenesisRun(ALADDIN, rom) as run:
        run.advance(4, events)
        expected_terminal = run.observable()
    output = tmp_path / 'capture'
    actual = recovery_census.capture_entries(
        [entry], lambda machine, pc: {'branch': 'entry'}, output, game=ALADDIN,
        history=tmp_path / 'history', node=node)
    key = f'{entry:06X}:entry'
    first = actual['first'][key][0]
    assert first['frame'] == 0
    assert first['history_id'] == node
    assert (output / first['fixture']).read_bytes() == expected_entry
    assert actual['terminal'] == expected_terminal
    with pytest.raises(ValueError, match='empty output'):
        recovery_census.capture_entries([entry], lambda machine, pc: {'branch': 'entry'},
                                       output, game=ALADDIN, history=tmp_path / 'history', node=node)


def test_census_retains_the_parent_state_that_preceded_each_child(tmp_path):
    store = HistoryStore(tmp_path / 'history', ALADDIN.history_root)
    node = store.append(ROOT_ID, [], 2)
    rom = read_rom()
    entry = int.from_bytes(rom[4:8], 'big')
    with Machine(rom) as machine:
        machine.gates([entry])
        assert machine.run(instructions=1) == 'gate'
        expected_parent = machine.snapshot()
        machine.gate(entry, bypass_once=True)
        assert machine.run(instructions=1) == 'limit'
        child = machine.info['pc']
    output = tmp_path / 'capture'
    report = recovery_census.capture_entries([child], recovery_census.kind_classifier, output,
                                             game=ALADDIN, history=tmp_path / 'history', node=node,
                                             parent=entry, retain=1)
    key = next(iter(report['counts']))
    assert key.startswith(f'{child:06X}:kind')
    assert report['parent'] == f'{entry:06X}'
    parent = report['parents'][key][0]
    assert parent['child'] == child and parent['parent'] == entry and parent['child_frame'] == 0
    assert (output / parent['fixture']).read_bytes() == expected_parent
    with pytest.raises(ValueError, match='parent entry'):
        recovery_census.capture_entries([child], recovery_census.kind_classifier, tmp_path / 'other',
                                       game=ALADDIN, history=tmp_path / 'history', node=node, parent=child)


# A five-instruction subroutine the boot code calls fourteen times in frame 4,
# and a routine called once just before it (found by tracing a cold boot).
BOOT_LEAF, BOOT_PARENT = 0x1E5800, 0x1E5780


def test_signature_census_retains_one_fixture_per_path_and_writes_the_index(tmp_path):
    import json
    import pathfacts
    store = HistoryStore(tmp_path / 'history', ALADDIN.history_root)
    node = store.append(ROOT_ID, [], 6)
    rom = read_rom()
    with GenesisRun(ALADDIN, rom) as run:
        run.advance(6, [])
        expected_terminal = run.observable()
    output = tmp_path / 'capture'
    report = recovery_census.capture_entries([BOOT_LEAF], recovery_census.kind_classifier, output,
                                             game=ALADDIN, history=tmp_path / 'history', node=node,
                                             parent=BOOT_PARENT, signatures=True)
    assert report['terminal'] == expected_terminal  # stepping the original did not perturb the replay
    plain = recovery_census.capture_entries([BOOT_LEAF], recovery_census.kind_classifier, tmp_path / 'plain',
                                            game=ALADDIN, history=tmp_path / 'history', node=node)
    key = next(iter(report['counts']))
    assert key.startswith('1E5800:kind') and report['counts'] == plain['counts']
    count = report['counts'][key]
    assert count >= 14
    cls = report['classes'][key]
    assert (cls['distinct'], cls['cut'], cls['unclassified'], report['signature_mismatches']) == (1, 0, 0, 0)
    row = cls['signatures'][0]
    assert row['count'] == count and row['signature']['instructions'] == 5 and row['first_frame'] == 4
    assert row['fixture'] == key.replace(':', '-') + '-p0.state'
    assert row['parent_fixture'] == 'parent-' + row['fixture']
    assert sorted(p.name for p in output.glob('*.state')) == sorted([row['fixture'], row['parent_fixture']])
    facts = pathfacts.trace((output / row['fixture']).read_bytes(), game=ALADDIN)
    assert pathfacts.signature_key(pathfacts.path_signature(facts)) == row['signature_key']
    index = json.loads((output / 'index.json').read_text())
    assert index['history_id'] == node and index['parent'] == '1E5780'
    (entry,) = index['rows']
    assert (entry['entry'], entry['count'], entry['instructions'], entry['natives']) == ('1E5800', count, 5, [])
    assert entry['fixture'] == row['fixture'] and entry['parent_fixture'] == row['parent_fixture']
    assert entry['writes'] is not None
    parent = json.loads((output / row['parent_fixture']).with_suffix('.json').read_text())
    assert parent['child'] == BOOT_LEAF and parent['parent_frame'] == 4 and parent['child_fixture'] == row['fixture']
