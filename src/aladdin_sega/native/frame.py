"""One game frame as the ordered list of main-loop steps, recovered or not.

The order is the original main loop's call sequence, identical in every
gameplay frame of the recording (docs/semantic-map.md section 1).  Each
step names its entry in the original (for the verification path, which
brackets the original between ``entry`` and ``exits``) and, when
recovered, the semantic callable that owns it natively.  Unrecovered
steps are gaps: native execution stops there, loudly.
"""
from __future__ import annotations
from dataclasses import dataclass
from .state import GameState, NativeGap
from ..game.objects.script_engine import Engine, Services, Trace
from ..game import pad, hud, player, video


@dataclass(frozen=True)
class Step:
    name: str
    entry: int
    exits: tuple = ()
    run: object = None          # callable(state, services) or None when not recovered
    note: str = ''


class NativeServices(Services):
    """Records the platform-facing event stream on the game state."""
    def __init__(self, state: GameState):
        super().__init__(Trace())
        self.state = state

    def sound(self, slot, sound_id, flush=True):
        self.state.events.append(('sound', self.state.frame, sound_id, flush))

    def frame_changed(self, slot, descriptor):
        self.state.events.append(('frame_upload', self.state.frame, slot, descriptor))

    def handoff(self, kind, slot, detail=()):
        raise NativeGap(f'engine service {kind}', 0, f'slot {slot} {detail}', self.state.frame)


def pad_read(state: GameState, services):
    if pad.read_pad(state.read, state.write, state.buttons):
        raise NativeGap('game start from attract mode', 0x1B3182, 'a button ended the attract demo', state.frame)


def attract_input(state: GameState, services):
    if not pad.attract_input(state.read, state.write, state.rom):
        raise NativeGap('game start from attract mode', 0x1B3182, 'the demo input stream ended', state.frame)


def vram_upload_flush(state: GameState, services):
    video.flush_upload_queue(state.read, state.write, lambda kind, data: state.events.append((kind, state.frame, data)))


def sprite_table_upload(state: GameState, services):
    video.upload_sprite_table(state.read, lambda kind, data: state.events.append((kind, state.frame, data)))


def tile_stream(state: GameState, services):
    video.stream_tiles(state.read, state.write, state.rom, lambda kind, data: state.events.append((kind, state.frame, data)))


def frame_counter(state: GameState, services):
    player.advance_frame_counter(state.read, state.write)


def publish_player_position(state: GameState, services):
    player.publish_position(state.read, state.write)


def pad_decode(state: GameState, services):
    pad.decode_directions(state.read, state.write)


def score_tally(state: GameState, services):
    hud.score_tally(state.read, state.write, lambda sound_id: services.sound(0, sound_id))


def animation_pass(state: GameState, services):
    Engine(state.memory(), services).animation_pass()


def motion_pass(state: GameState, services):
    Engine(state.memory(), services).motion_pass()


STEPS = (
    # after the VBlank wait (the frame boundary), in the original's call order (main loop at 1A8C16)
    Step('vram_upload_flush', 0x1AC726, (0x1AC782,), vram_upload_flush, 'recovered: game.video.flush_upload_queue (events)'),
    Step('sprite_table_upload', 0x1AB776, (0x1AB7A0, 0x1AB7A2), sprite_table_upload, 'recovered: game.video.upload_sprite_table (events)'),
    Step('tile_stream', 0x1AE0F6, (0x1AE19E,), tile_stream, 'recovered: game.video.stream_tiles (events)'),
    Step('camera_scroll_and_spawn_strips', 0x1AAA2A, note='FF7DA4 scroll routine; FFF0B9..BC -> spawn strips 1AE3FC/1AE406/...'),
    Step('attract_input', 0x1B315C, (0x1B317E,), attract_input, 'recovered: game.pad.attract_input (the demo pad stream)'),
    Step('pad_read', 0x1A8CEE, (0x1A8C16,), pad_read, 'recovered: game.pad.read_pad'),
    Step('frame_counter', 0x1A8C16, (0x1A8C1C,), frame_counter, 'recovered: game.player.advance_frame_counter'),
    Step('vdp_queue', 0x1A91C6, note='1B3208'),
    Step('publish_player_position', 0x1A8E0C, (0x1A8E3C,), publish_player_position, 'recovered: game.player.publish_position'),
    Step('player_ground_collision', 0x1AD7B4),
    Step('player_wall_collision', 0x1AD632),
    Step('player_jump_input', 0x1A986E),
    Step('player_attack_input', 0x1A99F0),
    Step('object_motion', 0x1ADE36, (0x1AE0AE,), motion_pass, 'recovered: game.objects.script_engine.Engine.motion_pass'),
    Step('object_level_collision', 0x1ADB5C),
    Step('contact_scan', 0x1ABB40, note='player-vs-object collision and the per-kind callbacks'),
    Step('pad_decode', 0x1A8C44, (0x1A8C8C,), pad_decode, 'recovered: game.pad.decode_directions'),
    Step('special_tile', 0x1B1E38),
    Step('player_horizontal_control', 0x1A9D98),
    Step('player_state_transitions', 0x1A9716),
    Step('camera_follow', 0x1AA8FA),
    Step('player_state_machine', 0x1A9304),
    Step('player_animation_selection', 0x1A9502),
    Step('contact_completion', 0x1ABD7E),
    Step('hud_health', 0x1B02EC, note='writes the OAM buffer'),
    Step('fall_check', 0x1A8F0C),
    Step('scroll_state', 0x1A8F04, note='writes FFEFD4'),
    Step('score_tally', 0x1B00CA, (0x1B0132,), score_tally, 'recovered: game.hud.score_tally'),
    Step('hud_counters', 0x1B01AC),
    Step('death_sequence', 0x1A8E3E),
    Step('object_animation', 0x1AC784, (0x1AC84E, 0x1B0334), animation_pass, 'recovered: game.objects.script_engine.Engine.animation_pass'),
    Step('sprite_table', 0x1AB7C4, note='objects, player and HUD pieces -> OAM buffer FF729A'),
    Step('wait_vblank', 0x1B249E),
)


def run_frame(state: GameState, buttons: int = 0) -> None:
    """Execute one native frame; raise NativeGap at the first step that is not recovered."""
    state.buttons = buttons
    services = NativeServices(state)
    for step in STEPS:
        if step.run is None:
            raise NativeGap(step.name, step.entry, step.note or 'not recovered', state.frame)
        step.run(state, services)
    state.frame += 1
