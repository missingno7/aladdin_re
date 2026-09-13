"""Independent contract checks for explicit synchronous sound seam facts."""
from pathlib import Path

from aladdin_sega import artifacts
from aladdin_sega.boundary import (
    COLLECTION_DISPATCH_ENTRY,
    CONTACT_SIBLING_ENTRY,
    CONTACT_SIBLING_WRAPPER,
    begin_collection_dispatch,
    begin_contact_sibling_dispatch_sound,
    begin_contact_sibling_dispatch_sound_seam,
    begin_contact_sibling_sound,
    begin_contact_sibling_sound_seam,
    begin_contact_sibling_wrapper_sound,
    begin_contact_sibling_wrapper_sound_seam,
)
from aladdin_sega.machine import Machine
from aladdin_sega.profile import DEFAULT_ROM, read_rom
from test_contact_retirement_review import _prepare_dispatch_wrapper, _prepare_wrapper
from test_contact_type13 import _prepare as prepare_type13
from test_recovery import native_write


ROOT = Path("artifacts/grinding/parent")
FIXTURE = ROOT / "sibling-census-old" / "1AEC00.alsnap"


def _machine():
    machine = Machine(read_rom(DEFAULT_ROM))
    artifacts.restore_snapshot(machine, FIXTURE.read_bytes())
    return machine


def test_direct_decrement_seam_preserves_command8_contract():
    with _machine() as machine:
        prepare_type13(machine, slots="first", sound=1)
        record = machine.registers()["a1"]
        native_write(machine, record, b"\x10\x01")
        registers = machine.registers()
        seam = begin_contact_sibling_sound_seam(machine, registers)
        assert seam.prefix == begin_contact_sibling_sound(machine, registers)
        assert seam.suffix.__name__ == "finish_contact_sibling_sound"
        assert (seam.stack_basis, seam.resume_pc, seam.return_slot,
                seam.saved_frame, seam.frame_size, seam.return_delta,
                seam.counts_contact) == (registers["a7"], 0x1AEC52,
                                          0x1AEC52, 24, 28, 28, False)


def test_direct_type13_seam_preserves_fixed_helper_contract():
    with _machine() as machine:
        prepare_type13(machine, slots="first", sound=1)
        registers = machine.registers()
        seam = begin_contact_sibling_sound_seam(machine, registers)
        assert seam.prefix == begin_contact_sibling_sound(machine, registers)
        assert seam.suffix.__name__ == "finish_contact_sibling_sound"
        assert (seam.stack_basis, seam.resume_pc, seam.return_slot,
                seam.saved_frame, seam.frame_size, seam.return_delta,
                seam.counts_contact) == (registers["a7"] - 4, 0x1AF1F6,
                                          0x1AF1F6, 20, 20, 24, False)


def test_wrapper_seam_distinguishes_contact31_from_command8():
    with _machine() as machine:
        _prepare_wrapper(machine, CONTACT_SIBLING_WRAPPER, d8=0,
                         object_type=0x10, contact_sound=True)
        registers = machine.registers()
        seam = begin_contact_sibling_wrapper_sound_seam(
            machine, registers, CONTACT_SIBLING_WRAPPER)
        assert seam.prefix == begin_contact_sibling_wrapper_sound(
            machine, registers, CONTACT_SIBLING_WRAPPER)
        assert seam.suffix.__name__ == "finish_contact_sibling_wrapper_sound"
        assert (seam.stack_basis, seam.resume_pc, seam.return_slot,
                seam.saved_frame, seam.frame_size, seam.return_delta,
                seam.counts_contact) == (registers["a7"] - 4, 0x1AE5B6,
                                          0x1AE5B6, 24, 28, 28, True)

    with _machine() as machine:
        _prepare_wrapper(machine, CONTACT_SIBLING_WRAPPER, d8=1,
                         object_type=0x10, contact_sound=True)
        native_write(machine, machine.registers()["a1"] + 1, b"\x01")
        registers = machine.registers()
        seam = begin_contact_sibling_wrapper_sound_seam(
            machine, registers, CONTACT_SIBLING_WRAPPER)
        assert seam.prefix == begin_contact_sibling_wrapper_sound(
            machine, registers, CONTACT_SIBLING_WRAPPER)
        assert seam.suffix.__name__ == "finish_contact_sibling_wrapper_sound"
        assert (seam.stack_basis, seam.resume_pc, seam.return_slot,
                seam.saved_frame, seam.frame_size, seam.return_delta,
                seam.counts_contact) == (registers["a7"] - 4, 0x1AEC52,
                                          0x1AEC52, 24, 28, 28, False)


def test_dispatch_seam_retains_wrapper_frame_and_contact_provenance():
    with _machine() as machine:
        _prepare_dispatch_wrapper(machine, 0x05, contact_sound=True)
        registers = machine.registers()
        entry, dispatch = begin_collection_dispatch(machine, registers)
        assert entry == CONTACT_SIBLING_WRAPPER
        seam = begin_contact_sibling_dispatch_sound_seam(
            machine, registers, dispatch, entry)
        assert seam.prefix == begin_contact_sibling_dispatch_sound(
            machine, registers, dispatch, entry)
        assert seam.suffix.__name__ == "finish_contact_sibling_wrapper_sound"
        assert seam.stack_basis == registers["a7"] - 8
        assert (seam.resume_pc, seam.return_slot, seam.saved_frame,
                seam.frame_size, seam.return_delta, seam.counts_contact) == (
                    0x1AE5B6, 0x1AE5B6, 24, 28, 28, True)

    with _machine() as machine:
        _prepare_dispatch_wrapper(machine, 0x10, contact_sound=True)
        native_write(machine, machine.registers()["a1"] + 1, b"\x01")
        native_write(machine, 0xFFF0D8, b"\x01")
        registers = machine.registers()
        entry, dispatch = begin_collection_dispatch(machine, registers)
        assert entry == CONTACT_SIBLING_WRAPPER
        seam = begin_contact_sibling_dispatch_sound_seam(
            machine, registers, dispatch, entry)
        assert seam.prefix == begin_contact_sibling_dispatch_sound(
            machine, registers, dispatch, entry)
        assert seam.suffix.__name__ == "finish_contact_sibling_wrapper_sound"
        assert seam.stack_basis == registers["a7"] - 8
        assert (seam.resume_pc, seam.return_slot, seam.saved_frame,
                seam.frame_size, seam.return_delta, seam.counts_contact) == (
                    0x1AEC52, 0x1AEC52, 24, 28, 28, False)
