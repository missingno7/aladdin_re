"""Play the recovered game natively: power-on, the frame loop, live input, the native VDP rendered, no original CPU.

  play_native.py [--resume NODE] [--store DIR] [--scale N] [--replay NODE] [--frames N] [--headless] [--wav FILE] [--mute]

The game runs from native power-on (aladdin_sega.native.boot) through the
native frame loop with the keyboard as the controller (arrows, Z = A,
X = B, C = C, Return = Start; Escape or closing the window exits, F5
journals a checkpoint).  Every frame the VDP model's memories are rendered
(aladdin_sega.native.render) and shown; the game's sound driver calls go
to the ROM's Z80 driver on a dedicated machine (aladdin_sega.native
.sound_service) whose PCM is played (--mute: not), or written to --wav
FILE when headless.

Input is journaled as an immutable history in the native history store
(--store, default history_native; the same model as the original
recordings, with the game-frame clock: the mask for game frame W applies
when the game returns from its W-th VBlank wait).  At a NativeGap or at
exit the session becomes a node of that store, with a screenshot, the gap
(subsystem, address, detail, frame) and the source identity in
history_native/gaps/<node>.json, and a cache of the native state in
history_native/cache/<node>.pkl (acceleration only: deleting it and
replaying the history from power-on is always valid).

--resume NODE replays the node's history from power-on (or from its cache
when the source identity still matches) and then hands control to the
keyboard; a replay that raises a gap before the node's end is a regression
and is reported, never bypassed.  --replay NODE with --frames N runs
headless.
"""
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from aladdin_sega.profile import read_rom
from aladdin_sega.history import HistoryStore, NATIVE_ROOT
from aladdin_sega.native import boot, render, run_frame
from aladdin_sega.native.frame import NativeServices
from aladdin_sega.native.state import NativeGap

ROOT = Path(__file__).resolve().parents[1]
FRAME_SECONDS = 1 / 59.92
CACHE_EVERY = 600            # frames between boundary caches kept for a resume


def source_identity() -> str:
    """A digest of the recovered source: what a cache was made with."""
    h = hashlib.sha256()
    for path in sorted((ROOT / 'src' / 'aladdin_sega').rglob('*.py')):
        h.update(path.relative_to(ROOT).as_posix().encode()); h.update(path.read_bytes())
    return h.hexdigest()


class Journal:
    """The inputs of a native session as history events: (frame, buttons) whenever the mask changes."""

    def __init__(self, start_frame=0, buttons=0):
        self.events = []
        self.buttons = self.initial = buttons
        self.start_frame = start_frame

    def note(self, frame, buttons):
        """The mask the game read for ``frame``; a second read in the same frame replaces the first (one mask per
        game frame in a history), and a change back to the previous mask cancels the event."""
        if buttons == self.buttons or frame < self.start_frame:
            return
        if self.events and self.events[-1]['frame'] == frame:
            self.events.pop()
            self.buttons = self.events[-1]['buttons'] if self.events else self.initial
            if buttons == self.buttons:
                return
        self.events.append({'frame': frame, 'buttons': buttons})
        self.buttons = buttons


class Player:
    def __init__(self, store: HistoryStore, scale=3):
        import pygame
        self.pygame = pygame
        pygame.display.init(); pygame.font.init()
        self.scale = scale
        self.window = pygame.display.set_mode((320 * scale, 224 * scale))
        pygame.display.set_caption('Aladdin, recovered')
        self.font = pygame.font.Font(None, 20)
        self.keys = {pygame.K_UP: 1, pygame.K_DOWN: 2, pygame.K_LEFT: 4, pygame.K_RIGHT: 8,
                     pygame.K_x: 16, pygame.K_c: 32, pygame.K_z: 64, pygame.K_RETURN: 128}
        self.held = set()
        self.mask = 0
        self.running = True
        self.checkpoint_requested = False
        self.next_time = time.perf_counter()
        self.store = store
        self.last_image = None

    def poll(self):
        pg = self.pygame
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.WINDOWFOCUSLOST:
                self.held.clear()
            elif event.type in (pg.KEYDOWN, pg.KEYUP):
                if event.key in self.keys:
                    (self.held.add if event.type == pg.KEYDOWN else self.held.discard)(event.key)
                elif event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                    self.running = False
                elif event.type == pg.KEYDOWN and event.key == pg.K_F5:
                    self.checkpoint_requested = True
        self.mask = sum(self.keys[k] for k in self.held)

    def present(self, state, text=''):
        pg = self.pygame
        image = render.render(state.vdp)
        self.last_image = image
        surface = pg.surfarray.make_surface(image.transpose(1, 0, 2))
        surface = pg.transform.scale(surface, self.window.get_size())
        self.window.blit(surface, (0, 0))
        if text:
            self.window.blit(self.font.render(text, True, (255, 255, 255), (0, 0, 0)), (4, 4))
        pg.display.flip()
        self.next_time += FRAME_SECONDS
        delay = self.next_time - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        elif delay < -0.5:
            self.next_time = time.perf_counter()


