"""The shared seam runner: pause recovered execution, let the machine run a platform operation, resume.

A fake machine stands in for the native one; the runner's contract is what
is tested: only the resume PC is gated, a foreign activation at the resume
is bypassed, a changed guard or expected slot raises, the suffix is planned
from the live state and handed to the game's admission, a deadline leaves
the original in charge, and the machine always leaves with ``in_seam``
clear and the game's gates armed again.
"""
import pytest

from genesis_re.seam import AtomicPlan, Seam, UnsupportedCandidate, run_seam

RESUME, GATES = 0x001234, (0x000100, 0x000200)
FRAME = 0xFF7FE0


class FakeMachine:
    def __init__(self, *, stops=(), deadline_after=None):
        self.ram = bytearray(65536)
        self.registers_now = {'a7': FRAME, 'pc': 0x001000, 'd0': 0}
        self.in_seam = False
        self.stops, self.deadline_after = list(stops), deadline_after
        self.armed, self.bypassed, self.runs = None, [], []

    def peek_ram(self, offset, size=1):
        return bytes(self.ram[offset:offset + size])

    def put(self, address, value, size):
        self.ram[address & 0xFFFF:(address & 0xFFFF) + size] = value.to_bytes(size, 'big')

    def registers(self):
        return dict(self.registers_now)

    def gates(self, pcs):
        self.armed = tuple(pcs)

    def gate(self, pc, *, bypass_once=False):
        self.bypassed.append((pc, bypass_once))

    def run(self, *, target=0, instructions=0):
        assert self.in_seam and self.armed == (RESUME,)
        self.runs.append(target)
        if not self.stops:
            return 'limit'
        a7, mutate = self.stops.pop(0)
        self.registers_now.update(pc=RESUME, a7=a7)
        if mutate:
            mutate(self)
        return 'gate'


def seam(**overrides):
    fields = dict(prefix=AtomicPlan(10, 1, (), {'pc': 0x001100}, 0x001000), resume_pc=RESUME, stack_basis=FRAME,
                  guards=((FRAME, 8),), suffix=lambda machine, registers: AtomicPlan(16, 1, (), {'a7': registers['a7'] + 4}, RESUME))
    fields.update(overrides)
    return Seam(**fields)


def test_the_activations_own_return_plans_and_admits_the_suffix_from_live_state():
    machine = FakeMachine(stops=[(FRAME, None)])
    admitted = []
    outcome = run_seam(machine, 5000, seam(), admit=lambda plan: admitted.append(plan) or True, gates=GATES)
    assert outcome.status == 'completed' and outcome.reason is None and (outcome.stops, outcome.foreign_returns) == (1, 0)
    assert admitted[0].registers == {'a7': FRAME + 4}
    assert not machine.in_seam and machine.armed == GATES and machine.runs == [5000]


def test_a_foreign_activation_at_the_resume_is_bypassed_once_and_the_run_continues():
    machine = FakeMachine(stops=[(FRAME - 40, None), (FRAME, None)])
    outcome = run_seam(machine, 5000, seam(), admit=lambda plan: True, gates=GATES)
    assert outcome.status == 'completed' and (outcome.stops, outcome.foreign_returns) == (2, 1)
    assert machine.bypassed == [(RESUME, True)] and not machine.in_seam and machine.armed == GATES


@pytest.mark.parametrize('corrupt', [lambda m: m.put(FRAME + 4, 0x12345678, 4), lambda m: m.put(FRAME + 8, 0x9, 4)])
def test_a_changed_guard_or_expected_slot_is_a_contract_violation_not_a_fallback(corrupt):
    machine = FakeMachine(stops=[(FRAME, corrupt)])
    machine.put(FRAME + 8, 0x00ABCDEF, 4)
    with pytest.raises(ValueError, match='return/frame mismatch'):
        run_seam(machine, 5000, seam(expect=((FRAME + 8, 4, 0x00ABCDEF),)), admit=lambda plan: True, gates=GATES)
    assert not machine.in_seam and machine.armed == GATES


def test_a_declined_or_refused_suffix_is_reported_and_left_to_the_caller():
    def declining(machine, registers):
        raise UnsupportedCandidate('suffix arm not witnessed')
    machine = FakeMachine(stops=[(FRAME, None)])
    outcome = run_seam(machine, 5000, seam(suffix=declining), admit=lambda plan: True, gates=GATES)
    assert (outcome.status, outcome.reason) == ('declined', 'unsupported domain: suffix arm not witnessed')
    machine = FakeMachine(stops=[(FRAME, None)])
    outcome = run_seam(machine, 5000, seam(), admit=lambda plan: False, gates=GATES)
    assert (outcome.status, outcome.reason) == ('refused', 'scheduler admission')
    assert machine.bypassed == [] and not machine.in_seam and machine.armed == GATES


def test_the_deadline_inside_the_platform_operation_leaves_the_original_in_charge():
    machine = FakeMachine(stops=[])
    outcome = run_seam(machine, 5000, seam(), admit=lambda plan: pytest.fail('no suffix at a deadline'), gates=GATES)
    assert (outcome.status, outcome.reason, outcome.stops) == ('deadline', 'seam deadline', 0)
    assert not machine.in_seam and machine.armed == GATES
