"""Drive the replay through the native runtime, or verify each recovered step against the oracle.

  native_replay.py --native  FRAME [COUNT]   seed from artifacts/evidence/frames/fFRAME.state and run natively;
                                             stops with a NativeGap report at the first unrecovered step
  native_replay.py --verify  FRAME [COUNT]   the oracle runs the frames; at every recovered step the semantic
                                             component runs over a copy of the oracle's state and is compared

The verify mode is the recovery loop: an unrecovered step is listed by
name and entry address in main-loop order; a recovered step is proven or
its mismatching fields are named.
"""
import os, sys, collections
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
os.environ.setdefault('ALADDIN_NATIVE_LIBRARY', str(root / 'build' / 'libaladdin_native.dll'))
from aladdin_sega.profile import read_rom
from aladdin_sega.machine import Machine
from aladdin_sega.native import GameState, NativeGap, STEPS, run_frame
from aladdin_sega.native.replay import ReplayClock, ReplayMismatch
from aladdin_sega.native.frame import NativeServices
from aladdin_sega.native.oracle import trace_port_writes, run_to_exits
from aladdin_sega.game.objects.record import RECORD_TABLE, FIELDS
from aladdin_sega.history import HistoryStore
FRAME_TICKS = 896040
VBLANK_HANDLER = 0x1B246E
FRAME_BOUNDARY = 0x1AC726        # the first main-loop call after the VBlank wait
MAIN_LOOP_RETURN = 0x1A8CDC      # ... as called from the main loop (1A8CD8); the sequences call it from elsewhere


