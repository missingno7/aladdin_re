"""The registry and the boundaries between games: profiles, ROM validation, histories, caches, snapshots."""
import hashlib

import pytest

from genesis_re import games
from genesis_re.history import HistoryStore
from genesis_re.history_runtime import GenesisRun, Session
from genesis_re.machine import Machine
from genesis_re.profile import NTSC, GameProfile

PRESENT = [game for game in games.GAMES.values() if game.rom_path.is_file()]
PAIRS = [(a, b) for a in PRESENT for b in PRESENT if a is not b]


def test_registry_lists_distinct_explicit_games():
    assert set(games.GAMES) == {"aladdin", "gods"}
    profiles = list(games.GAMES.values())
    assert len({p.id for p in profiles}) == len({p.profile_id for p in profiles}) == len(profiles)
    assert len({p.rom_sha256 for p in profiles}) == len({p.history_root["root"] for p in profiles}) == len(profiles)
    assert len({p.profile_sha256 for p in profiles}) == len(profiles)
    for profile in profiles:
        assert profile.board is NTSC and profile.package in ("aladdin_sega", "gods_sega")
        assert profile.history_path().as_posix() == f"history/{profile.id}"
    with pytest.raises(ValueError, match="Unknown game"):
        games.game("sonic")


def test_a_profile_needs_its_facts():
    with pytest.raises(ValueError):
        GameProfile(id="x", title="X", package="x", profile_id="x", rom_sha256="short", rom_size=1,
                    rom_filename="x.md", history_root={})


@pytest.mark.parametrize("game", PRESENT, ids=lambda g: g.id)
def test_each_present_rom_is_exactly_its_registered_revision(game):
    data = game.read_rom()
    assert len(data) == game.rom_size and hashlib.sha256(data).hexdigest() == game.rom_sha256
    assert games.for_rom(data) is game and games.registered(data) is game
    assert games.registered(b"\0" * 1024) is None
    with pytest.raises(ValueError, match="No supported game"):
        games.for_rom(data[:-1])


@pytest.mark.parametrize("game", PRESENT, ids=lambda g: g.id)
def test_a_wrong_or_truncated_rom_is_refused_loudly(game, tmp_path):
    wrong = tmp_path / "wrong.md"
    data = bytearray(game.read_rom())
    data[0x200] ^= 0xFF                      # same size, one byte of the entry code changed
    wrong.write_bytes(data)
    with pytest.raises(ValueError, match=f"Wrong {game.title} ROM revision"):
        game.read_rom(wrong)
    truncated = tmp_path / "short.md"
    truncated.write_bytes(game.read_rom()[:4096])
    with pytest.raises(ValueError, match="Wrong"):
        game.read_rom(truncated)


@pytest.mark.parametrize("a,b", PAIRS, ids=lambda g: g.id)
def test_one_games_history_store_cannot_be_opened_as_another(a, b, tmp_path):
    HistoryStore(tmp_path / "store", a.history_root)
    with pytest.raises(ValueError, match=f"belongs to root '{a.history_root['root']}'"):
        HistoryStore(tmp_path / "store", b.history_root)
    store = HistoryStore(tmp_path / "store", a.history_root)
    with pytest.raises(ValueError, match=f"not a {b.title}"):
        Session(b, store, b.read_rom())


@pytest.mark.parametrize("a,b", PAIRS, ids=lambda g: g.id)
def test_root_ids_and_node_ids_never_collide_across_games(a, b, tmp_path):
    left = HistoryStore(tmp_path / "a", a.history_root)
    right = HistoryStore(tmp_path / "b", b.history_root)
    events = [{"frame": 0, "buttons": 128}, {"frame": 3, "buttons": 0}]
    assert left.root_id != right.root_id
    assert left.append(left.root_id, events, 5) != right.append(right.root_id, events, 5)


@pytest.mark.parametrize("a,b", PAIRS, ids=lambda g: g.id)
def test_a_cartridge_runs_only_as_its_own_game(a, b):
    with pytest.raises(ValueError, match=f"are the {a.title} cartridge, not {b.title}"):
        GenesisRun(b, a.read_rom())
    with pytest.raises(ValueError, match=f"not the {b.title} cartridge"):
        Machine(a.read_rom(), b)


@pytest.mark.parametrize("a,b", PAIRS, ids=lambda g: g.id)
def test_snapshots_and_caches_do_not_cross_games(a, b, tmp_path):
    with GenesisRun(a, a.read_rom()) as run:
        run.step(0)
        state = run.machine.snapshot()
        store = HistoryStore(tmp_path / "a", a.history_root)
        node = store.append(store.root_id, [], 1)
        run.cache(store, node)
        implementation = run.implementation
    with GenesisRun(b, b.read_rom()) as other:
        assert other.implementation["game"] == b.id != a.id
        assert other.implementation["rom"] != implementation["rom"]
        assert other.implementation["profile"] != implementation["profile"]
        with pytest.raises(Exception, match="identity mismatch"):
            other.machine.restore(state)
        assert other.frame == 0
        # The other game's store cannot even be opened for this game, so its cache is out of reach;
        # a cache file dropped into this game's store under a foreign implementation id is ignored.
        foreign = HistoryStore(tmp_path / "b", b.history_root)
        foreign_node = foreign.append(foreign.root_id, [], 1)
        cache = next((store.path / "caches").rglob("*.cache"))
        planted = other._cache_path(foreign, foreign_node)     # where this game would look for its own cache
        planted.parent.mkdir(parents=True)
        planted.write_bytes(cache.read_bytes())
        assert not other.restore_cache(foreign, foreign_node)
        assert other.frame == 0


@pytest.mark.parametrize("game", PRESENT, ids=lambda g: g.id)
def test_cold_rerun_of_each_game_is_deterministic_and_progresses(game):
    frames = 120
    with GenesisRun(game, game.read_rom()) as first:
        first.advance(frames, [{"frame": 90, "buttons": 128}])
        one = first.observable()
    with GenesisRun(game, game.read_rom()) as second:
        second.advance(frames, [{"frame": 90, "buttons": 128}])
        two = second.observable()
    assert one == two
    assert one["frame"] == frames and frames - 10 <= one["vblanks"] <= frames and one["m68k_instructions"] > 0
    assert one["pcm_bytes"] > 0 and one["frame_sha256"] is not None
    assert one["buttons"] == 128
