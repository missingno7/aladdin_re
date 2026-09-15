import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("architecture", ROOT / "scripts/check_architecture.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_current_python_boundary():
    assert guard.check() == []


def test_accidental_framework_leak_is_detected():
    assert guard.violations("from port_forge.replay import verdict_record", filename="recovery.py")
    assert guard.violations("codec = b'PFGENS02'", filename="artifacts.py", package="genesis_re")
    assert guard.violations("from .verification import Observer", filename="recovered.py")
    assert guard.violations("from .boundary import AtomicPlan", filename="recovered.py")
    assert guard.violations("plan = AtomicPlan()", filename="recovered.py")
    assert guard.violations("from ...machine import Machine", filename="game/objects/contact.py")
    assert guard.violations("from genesis_re.machine import Machine", filename="game/objects/contact.py")
    assert guard.violations("plan = AtomicPlan()", filename="game/objects/contact.py")
    assert not guard.violations("from genesis_re.machine import Machine", filename="recovery.py")


def test_shared_layer_may_not_import_a_game_except_in_the_registry():
    assert guard.violations("from aladdin_sega.boundary import LEAF_ENTRY", filename="history_runtime.py", package="genesis_re")
    assert guard.violations("import gods_sega", filename="frontend.py", package="genesis_re")
    assert not guard.violations("from aladdin_sega.profile import ALADDIN", filename="games.py", package="genesis_re")
    assert not guard.violations("from genesis_re.machine import Machine", filename="native/sound_service.py", package="aladdin_sega")


def test_recovered_semantics_are_packaged_with_compatibility_facade():
    from aladdin_sega import recovered
    from aladdin_sega.game.objects import collection, lifecycle

    assert recovered.clear_pair is lifecycle.clear_pair
    assert recovered.retire_collected_object is lifecycle.retire_collected_object
    assert recovered.collection_state is collection.collection_state
    assert recovered.increment_counter is collection.increment_counter


def test_architecture_check_walks_semantic_subpackage():
    assert (ROOT / "src/aladdin_sega/game/objects/lifecycle.py").is_file()
    assert (ROOT / "src/aladdin_sega/game/objects/collection.py").is_file()
    assert (ROOT / "src/genesis_re/machine.py").is_file() and (ROOT / "src/gods_sega/profile.py").is_file()
    assert guard.check() == []
