"""One game frame as the ordered list of main-loop steps, recovered or not.

The order is the original main loop's call sequence, identical in every
gameplay frame of the recording (docs/aladdin/semantic-map.md section 1).  Each
step names its entry in the original (for the verification path, which
brackets the original between ``entry`` and ``exits``) and, when
recovered, the semantic callable that owns it natively.  Unrecovered
steps are gaps: native execution stops there, loudly.
"""
from __future__ import annotations
from dataclasses import dataclass
from .state import GameState, NativeGap
from . import sequences
from ..game.objects.script_engine import Engine, Services, Trace
from ..game import pad, hud, player, video, scroll, level, spawn, pause, camera, tiles, control, flow, sprites, messages
from ..game.objects import ground, contact_scan, contacts  # noqa: F401  (contacts registers the callbacks)


@dataclass(frozen=True)
class Step:
    name: str
    entry: int
    exits: tuple = ()
    run: object = None          # callable(state, services) or None when not recovered
    note: str = ''
    ports: bool = False         # the step writes the VDP ports: verification traces them in the oracle


class NativeServices(Services):
    """Records the platform-facing event stream on the game state."""
    def __init__(self, state: GameState):
        super().__init__(Trace())
        self.state = state
        state.on_vblank = _vblank_boundary
        self.waits = 0
        self.checkpoints = None   # the verification tools collect (pc, ram, frame) here when set

    def checkpoint(self, pc):
        """A sequence reached the point the original reaches at ``pc``: a progress marker for the platform.

        The game does nothing with it.  A replay clock (``state.replay``) lines the recorded input up with
        the original's work time here; the verification tools compare RAM here.
        """
        state = self.state
        if state.replay is not None:
            state.replay.checkpoint(pc)
        if self.checkpoints is not None:
            self.checkpoints.append((pc, bytes(state.ram), state.frame))

    def work(self):
        """The original spends at least one frame of work here (a decompression, the screen draw): its VBlank
        handler runs meanwhile.  The native runtime spends no time, so the handler's effects run once; with
        the pad unchanged they are the same however many frames the work took.
        """
        if self.state.on_vblank is not None:
            self.state.on_vblank(self.state)

    def palette_line(self, index, source):
        video.load_palette(self.state.write, self.state.rom, self.state.vdp, index, source)

    def sound_driver_init(self, tables):
        """1E584A at power-on: the sound driver receives its four data tables (a platform event)."""
        self.state.events.append(('sound_driver_init', self.state.frame, tuple(tables)))

    def pal(self):
        """The console's video mode (the VDP status bit the game reads at 1AA3B2): the recordings are NTSC."""
        return False

    def sound_flush(self, value):
        """1E589A on its own: the driver's flush command with a value (the level music)."""
        self.state.events.append(('sound_flush', self.state.frame, value))

    def sound(self, slot, sound_id, flush=True):
        self.state.events.append(('sound', self.state.frame, sound_id, flush))

    def vblank(self):
        """A nested VBlank wait inside a step (1B249E from a callback or a sequence): one recorded frame passes."""
        self.waits += 1
        self.state.advance_frames(1)            # the handler's effects run inside (state.on_vblank)

    def show_message(self, code):
        try:
            messages.show(self.state.read, self.state.write, self.state.rom, self.state.vdp, self.state.memory(), self, code)
        except messages.MessageGap as gap:
            raise NativeGap('message', 0x1B2238, str(gap), self.state.frame) from None

    def spawned(self, flag, record, kind):
        self.state.events.append(('spawn', self.state.frame, flag, (record - 0xFF7E40) // 66, kind))

    def sound_command(self, code):
        self.state.events.append(('sound_command', self.state.frame, code))

    def frame_changed(self, slot, descriptor):
        self.state.events.append(('frame_upload', self.state.frame, slot, descriptor))

    def handoff(self, kind, slot, detail=()):
        raise NativeGap(f'engine service {kind}', 0, f'slot {slot} {detail}', self.state.frame)


def _attract_end(name, entry):
    """A button ended the attract demo, or its recorded input ran out: 1B3182 exits to the title entry."""
    def step(state: GameState, services):
        resume = sequences.run_transition(state, services, 'attract_end')
        if resume is not None:
            raise ResumeFrame(resume)
    step.__name__ = name
    return step


def pad_read(state: GameState, services):
    if pad.read_pad(state.read, state.write, state.buttons, state.buttons_low):
        _attract_end('pad_read', 0x1A8CEE)(state, services)


def attract_input(state: GameState, services):
    if not pad.attract_input(state.read, state.write, state.rom):
        _attract_end('attract_input', 0x1B315C)(state, services)


def vram_upload_flush(state: GameState, services):
    video.flush_upload_queue(state.read, state.write, state.vdp)


def sprite_table_upload(state: GameState, services):
    video.upload_sprite_table(state.read, state.rom, state.vdp)


def tile_stream(state: GameState, services):
    video.stream_tiles(state.read, state.write, state.rom, state.vdp)


def camera_scroll_and_spawn_strips(state: GameState, services):
    try:
        scroll.run(state.read, state.write, state.rom, state.vdp, services)
    except LookupError as error:
        raise NativeGap('camera_scroll_and_spawn_strips', 0x1AAA80, str(error), state.frame) from None

    def walk(row, far):
        try:
            spawn.walk_strip(state.read, state.write, state.rom, state.vdp, services, row=row, far=far)
        except spawn.SpawnGap as error:
            raise NativeGap('camera_scroll_and_spawn_strips', 0x1AE44A, str(error), state.frame) from None
    level.draw_pending_strips(state.read, state.write, state.rom, state.vdp, walk)


def pause_check(state: GameState, services):
    if pause.pause_requested(state.read, state.write):
        sequences.run_transition(state, services, 'pause')     # 1A91E4: the loop inside the step; resumes at 1A8E0C


def player_wall_collision(state: GameState, services):
    player.wall_sensors(state.read, state.write)


def player_ground_collision(state: GameState, services):
    player.ground_collision(state.read, state.write, state.rom)


def player_vertical_input(state: GameState, services):
    player.vertical_input(state.read, state.write, state.rom)


def player_attack_input(state: GameState, services):
    player.attack_input(state.read, state.write, state.rom)


def object_level_collision(state: GameState, services):
    ground.object_level_collision(state.read, state.write, state.rom, services, state.memory())


def player_contact_scan(state: GameState, services):
    try:
        contact_scan.player_contact_scan(state.read, state.write, state.rom, services, state.memory(), state.bus_read)
    except contact_scan.ContactGap as gap:
        raise NativeGap('contact_scan', gap.target, str(gap), state.frame) from None
    except contacts.ContactFrameGap as gap:
        raise NativeGap('contact_scan', 0x1ABC9E, str(gap), state.frame) from None


def projectile_contact_scan(state: GameState, services):
    try:
        contact_scan.projectile_contact_scan(state.read, state.write, state.rom, services, state.memory(), state.bus_read)
    except contact_scan.ContactGap as gap:
        raise NativeGap('projectile_contact_scan', gap.target, str(gap), state.frame) from None


def camera_follow(state: GameState, services):
    camera.follow(state.read, state.write, state.rom)


def special_tile(state: GameState, services):
    try:
        tiles.special_tile(state.read, state.write, state.rom, services, state.memory())
    except tiles.TileGap as gap:
        raise NativeGap('special_tile', gap.target, str(gap), state.frame) from None


def _control(name, entry):
    def step(state: GameState, services):
        try:
            getattr(control, name)(state.read, state.write, services)
        except LookupError as error:
            raise NativeGap(name, entry, str(error), state.frame) from None
    step.__name__ = name
    return step


def hud_health(state: GameState, services):
    hud.health_display(state.read, state.write)


def token_counter(state: GameState, services):
    hud.token_counter(state.read, state.write, lambda sound_id: services.sound(0, sound_id), lambda code: None)   # 1B2236 is an RTS


def _flow(name, entry):
    def step(state: GameState, services):
        try:
            if name == 'level_tick':
                flow.level_tick(state.read, state.write, state.rom, services, state.vdp)
            else:
                getattr(flow, name)(state.read, state.write)
        except flow.Transition as transition:
            if transition.kind in ('fell', 'life_lost', 'level_change'):
                resume = sequences.run_transition(state, services, transition.kind)
                if resume is not None:
                    raise ResumeFrame(resume)
            else:
                raise NativeGap(name, entry, str(transition), state.frame) from None
    step.__name__ = name
    return step


def sprite_table(state: GameState, services):
    sprites.build_sprite_table(state.read, state.write, state.rom, state.bus_read)


def _vblank_boundary(state: GameState):
    """The VBlank handler 1B246E: the flag the wait spins on, and the any-button latch."""
    state.write(0xFF7E1E, 0xFF, 1)
    if state.read(0xFF7E23, 1) and any(f(state.read) for f in (pad.button_start, pad.button_a, pad.button_b, pad.button_c)):
        state.write(0xFF7E22, 0xFF, 1)


def wait_vblank(state: GameState, services):
    """1B249E: the frame boundary (the VBlank the loop waits for is the one run_frame's advance passes)."""
    if state.read(pause.PAUSE_INHIBITED, 1):
        raise NativeGap('wait_vblank', 0x1B24AC, 'the Start-release wait is not recovered', state.frame)


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
    # the original main loop (1A8C16..1A8CEE) in call order, one frame starting after the VBlank wait;
    # every step's exit is the next call's entry, so a step is bracketed by the main loop itself
    Step('vram_upload_flush', 0x1AC726, (0x1AB776, 0x1AC782), vram_upload_flush, 'recovered: game.video.flush_upload_queue', ports=True),
    Step('sprite_table_upload', 0x1AB776, (0x1AE0F6, 0x1AB7A0, 0x1AB7A2), sprite_table_upload, 'recovered: game.video.upload_sprite_table', ports=True),
    Step('tile_stream', 0x1AE0F6, (0x1AAA2A, 0x1AE19E), tile_stream, 'recovered: game.video.stream_tiles', ports=True),
    Step('camera_scroll_and_spawn_strips', 0x1AAA2A, (0x1B315C, 0x1AAA7E), camera_scroll_and_spawn_strips,
         'recovered: game.scroll (per-level parallax), game.level (map strips), game.spawn (spawn sites)', ports=True),
    Step('attract_input', 0x1B315C, (0x1A8CEE,), attract_input, 'recovered: game.pad.attract_input (the demo pad stream)'),
    Step('pad_read', 0x1A8CEE, (0x1A8C16,), pad_read, 'recovered: game.pad.read_pad'),
    Step('frame_counter', 0x1A8C16, (0x1A91C6,), frame_counter, 'recovered: game.player.advance_frame_counter'),
    Step('pause_check', 0x1A91C6, (0x1A8E0C,), pause_check, 'recovered: game.pause.pause_requested, sequences.pause_loop'),
    Step('publish_player_position', 0x1A8E0C, (0x1AD7B4, 0x1AD632, 0x1AA8FA, 0x1A8E3E), publish_player_position,
         'recovered: game.player.publish_position'),
    Step('player_ground_collision', 0x1AD7B4, (0x1A8E0C,), player_ground_collision, 'recovered: game.player.ground_collision'),
    Step('publish_player_position', 0x1A8E0C, (0x1AD7B4, 0x1AD632, 0x1AA8FA, 0x1A8E3E), publish_player_position,
         'recovered: game.player.publish_position'),
    Step('player_wall_collision', 0x1AD632, (0x1A986E,), player_wall_collision, 'recovered: game.player.wall_sensors'),
    Step('player_vertical_input', 0x1A986E, (0x1A99F0,), player_vertical_input, 'recovered: game.player.vertical_input'),
    Step('player_attack_input', 0x1A99F0, (0x1ADE36,), player_attack_input, 'recovered: game.player.attack_input'),
    Step('object_motion', 0x1ADE36, (0x1ADB5C,), motion_pass, 'recovered: game.objects.script_engine.Engine.motion_pass'),
    Step('object_level_collision', 0x1ADB5C, (0x1ABB40,), object_level_collision, 'recovered: game.objects.ground'),
    Step('contact_scan', 0x1ABB40, (0x1A8C44,), player_contact_scan,
         'recovered: game.objects.contact_scan (callbacks are registered per kind as they are recovered)'),
    Step('pad_decode', 0x1A8C44, (0x1B1E38,), pad_decode, 'recovered: game.pad.decode_directions'),
    Step('special_tile', 0x1B1E38, (0x1A9D98,), special_tile, 'recovered: game.tiles (handlers by collision class)'),
    Step('player_horizontal_control', 0x1A9D98, (0x1A9716,), _control('horizontal_control', 0x1A9D98),
         'recovered: game.control.horizontal_control'),
    Step('jump_start', 0x1A9716, (0x1A8E0C,), _control('jump_start', 0x1A9716), 'recovered: game.control.jump_start'),
    Step('publish_player_position', 0x1A8E0C, (0x1AD7B4, 0x1AD632, 0x1AA8FA, 0x1A8E3E), publish_player_position,
         'recovered: game.player.publish_position'),
    Step('camera_follow', 0x1AA8FA, (0x1A9304,), camera_follow, 'recovered: game.camera.follow'),
    Step('throw_input', 0x1A9304, (0x1A9502,), _control('throw_input', 0x1A9304), 'recovered: game.control.throw_input'),
    Step('sword_input', 0x1A9502, (0x1ABD7E,), _control('sword_input', 0x1A9502), 'recovered: game.control.sword_input'),
    Step('projectile_contact_scan', 0x1ABD7E, (0x1B02EC,), projectile_contact_scan,
         'recovered: game.objects.contact_scan (callbacks per struck kind)'),
    Step('hud_health', 0x1B02EC, (0x1A8F0C,), hud_health, 'recovered: game.hud.health_display'),
    Step('fall_check', 0x1A8F0C, (0x1A8F04,), _flow('fall_check', 0x1A8F0C), 'recovered: game.flow.fall_check (the life-lost sequence is a gap)'),
    Step('level_tick', 0x1A8F04, (0x1B00CA,), _flow('level_tick', 0x1A8F04), 'recovered: game.flow.level_tick (per-level routines)'),
    Step('score_tally', 0x1B00CA, (0x1B01AC,), score_tally, 'recovered: game.hud.score_tally'),
    Step('token_counter', 0x1B01AC, (0x1A8E0C,), token_counter, 'recovered: game.hud.token_counter (the message overlay is a gap)'),
    Step('publish_player_position', 0x1A8E0C, (0x1AD7B4, 0x1AD632, 0x1AA8FA, 0x1A8E3E), publish_player_position,
         'recovered: game.player.publish_position'),
    Step('transition_countdown', 0x1A8E3E, (0x1AC784,), _flow('transition_countdown', 0x1A8E3E),
         'recovered: game.flow.transition_countdown (the level change is a gap)'),
    Step('object_animation', 0x1AC784, (0x1AB7C4,), animation_pass, 'recovered: game.objects.script_engine.Engine.animation_pass'),
    Step('sprite_table', 0x1AB7C4, (0x1B249E, 0x1ABB3E), sprite_table, 'recovered: game.sprites.build_sprite_table'),
    Step('wait_vblank', 0x1B249E, (0x1AC726, 0x1B24F4), wait_vblank, 'recovered: the frame boundary (VBlank handler 1B246E)'),
)


class ResumeFrame(Exception):
    """A sequence re-entered the main loop at ``step`` (the level prologue ends at 1A8C16, not where it left)."""
    def __init__(self, step):
        super().__init__(step)
        self.step = step


def run_frame(state: GameState, buttons: int | None = None, start_step: str | None = None) -> None:
    """Execute one native frame; raise NativeGap at the first step that is not recovered.

    The pad comes from ``state.pads`` (the recorded masks by VBlank frame) when set, else ``buttons``.
    ``start_step`` enters the loop at that step (the boot and the prologues end at 1A8C16, the frame counter).
    """
    # a frame entered at a later step (the boot, a prologue) has no controller read: the mask stands
    sampled = state.replay.sample_input() if state.replay is not None and start_step is None else None
    if sampled is not None:
        state.buttons, state.buttons_low = sampled[0], sampled[1]
    else:
        state.buttons = state.pads(state.frame) if state.pads is not None else (buttons or 0)
        state.buttons_low = None
    services = NativeServices(state)
    index = next(i for i, s in enumerate(STEPS) if s.name == start_step) if start_step else 0
    while index < len(STEPS):
        step = STEPS[index]
        if step.run is None:
            raise NativeGap(step.name, step.entry, step.note or 'not recovered', state.frame)
        try:
            step.run(state, services)
        except ResumeFrame as resume:
            index = next(i for i, s in enumerate(STEPS) if s.name == resume.step)
            continue
        index += 1
    state.advance_frames(1)
