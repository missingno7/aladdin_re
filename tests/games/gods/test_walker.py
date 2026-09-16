"""The line walker (game/walker.py): Gods' Bresenham stepper with a persistent record, two ROM copies.

The semantic tier: the cold start's phase selection and setup for all four
directions and both slopes; a step's arithmetic; the budget yield; the
object copy's completion by its counter and the projectile copy's
caller-owned completion; the projectile copy's re-arm quirk; and the record
round trip.  The boundary and evidence tiers are in the entries' own test
modules (`test_walker_resume.py` for 00FFF0).
"""
import pytest

from gods_sega.game import walker


def test_the_cold_start_selects_the_phase_from_the_span_and_sets_up_the_accumulator():
    right_shallow = walker.start(10, 20, 30, 25)
    assert right_shallow.phase == ('+x', 'shallow') and (right_shallow.dx, right_shallow.dy) == (20, 5)
    assert (right_shallow.x, right_shallow.y, right_shallow.y_sign, right_shallow.error, right_shallow.counter) == (10, 20, 1, 10, 20)
    left_steep = walker.start(30, 25, 10, 5)
    assert left_steep.phase == ('-x', 'shallow')                                   # dx == dy is shallow (bcs is unsigned lower)
    assert walker.start(30, 25, 25, 5).phase == ('-x', 'steep') and walker.start(30, 25, 25, 5).y_sign == 0xFFFF
    up_steep = walker.start(0, 0, 3, 10)
    assert up_steep.phase == ('+x', 'steep') and up_steep.counter == 10 and up_steep.error == 5
    assert walker.start(5, 5, 5, 5).phase == ('+x', 'shallow')                   # a zero span is a shallow +x walk of dx 0
    assert walker.start(0xFFF0, 0, 0x0010, 0).phase == ('+x', 'shallow')          # signed compare: -16 > 16 is false...
    assert walker.start(0x0010, 0, 0xFFF0, 0).phase == ('-x', 'shallow')          # ... and 16 > -16 is true


def test_the_cold_start_signed_compare_and_wrapping_spans():
    # cmp.w d2,d0 is a signed compare of the start against the end; the spans are 16-bit differences.
    assert walker.start(0xFFF0, 0, 0x0010, 0).phase[0] == '+x'
    assert walker.start(0xFFF0, 0, 0x0010, 0).dx == 0x20
    assert walker.start(0x0010, 0x0100, 0xFFF0, 0x00F0).dy == 0x10 and walker.start(0x0010, 0x0100, 0xFFF0, 0x00F0).y_sign == 0xFFFF


def test_a_shallow_walk_steps_x_every_step_and_y_when_the_error_wraps():
    walk = walker.start(0, 0, 8, 2)                                                # dx 8, dy 2, error 4, counter 8
    after, budget, steps, completed = walker.run(walk, 3, 'object')
    assert (steps, budget, completed) == (3, 0, False)
    assert (after.x, after.y) == (3, 1) and after.error == 6 and after.counter == 8 - 2 - 1     # dbra twice, subq once
    assert after.phase == walk.phase


def test_a_steep_walk_steps_y_every_step_and_x_when_the_error_wraps():
    walk = walker.start(0, 0, 2, 8)                                                # dy 8, dx 2, error 4, counter 8
    after, budget, steps, completed = walker.run(walk, 5, 'object')
    assert (after.x, after.y, steps, budget, completed) == (1, 5, 5, 0, False)


def test_the_object_copy_completes_when_its_counter_runs_out_and_the_projectile_copy_never_does():
    walk = walker.start(0, 0, 4, 1)                                                # major 4
    after, budget, steps, completed = walker.run(walk, 100, 'object')
    assert completed and steps == 5 and budget == 95                               # dbra loops major + 1 times
    assert after.counter == 0xFFFE                                                 # -1 from the dbra, -1 from the subq
    projectile = walker.Walk(('+x', 'shallow'), 0, 0, 1, 4, 1, 2, 4)
    after, budget, steps, completed = walker.run(projectile, 100, 'projectile')
    assert not completed and steps == 100 and budget == 0 and after.counter == 3   # only the subq after the yield
    assert after.x == 100


def test_the_projectile_copy_rearms_its_leftward_steep_body_as_the_rightward_one():
    walk = walker.Walk(('-x', 'steep'), 50, 50, 1, 2, 10, 5, 10)
    after, *_ = walker.run(walk, 3, 'projectile')
    assert after.phase == ('+x', 'steep') and (after.x, after.y, after.error) == (49, 53, 9)
    assert walker.stores(after, 0xFFE19E, 'projectile')[0xFFE19E] == (0x009436, 4)
    same = walker.run(walker.Walk(('-x', 'steep'), 50, 50, 1, 2, 10, 5, 10), 3, 'object')[0]
    assert same.phase == ('-x', 'steep')


def test_a_record_round_trips_and_an_unknown_continuation_is_not_a_walk():
    walk = walker.Walk(('-x', 'shallow'), 0x0123, 0xFFF0, 0xFFFF, 9, 3, 4, 9)
    stored = walker.stores(walk, 0xFF4AB4, 'object')
    assert stored[0xFF4AB4] == (0x010098, 4) and len(stored) == 8 and stored[0xFF4AB4 + 16] == (9, 2)
    values = {(address, size): value for address, (value, size) in stored.items()}
    read = lambda address, size: values[(address, size)]
    assert walker.load(read, 0xFF4AB4, 'object') == walk
    assert walker.load(read, 0xFF4AB4, 'projectile') is None
    with pytest.raises(ValueError, match='zero budget'):
        walker.run(walk, 0, 'object')