def run_with_pads(m, pads, target):
    """Run the oracle toward tick ``target`` or the next armed gate, applying the recorded input as the recording's
    runtime does: the mask for the frame interval [f, f+1) is set at tick f * FRAME_TICKS (history_runtime.step).

    Returns 'gate' (the oracle parked on a gate) or 'limit' (the target tick reached).
    """
    while True:
        wrap = (m.info['tick'] // FRAME_TICKS + 1) * FRAME_TICKS
        if m.run(target=min(wrap, target)) == 'gate':
            return 'gate'
        if m.info['tick'] >= target:
            return 'limit'
        m.pad(pads.get(m.info['tick'] // FRAME_TICKS, 0))


def arm(m, pcs):
    """Gate ``pcs``; when the oracle already stands on one of them, let it leave before gating again."""
    m.gates(list(pcs))
    if m.info['pc'] in pcs:
        m.gate(m.info['pc'], bypass_once=True)


def seed_at_boundary(m, frame, pads, rom, patience=3):
    """Run the oracle from a snapshot to the next main-loop frame boundary and seed a native state there.

    ``patience`` is the number of frames the oracle may run without reaching a gate (a cold boot passes
    the title and attract screens first, with their own VBlank handling).
    """
    arm(m, [FRAME_BOUNDARY])
    m.pad(pads.get(m.info['tick'] // FRAME_TICKS, 0))
    while True:
        assert run_with_pads(m, pads, m.info['tick'] + patience * FRAME_TICKS) == 'gate', 'no frame boundary after the snapshot'
        m.gate(m.info['pc'], bypass_once=True)
        if at_main_loop_boundary(m):
            break
    frame = m.info['tick'] // FRAME_TICKS
    state = GameState.from_machine(m, frame, rom)
    state.pads = lambda f: pads.get(f, 0)
    state.replay = OracleClock(state, m, pads)
    return state, frame


TRANSITION_ENTRIES = {'life_lost': 0x1A8F82, 'fell': 0x1A902E}
TRANSITION_LIMIT = 4000 * FRAME_TICKS      # the continue screen and a level's prologue are under this
PAD_READS = ((0x1A8DB8, 0x1A8DF4), (0x1A8D22, 0x1A8D68))   # the main loop's two controller port reads (1A8CEE), and attract mode's


class OracleClock(ReplayClock):
    """The replay clock answered by the oracle running alongside: the original's frame at each checkpoint.

    The oracle sits at the main-loop boundary of the frame the native runtime is executing.  When the
    native frame raises a transition, ``begin`` drives the oracle to the transition's entry inside that
    frame; every ``checkpoint(pc)`` drives it to ``pc`` and moves the native frame counter to the
    oracle's VBlank count there; ``end`` drives it to its main loop's next boundary.  ``consumed`` then
    tells the frame driver that the oracle already stands at the next boundary.
    """

    def __init__(self, state, m, pads):
        self.state, self.m, self.pads = state, m, pads
        self.frame = None          # the oracle's VBlank count (the native frame number it corresponds to)
        self.consumed = False

    def _run_to(self, targets, limit, main_loop=False):
        m = self.m
        arm(m, [VBLANK_HANDLER, *targets])
        while True:
            if run_with_pads(m, self.pads, limit) != 'gate':
                return None
            here = m.info['pc']
            m.gate(here, bypass_once=True)
            if here == VBLANK_HANDLER:
                self.frame += 1; continue
            if main_loop and not at_main_loop_boundary(m):
                continue
            return here

    def sample_input(self):
        """The mask the original's controller read sees in this frame: the oracle is run to that read.

        The recorded mask changes at the frame's tick wrap and the emulated controller shows it at once; the
        main loop's read falls before or after the wrap depending on the work before it, which the native
        runtime does not time.  The oracle decides, and then stands mid-frame; the frame driver runs it on.
        A standalone game reads its live controller and has no such question.
        """
        m = self.m
        masks = []
        for reads in zip(*PAD_READS):           # the first port read of either path, then the second
            arm(m, list(reads))
            if run_with_pads(m, self.pads, m.info['tick'] + 3 * FRAME_TICKS) != 'gate':
                raise ReplayMismatch('pad_read', reads[0], 'the original did not read the controller in the frame',
                                     self.state.frame)
            m.gate(m.info['pc'], bypass_once=True)
            masks.append(self.pads.get(m.info['tick'] // FRAME_TICKS, 0))
        return tuple(masks)

    def begin(self, kind):
        state = self.state
        self.frame = state.frame
        entry = TRANSITION_ENTRIES.get(kind)
        if entry is None:
            raise ReplayMismatch(kind, 0, f'the replay clock knows no entry for a {kind!r} transition', state.frame)
        if self._run_to((entry,), self.m.info['tick'] + 3 * FRAME_TICKS) is None:
            raise ReplayMismatch(kind, entry, 'the original did not start this transition in the frame', state.frame)
        self.consumed = True
        self._align(entry)

    def _align(self, pc):
        state = self.state
        if state.frame > self.frame:
            raise ReplayMismatch('checkpoint', pc, f'the sequence reached this point in frame {state.frame}, '
                                                   f'the original in frame {self.frame}', state.frame)
        state.advance_frames(self.frame - state.frame)

    def checkpoint(self, pc):
        if self._run_to((pc,), self.m.info['tick'] + TRANSITION_LIMIT) is None:
            raise ReplayMismatch('checkpoint', pc, f'the original did not reach {pc:06X} next', self.state.frame)
        self._align(pc)

    def end(self):
        state = self.state
        if self._run_to((FRAME_BOUNDARY,), self.m.info['tick'] + TRANSITION_LIMIT, main_loop=True) is None:
            raise ReplayMismatch('resume', 0, 'the original did not resume its main loop', state.frame)
        if state.frame >= self.frame:
            raise ReplayMismatch('resume', 0, f'the sequence waited to frame {state.frame}, the original resumed '
                                              f'its loop at frame {self.frame}', state.frame)
        state.advance_frames(self.frame - 1 - state.frame)   # the frame loop counts the resumed frame's own VBlank


WAIT_RETURN = 0x1B24F4                      # the RTS of the VBlank wait 1B249E: the game has passed one of its frames
SOUND_REQUEST, SOUND_FLUSH, SOUND_COMMAND = 0x1E58B8, 0x1E589A, 0x1E58F4


class OracleDriver:
    """Runs the oracle frame by frame beside the native runtime, under one of two input contracts.

    *Faithful* (the default): the recorded mask changes at the frame's tick wrap, as the recording runtime
    applied it; with a replay clock this is the aligned mode.  *By waits* (the independent contract): the mask
    for game frame W is applied when the game returns from its W-th VBlank wait, so input advances with the
    game's own frames and never with work time; the native runtime under the same contract needs no oracle.
    Either way the driver collects the sound driver's calls per frame for comparison with the native events.
    """

    def __init__(self, m, pads, by_waits=False, frame=0):
        self.m, self.pads, self.by_waits = m, pads, by_waits
        self.waits = frame              # the game frames passed so far (the native frame number)
        self.sounds = []                # this frame's ('request', id) / ('flush', value) / ('command',) events

    def run_frame(self, clock=None):
        """To the next main-loop boundary; nothing when the frame's transition already drove the oracle there."""
        m = self.m
        self.sounds = []
        if clock is not None and clock.consumed:
            clock.consumed = False
            return
        gates = [FRAME_BOUNDARY, SOUND_REQUEST, SOUND_FLUSH, SOUND_COMMAND] + ([WAIT_RETURN] if self.by_waits else [])
        arm(m, gates)
        limit = m.info['tick'] + (TRANSITION_LIMIT if self.by_waits else 3 * FRAME_TICKS)
        while True:
            if self.by_waits:
                result = 'gate' if m.run(target=limit) == 'gate' else 'limit'
            else:
                result = run_with_pads(m, self.pads, limit)
            assert result == 'gate', 'the oracle did not reach the frame boundary'
            pc = m.info['pc']
            m.gate(pc, bypass_once=True)
            if pc == WAIT_RETURN:
                self.waits += 1
                m.pad(self.pads.get(self.waits, 0))
            elif pc == SOUND_REQUEST:
                self.sounds.append(('request', self._argument()))
            elif pc == SOUND_FLUSH:
                self.sounds.append(('flush', self._argument()))
            elif pc == SOUND_COMMAND:
                self.sounds.append(('command',))
            elif at_main_loop_boundary(m):
                return

    def _argument(self):
        sp = self.m.registers()['a7']
        return int.from_bytes(self.m.peek_ram((sp + 4) & 0xFFFF, 4), 'big') & 0xFFFF


def native_sound_events(events, frame):
    """The native event stream of one frame in the driver's terms."""
    out = []
    for e in events:
        if e[1] != frame:
            continue
        if e[0] == 'sound':
            out.append(('request', e[2]))
            if e[3]:
                out.append(('flush', e[2]))
        elif e[0] == 'sound_flush':
            out.append(('flush', e[2]))
        elif e[0] == 'sound_command':
            out.append(('command',))
    return out


def run_oracle_frame(m, pads, clock=None):
    """Run the oracle to its next frame boundary under the faithful input contract (see OracleDriver)."""
    if clock is not None and clock.consumed:
        clock.consumed = False
        return
    _run_oracle_frame(m, pads)


def seed_cold(m, pads, rom):
    """A native state at the first main-loop boundary of a cold start (boot, title and attract are the oracle's)."""
    return seed_at_boundary(m, 0, pads, rom, patience=20000)


def _run_oracle_frame(m, pads):
    arm(m, [FRAME_BOUNDARY])
    while True:
        assert run_with_pads(m, pads, m.info['tick'] + 3 * FRAME_TICKS) == 'gate', 'the oracle did not reach the frame boundary'
        m.gate(m.info['pc'], bypass_once=True)
        if at_main_loop_boundary(m):
            return


def _run_oracle_frame_by_interrupts(m, pads):
    """The former rule (the mask applied at the VBlank interrupt); kept for reference, unused."""
    while True:
        assert m.run(target=m.info['tick'] + 3 * FRAME_TICKS) == 'gate', 'the oracle did not reach the frame boundary'
        pc = m.info['pc']
        m.gate(pc, bypass_once=True)
        if pc == VBLANK_HANDLER:
            m.pad(pads.get(m.info['tick'] // FRAME_TICKS, 0))
            continue
        if pc == FRAME_BOUNDARY and at_main_loop_boundary(m):
            return


def at_main_loop_boundary(m):
    """At the FRAME_BOUNDARY gate: is this the main loop's own call (the mini frames of a transition call it too)?"""
    sp = m.registers()['a7']
    return int.from_bytes(m.peek_ram(sp & 0xFFFF, 4), 'big') == MAIN_LOOP_RETURN

BOOKKEEPING = ((0xFF769A, 0xFF7A00, 'DMA queue'), (0xFFED00, 0xFFEFDC, 'stack (the decompressors keep their tables 0x1B0 below it)'),
               (0xFF7D9A, 0xFF7DA3, 'continuations'), (0xFFEFEE, 0xFFEFF0, 'queue counters'))


def field_name(address):
    if RECORD_TABLE <= address < RECORD_TABLE + 32 * 66:
        slot, off = divmod(address - RECORD_TABLE, 66)
        for name, (o, size, _) in FIELDS.items():
            if o <= off < o + size:
                return f'slot{slot}.{name}'
        return f'slot{slot}+{off:02X}'
    return f'{address:06X}'


def history_id():
    """The recording the evidence snapshots were taken from (artifacts/evidence/frames/history_id), never 'main'."""
    path = root / 'artifacts' / 'evidence' / 'frames' / 'history_id'
    if not path.exists():
        sys.exit(f'no {path}: the evidence snapshots do not name their recording')
    return path.read_text().strip()


def masks(recording=None):
    """Recorded pad mask per frame (a recording's events, held until the next event); a node id or its prefix."""
    store = HistoryStore(str(root / 'history'))
    node = history_id() if recording is None else next(
        (n for n in store.nodes() if n.startswith(recording)), recording)
    path = store.flatten(store.resolve(node))
    out = {}; current = 0; events = sorted(path['events'], key=lambda e: e['frame'])
    i = 0
    for f in range(path['end_frame'] + 1):
        while i < len(events) and events[i]['frame'] <= f:
            current = events[i]['buttons']; i += 1
        out[f] = current
    return out


def load(frame):
    path = root / 'artifacts' / 'evidence' / 'frames' / f'f{frame}.state'
    if not path.exists():
        sys.exit(f'no snapshot {path}; run scripts/cartography/frame_states.py {frame}')
    return path.read_bytes()


def native(frame, count):
    """An independent run: after the seed the oracle is closed; time and input come from the frame clock alone.

    The native frame N reads the recorded mask pads(N); transitions spend no work time.  This is the standalone
    timing policy, not the recording's: the run is evidence of what the native game does on its own.
    """
    rom = read_rom()
    m = Machine(rom); m.audio_policy('discard'); m.restore(load(frame))
    pads = masks()
    state, frame = seed_at_boundary(m, frame, pads, rom); m.close()
    state.replay = None
    print(f'independent run from main-loop frame {frame}: no oracle after the seed')
    try:
        for _ in range(count):
            run_frame(state)
    except NativeGap as gap:
        done = [s.name for s in STEPS[:[s.name for s in STEPS].index(gap.step)]] if gap.step in [s.name for s in STEPS] else []
        print(f'NativeGap: frame {gap.frame}, step "{gap.step}" at {gap.pc:06X}: {gap.detail}')
        print(f'  steps executed natively this frame: {done}')
        print(f'  events so far: {len(state.events)}')
        return 1
    print(f'native replay completed {count} frames to frame {state.frame}; events {len(state.events)}')
    return 0


def verify(frame, count):
    rom = read_rom()
    m = Machine(rom); m.audio_policy('discard'); m.restore(load(frame))
    entries = {s.entry: s for s in STEPS}
    results = collections.Counter(); mismatches = collections.defaultdict(collections.Counter)
    m.gates(sorted({s.entry for s in STEPS if s.run is not None} | {e for s in STEPS if s.run for e in s.exits}))
    frames_done = 0; recovered_entries = {s.entry for s in STEPS if s.run is not None}
    tick_end = m.info['tick'] + count * FRAME_TICKS
    pads = masks(); padded = -1
    while m.info['tick'] < tick_end:
        current_frame = m.info['tick'] // FRAME_TICKS
        if current_frame != padded:
            m.pad(pads.get(current_frame, 0)); padded = current_frame
        if m.run(target=min(tick_end, (current_frame + 1) * FRAME_TICKS)) != 'gate':
            continue
        pc = m.info['pc']
        step = entries.get(pc)
        if step is None or step.run is None:
            m.gate(pc, bypass_once=True); continue
        before = bytearray(m.peek_ram(0, 65536))
        m.gate(pc, bypass_once=True)
        if step.ports:
            traced = trace_port_writes(m, step.exits)
        else:
            run_to_exits(m, step.exits, tick_end + 896040)
        after = m.peek_ram(0, 65536)
        state = GameState(bytearray(before), rom, current_frame); state.buttons = pads.get(current_frame, 0)
        try:
            step.run(state, NativeServices(state))
        except NativeGap as gap:
            results[f'{step.name}: gap {gap.step}'] += 1
            m.gate(m.info['pc'], bypass_once=True); continue
        bad = 0
        for a in range(65536):
            if after[a] != state.ram[a] and not any(lo <= 0xFF0000 | a < hi for lo, hi, _ in BOOKKEEPING):
                mismatches[step.name][field_name(0xFF0000 | a)] += 1; bad += 1
        if step.ports and state.vdp.log != traced:
            bad += 1
            first = next((i for i, (a, b) in enumerate(zip(state.vdp.log, traced)) if a != b), min(len(state.vdp.log), len(traced)))
            mismatches[step.name][f'ports: native {len(state.vdp.log)} vs oracle {len(traced)} words, first difference at {first}: '
                                  f'{state.vdp.log[first:first + 3]} vs {traced[first:first + 3]}'] += 1
        results[f'{step.name}: {"ok" if not bad else "mismatch"}'] += 1
        if entries.get(m.info['pc']) is None or entries[m.info['pc']].run is None:
            m.gate(m.info['pc'], bypass_once=True)      # an exit that is the next recovered step's entry is verified next
    m.close()
    print('verified passes:', dict(results))
    for name, fields in mismatches.items():
        print(' ', name, 'mismatching fields:', dict(fields.most_common(10)))
    print('unrecovered steps, in main-loop order:')
    for s in STEPS:
        if s.run is None:
            print(f'  {s.entry:06X} {s.name}  {s.note}')
    failures = sum(n for name, n in results.items() if not name.endswith(': ok'))
    verified = {name.split(':')[0] for name in results if name.endswith(': ok')}
    missing = [s.name for s in STEPS if s.run is not None and s.name not in verified]
    if missing:
        print('recovered steps NOT exercised in this window:', missing)
    return 2 if failures else (3 if missing else 0)


if __name__ == '__main__':
    mode, frame = sys.argv[1], int(sys.argv[2])
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    sys.exit(native(frame, count) if mode == '--native' else verify(frame, count))