class Sound:
    """The driver service fed the session's sound events, its PCM to the speakers or a WAV file."""

    def __init__(self, rom, wav=None, output=True):
        from aladdin_sega.native.sound_service import SoundDriver
        self.driver = SoundDriver(rom)
        self.seen = 0
        self.output = None
        self.wav = None
        if output:
            from aladdin_sega.audio import AudioOutput
            self.output = AudioOutput()
        if wav:
            import wave
            from aladdin_sega.audio import SAMPLE_RATE
            self.wav = wave.open(str(wav), 'wb'); self.wav.setnchannels(2); self.wav.setsampwidth(2); self.wav.setframerate(SAMPLE_RATE)

    def frame(self, state):
        events = state.events
        for e in events[self.seen:]:
            if e[0] in ('sound', 'sound_flush', 'sound_command'):
                self.driver.event(e)
        self.seen = len(events)
        pcm = self.driver.advance()
        if self.output is not None:
            self.output.push(pcm)
        if self.wav is not None:
            self.wav.writeframes(pcm)

    def close(self):
        if self.wav is not None:
            self.wav.close()
        if self.output is not None:
            self.output.close()
        self.driver.close()


class Session:
    """One native playthrough: power-on (or a resumed history), the journal, the presenter, the gap record."""

    def __init__(self, rom, store, player=None, sound=None):
        self.rom, self.store, self.player, self.sound = rom, store, player, sound
        self.state = boot.power_on(rom)
        self.journal = Journal()
        self.replay = None            # (events by frame, end_frame) while a history is being replayed
        self.parent = store.root_id
        self.gap = None
        self.boundary_cache = None    # the latest native state at a main-loop boundary (every CACHE_EVERY frames)
        self.resumed_from_cache = False
        self.state.pads = self.pad_for_frame
        self.state.on_frame = self.on_frame

    # -- the platform services the frame clock calls -------------------------------------------
    def pad_for_frame(self, frame):
        if self.replay is not None and frame < self.replay[1]:
            events, _ = self.replay
            mask = events.get(frame, self.journal.buttons)
        elif self.player is not None:
            mask = self.player.mask
        else:
            mask = self.journal.buttons
        self.journal.note(frame, mask)
        return mask

    def on_frame(self, state):
        if self.sound is not None:
            self.sound.frame(state)
        if self.replay is not None and state.frame < self.replay[1]:
            return                                    # replaying: no presentation, no pacing
        if self.replay is not None:
            self.replay = None
            print(f'history replayed to frame {state.frame}; the keyboard has the controller')
        if self.player is not None:
            self.player.poll()
            self.player.present(state, f'frame {state.frame}')
            if self.player.checkpoint_requested:
                self.player.checkpoint_requested = False
                node = self.journal_node('manual')
                print(f'checkpoint {node[:12]}')
            if not self.player.running:
                raise SessionExit()

    # -- running -------------------------------------------------------------------------------
    def snapshot(self):
        vdp = self.state.vdp
        return {'source': source_identity(), 'frame': self.state.frame, 'ram': bytes(self.state.ram),
                'vram': bytes(vdp.vram), 'cram': bytes(vdp.cram), 'vsram': bytes(vdp.vsram),
                'registers': list(vdp.registers), 'buttons': self.journal.buttons, 'events': len(self.state.events)}

    def run(self, frames=None):
        state = self.state
        start_step = 'frame_counter' if self.resumed_from_cache else None
        last_cache = state.frame
        try:
            if not self.resumed_from_cache:
                start_step = boot.start(state, NativeServices(state))
            while frames is None or state.frame < frames:
                run_frame(state, start_step=start_step)
                start_step = None
                if state.frame - last_cache >= CACHE_EVERY and (self.replay is None):
                    self.boundary_cache = self.snapshot(); last_cache = state.frame
        except NativeGap as gap:
            self.gap = gap
            print(f'NativeGap at {gap.step} ({gap.pc:06X}) frame {gap.frame}: {gap.detail}')
        except SessionExit:
            pass
        return self.gap

    # -- the immutable record ------------------------------------------------------------------
    def journal_node(self, reason, label=None):
        events = self.journal.events
        end_frame = max(self.state.frame, 1, (events[-1]['frame'] + 1) if events else 0)   # a history's events precede its end
        node = self.store.append(self.parent, list(events), end_frame)
        image = self.player.last_image if self.player is not None else render.render(self.state.vdp)
        self.store.present(node, rgb=image.tobytes(), width=320, height=224, reason=reason, label=label)
        # the session continues as a child of this node
        self.parent, self.journal = node, Journal(end_frame, self.journal.buttons)
        return node

    def record(self):
        """At a gap or exit: the node, its gap record and a cache of the native state."""
        gap = self.gap
        reason = 'native_gap' if gap else 'session_exit'
        label = f'{gap.step} {gap.pc:06X}' if gap else None
        node = self.journal_node(reason, label)
        record = {'node': node, 'end_frame': self.state.frame, 'source': source_identity(),
                  'gap': None if gap is None else {'step': gap.step, 'pc': f'{gap.pc:06X}', 'detail': gap.detail,
                                                   'frame': gap.frame},
                  'events': len(self.state.events)}
        gaps = self.store.path / 'gaps'; gaps.mkdir(exist_ok=True)
        (gaps / f'{node}.json').write_text(json.dumps(record, indent=2))
        if self.boundary_cache is not None:        # a state at a main-loop boundary before the gap, never inside it
            cache = self.store.path / 'cache'; cache.mkdir(exist_ok=True)
            with open(cache / f'{node}.pkl', 'wb') as f:
                pickle.dump(self.boundary_cache, f)
            where = 'cache at boundary frame %d' % self.boundary_cache['frame']
        else:
            where = 'no boundary cache (a resume replays from power-on)'
        print(f'{reason}: node {node} (end frame {self.state.frame}); record in {gaps.name}/; {where}')
        return node


