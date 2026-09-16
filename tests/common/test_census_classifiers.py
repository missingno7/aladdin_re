"""The census classifiers that carry no game knowledge: one class per entry, or per register value at the entry."""
import pytest

import recovery_census


class FakeMachine:
    def __init__(self, **registers):
        self._registers = {**{f'd{i}': 0 for i in range(8)}, **{f'a{i}': 0 for i in range(8)}, 'pc': 0, 'sr': 0}
        self._registers.update(registers)

    def registers(self):
        return dict(self._registers)


def test_a_register_classifier_names_the_class_by_the_masked_value():
    classify = recovery_census.classifier('reg:d5.w')
    assert classify(FakeMachine(d5=0xABCD0007), 0x470C) == {'branch': 'd5-0007', 'kind': 7}
    assert recovery_census.classifier('reg:a1.l')(FakeMachine(a1=0xFFFF1234), 0) == {'branch': 'a1-FFFF1234', 'kind': 0xFFFF1234}
    assert recovery_census.classifier('reg:d0.b')(FakeMachine(d0=0x1FF), 0)['branch'] == 'd0-FF'
    assert recovery_census.classifier('reg:d3')(FakeMachine(d3=0x12345), 0)['branch'] == 'd3-2345'
    assert recovery_census._branch_kind('d5-0007') == 7 and recovery_census._branch_kind('kind2C') == 0x2C
    assert recovery_census._branch_kind('entry') is None


def test_the_named_classifiers_and_bad_specs():
    assert recovery_census.classifier('entry') is recovery_census.entry_classifier
    assert recovery_census.classifier('kind') is recovery_census.kind_classifier
    with pytest.raises(ValueError, match='register classifier'):
        recovery_census.classifier('reg:d9')
    with pytest.raises(ValueError, match='register classifier'):
        recovery_census.classifier('reg:d1.q')
    with pytest.raises(KeyError):
        recovery_census.classifier('object')
