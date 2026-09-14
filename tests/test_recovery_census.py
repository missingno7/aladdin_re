"""Census hooks must preserve canonical frame-zero input and machine execution."""
import pytest
import recovery_census
from aladdin_sega.history import HistoryStore, ROOT_ID
from aladdin_sega.history_runtime import GenesisRun
from aladdin_sega.machine import Machine
from aladdin_sega.profile import read_rom


def test_census_preserves_frame_zero_input_and_original_terminal(tmp_path):
    events = [{'frame': frame, 'buttons': 1 << frame} for frame in range(4)]
    store = HistoryStore(tmp_path / 'history')
    node = store.append(ROOT_ID, events, 4)
    rom = read_rom()
    entry = int.from_bytes(rom[4:8], 'big')
    with Machine(rom) as machine:
        machine.pad(1)
        machine.gates([entry])
        assert machine.run(instructions=1) == 'gate'
        expected_entry = machine.snapshot()
    with GenesisRun(rom) as run:
        run.advance(4, events)
        expected_terminal = run.observable()
    output = tmp_path / 'capture'
    actual = recovery_census.capture_entries(
        [entry], lambda machine, pc: {'branch': 'entry'}, output,
        history=tmp_path / 'history', node=node)
    key = f'{entry:06X}:entry'
    first = actual['first'][key][0]
    assert first['frame'] == 0
    assert first['history_id'] == node
    assert (output / first['fixture']).read_bytes() == expected_entry
    assert actual['terminal'] == expected_terminal
    with pytest.raises(ValueError, match='empty output'):
        recovery_census.capture_entries([entry], lambda machine, pc: {'branch': 'entry'},
                                       output, history=tmp_path / 'history', node=node)


def test_census_retains_the_parent_state_that_preceded_each_child(tmp_path):
    store = HistoryStore(tmp_path / 'history')
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
                                             history=tmp_path / 'history', node=node,
                                             parent=entry, retain=1)
    key = next(iter(report['counts']))
    assert key.startswith(f'{child:06X}:kind')
    assert report['parent'] == f'{entry:06X}'
    parent = report['parents'][key][0]
    assert parent['child'] == child and parent['parent'] == entry and parent['child_frame'] == 0
    assert (output / parent['fixture']).read_bytes() == expected_parent
    with pytest.raises(ValueError, match='parent entry'):
        recovery_census.capture_entries([child], recovery_census.kind_classifier, tmp_path / 'other',
                                       history=tmp_path / 'history', node=node, parent=child)