class SessionExit(Exception):
    pass


def resume(session: Session, node: str):
    """Replay the node's history from power-on, or from its cache when the source identity matches."""
    store = session.store
    path = store.flatten(store.resolve(node))
    events = {e['frame']: e['buttons'] for e in path['events']}
    end_frame = path['end_frame']
    final_mask = path['events'][-1]['buttons'] if path['events'] else 0
    session.parent = node
    session.journal = Journal(end_frame, final_mask)
    session.replay = (events, end_frame)
    cache = store.path / 'cache' / f'{node}.pkl'
    if cache.exists():
        with open(cache, 'rb') as f:
            saved = pickle.load(f)
        if saved['source'] == source_identity():
            state = session.state
            state.ram[:] = saved['ram']
            state.vdp.vram[:] = saved['vram']; state.vdp.cram[:] = saved['cram']; state.vdp.vsram[:] = saved['vsram']
            state.vdp.registers[:] = saved['registers']
            state.frame = saved['frame']
            state.buttons = saved['buttons']
            session.resumed_from_cache = True
            print(f'resumed {node[:12]} from its boundary cache at frame {state.frame} (same source identity); '
                  f'replaying the history from there to frame {end_frame}')
            return
        print('the cache was made with other source: replaying the history from power-on')
    print(f'replaying {len(path["events"])} input changes to frame {end_frame} from power-on')


def main(argv):
    if '--help' in argv or '-h' in argv:
        print(__doc__); return 0
    flags = [a for a in argv if a in ('--headless', '--mute')]
    argv = [a for a in argv if a not in flags]
    args = dict(zip(argv[::2], argv[1::2])) if len(argv) % 2 == 0 else {}
    store = HistoryStore(Path(args.get('--store', 'history_native')), root=NATIVE_ROOT)
    rom = read_rom()
    headless = '--replay' in args or '--headless' in flags
    player = None if headless else Player(store, scale=int(args.get('--scale', 3)))
    sound = None
    if '--wav' in args or (not headless and '--mute' not in flags):
        sound = Sound(rom, wav=args.get('--wav'), output=not headless and '--mute' not in flags)
    session = Session(rom, store, player, sound)
    node = args.get('--resume') or args.get('--replay')
    if node:
        resume(session, node)
    frames = int(args['--frames']) if '--frames' in args else None
    session.run(frames)
    session.record()
    if sound is not None:
        sound.close()
    return 1 if session.gap else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
