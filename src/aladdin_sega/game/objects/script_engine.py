"""The object script engine as game semantics: one frame of animation and motion per object.

Recovered from 1AC784 (animation channel), 1ADE36 (motion channel and
velocity integration), the opcode handlers behind ROM table 4954, and the
player selector 1AD150.  The engine reads and writes object records and
a few global fields through :class:`Memory`, and reaches the rest of the
game through :class:`Services`; nothing here knows about registers, the
stack, or cycles.  Effects the engine cannot own in Python yet (native
calls, spawning through the allocators, VRAM uploads) are reported as
:class:`Handoff` so a caller can hand them to the original machine or to a
standalone implementation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .record import (RecordView, RECORD_TABLE, RECORD_SIZE, RECORD_COUNT, PLAYER_KIND)
from ..scripts import (decode_op, ANIMATION_OPCODE_BASE, MOTION_OPCODE_BASE, OPCODES)
from ..rng import advance_rng

# Global fields the engine touches (see docs/semantic-map.md)
PLAYER_X, PLAYER_Y = 0xFF7E02, 0xFF7E04
PLAYER_SCREEN_X, PLAYER_SCREEN_Y = 0xFF7DFA, 0xFF7DFC
CAMERA_X, CAMERA_Y = 0xFF7DF6, 0xFF7DF8
FRAME_COUNTER = 0xFF7E28
SOUND_ENABLED = 0xFFF57D
PREVIOUS_X, PREVIOUS_Y = 0xFFF090, 0xFFF092
SPAWN_BITMAP = 0xFFAE87
RNG_SEED = 0xFF7DEA
VRAM_SLOT_MAP = 0xFFF008          # 116 bytes, one per VRAM tile slot; FF = taken (1AD3E8 / 1AE372)
VRAM_SLOT_COUNT = 0x74
VRAM_SLOT_TABLE = 0x11F500        # ROM: slot index -> VRAM tile address

# Player animation scripts chosen by the selector (opcode F8 / 1AD150)
PLAYER_SCRIPTS = {
    'attack': 0x121964, 'special_115': 0x125E72, 'hang': 0x122336, 'special_tile': 0x12181A,
    'jump_table': 0x121828, 'd2': 0x121C62, 'push_left': 0x12231E, 'push_right': 0x122298,
    'ed': 0x121FA6, 'walk': 0x122006, 'idle': 0x121D9A, 'fall': 0x121AD8,
    'cutscene_walk': 0x121FD4, 'cutscene_idle': 0x121D5A, 'cutscene_fall': 0x121C28,
}


class Memory:
    """Byte-addressed access to the game's work RAM plus read-only ROM."""
    def __init__(self, read, write, rom: bytes):
        self.read, self.write, self.rom = read, write, rom

    def record(self, slot: int) -> RecordView:
        return RecordView(RECORD_TABLE + RECORD_SIZE * slot, self.read, self.write)

    def u8(self, a): return self.read(a, 1)
    def u16(self, a): return self.read(a, 2)
    def u32(self, a): return self.read(a, 4)


@dataclass
class Handoff:
    """An effect the engine does not implement itself."""
    kind: str             # 'native', 'spawn', 'destroy', 'frame_upload'
    slot: int
    detail: tuple = ()


@dataclass
class Trace:
    sounds: list = field(default_factory=list)      # (slot, id, flush)
    handoffs: list = field(default_factory=list)
    frames_changed: list = field(default_factory=list)


class Services:
    """What the engine asks of the rest of the game.  Override in a standalone game."""
    def __init__(self, trace: Trace | None = None):
        self.trace = trace or Trace()

    def sound(self, slot, sound_id, flush=True):
        self.trace.sounds.append((slot, sound_id, flush))

    def frame_changed(self, slot, descriptor):
        self.trace.frames_changed.append((slot, descriptor))
        self.trace.handoffs.append(Handoff('frame_upload', slot, (descriptor,)))

    def handoff(self, kind, slot, detail=()):
        self.trace.handoffs.append(Handoff(kind, slot, detail))
        return False    # not handled here


class Stop(Exception):
    """End this record's processing for the frame (the handlers' FF7D9A/FF7D9E returns)."""


def _resolve(mem: Memory, obj: RecordView, where):
    kind, value = where
    return obj.base + value if kind == 'record' else value


def _channel_fields(motion: bool):
    return (('motion_delay', 'motion_loop', 'motion_count', 'motion_script') if motion
            else ('delay', 'loop', 'loop_count', 'script'))


class Engine:
    def __init__(self, mem: Memory, services: Services | None = None):
        self.mem = mem
        self.services = services or Services()
        self.rom = mem.rom

    # ---- opcode execution shared by both channels --------------------------------
    def run_ops(self, obj: RecordView, pc: int, *, motion: bool) -> int:
        """Execute opcodes at ``pc`` until a frame word (animation) or a data pair (motion)."""
        base = MOTION_OPCODE_BASE if motion else ANIMATION_OPCODE_BASE
        hi = base + len(OPCODES)
        while True:
            head = self.rom[pc]
            if not (base <= head < hi):
                return pc
            op = decode_op(self.rom, pc, head - base)
            pc = self.execute(obj, op, pc + op.size, motion=motion)

    def execute(self, obj: RecordView, op, next_pc: int, *, motion: bool) -> int:
        mem, rom, name, args = self.mem, self.rom, op.name, op.operands
        delay, loop, count, script = _channel_fields(motion)
        if name == 'jump':
            return args[0]
        if name == 'flip':
            if args[0] == 0:
                obj.facing ^= 0xFF
            else:
                obj.flip ^= 0xFF
            return next_pc
        if name == 'end':
            if args[0] == 0:
                obj.motion_script = 0
            else:
                obj.script = 0
            raise Stop()
        if name == 'set':
            size, where, value = args
            mem.write(_resolve(mem, obj, where), value, size)
            return next_pc
        if name == 'add':
            size, where, value = args
            a = _resolve(mem, obj, where)
            mem.write(a, (mem.read(a, size) + value) & ((1 << (8 * size)) - 1), size)
            return next_pc
        if name == 'wait':
            n = args[0]
            if n & 0x80:
                setattr(obj, delay, n & 0x7F)
                setattr(obj, script, next_pc)
                raise Stop()
            setattr(obj, count, n)
            setattr(obj, loop, next_pc)
            return next_pc
        if name == 'loop':
            if getattr(obj, count):
                setattr(obj, count, getattr(obj, count) - 1)
                return getattr(obj, loop)
            return next_pc
        if name == 'random_jump':
            seed = mem.u32(RNG_SEED)
            new_seed, value = advance_rng(seed)
            mem.write(RNG_SEED, new_seed, 4)
            return args[1] if (value & 0xFF) < args[0] else next_pc
        if name == 'move':
            axis, amount = args
            if axis == 0:
                obj.x = obj.x + (-amount if obj.facing else amount)
            else:
                obj.y = obj.y + (-amount if obj.flip else amount)
            return next_pc
        if name == 'branch_bit':
            bit, where, sense, target = args
            value = mem.u8(_resolve(mem, obj, where))
            taken = bool(value & (1 << bit)) == (sense == 'set')
            return target if taken else next_pc
        if name == 'sound':
            sound_id = args[0]
            if mem.u8(SOUND_ENABLED):
                self.services.sound(obj.slot, sound_id & 0x7F, flush=not (sound_id & 0x80))
            return next_pc
        if name == 'branch_compare':
            size, where, cmp, imm, target = args
            value = mem.read(_resolve(mem, obj, where), size)
            taken = {'imm<mem': imm < value, 'eq': imm == value, 'ne': imm != value,
                     'imm>=mem': imm >= value}.get(cmp, False)
            return target if taken else next_pc
        if name == 'face_player':
            obj.facing = 0xFF if mem.u16(PLAYER_X) < obj.x else 0
            return next_pc
        if name == 'near_x':
            d = abs(mem.u16(PLAYER_X) - obj.x)
            limit = 0x140 if args[0] == 0xFF else args[0]
            return args[1] if d <= limit else next_pc
        if name == 'near_y':
            d = abs(mem.u16(PLAYER_Y) - obj.y)
            return args[1] if d <= args[0] else next_pc
        if name == 'home':
            speed, ywin, xwin = args
            py, px = mem.u16(PLAYER_Y), mem.u16(PLAYER_X)
            vy = speed if (obj.y - ywin) & 0xFFFF < py else -speed
            obj.vel_y = _add_byte_to_word(obj.vel_y, vy)
            vx = speed if (obj.x - xwin) & 0xFFFF < px else -speed
            obj.vel_x = _add_byte_to_word(obj.vel_x, vx)
            return next_pc
        if name == 'resume':
            if args[0] & 0x80:
                return obj.saved_script
            return next_pc
        if name == 'player_select':
            return self.player_select(obj)
        if name == 'destroy':
            self.destroy(obj, args[0])
            raise Stop()
        if name == 'spawn':
            self.services.handoff('spawn', obj.slot, args)
            return next_pc          # the original continues after the 15 operand bytes either way
        if name == 'call_native':
            self.services.handoff('native', obj.slot, (args[0],))
            raise Stop()
        raise ValueError(name)

    # ---- record lifetime: VRAM slots, retirement, despawn ----------------------------
    def release(self, obj: RecordView) -> None:
        """1AE372: free the object's VRAM tile slots."""
        map_address = obj.vram_map
        if not map_address:
            return
        obj.vram_map = 0; obj.vram = 0
        count = obj.vram_slots; obj.vram_slots = 0
        for i in range(count + 1):
            self.mem.write(map_address + i, 0, 1)

    def retire(self, obj: RecordView) -> None:
        """1ABE6E: deactivate the record (and its rider) and free their VRAM slots."""
        obj.kind = 0
        self.release(obj)
        if obj.rider:
            rider = RecordView(obj.rider, self.mem.read, self.mem.write)
            rider.kind = 0
            self.release(rider)

    def destroy(self, obj: RecordView, mode: int) -> None:
        """Opcode F6."""
        if mode or obj.flags3c & 0x04:
            self.retire(obj)
            return
        obj.kind = 0
        self.release(obj)
        if obj.rider:
            rider = RecordView(obj.rider, self.mem.read, self.mem.write)
            rider.rider = 0
            rider.flags3c = rider.flags3c & ~0x04

    def restore_spawn_flag(self, obj: RecordView) -> None:
        """1AE0D4 / 1AE6DE: re-arm the level object table entry this record came from."""
        if obj.spawn_flag and (obj.flags6 & 0x20 or True):
            self.mem.write(SPAWN_BITMAP + obj.spawn_index, obj.spawn_flag, 1)

    def despawn(self, obj: RecordView) -> None:
        """1AE0B0: an object left the camera's neighbourhood."""
        for record in (obj, RecordView(obj.rider, self.mem.read, self.mem.write) if obj.rider else None):
            if record is None:
                continue
            record.kind = 0
            self.release(record)
            if record.flags6 & 0x20:
                self.restore_spawn_flag(record)

    def allocate_vram(self, obj: RecordView) -> bool:
        """1AD3E8: find ``vram_slots`` free consecutive slots; on failure the record is dropped."""
        need = obj.vram_slots
        base = VRAM_SLOT_MAP
        limit = VRAM_SLOT_COUNT - need
        for index in range(limit):
            if all(self.mem.u8(base + index + i) == 0 for i in range(need + 1)):
                for i in range(need + 1):
                    self.mem.write(base + index + i, 0xFF, 1)
                obj.vram_map = base + index
                obj.vram = int.from_bytes(self.rom[VRAM_SLOT_TABLE + 4 * index:VRAM_SLOT_TABLE + 4 * index + 4], 'big')
                return True
        self.restore_spawn_flag(obj)
        obj.kind = 0
        if obj.rider:
            rider = RecordView(obj.rider, self.mem.read, self.mem.write)
            self.restore_spawn_flag(rider)
            rider.kind = 0
        return False

    # ---- the player's animation selector (1AD150) ----------------------------------
    def player_select(self, obj: RecordView) -> int:
        m, S = self.mem, PLAYER_SCRIPTS
        if m.u8(0xFFF0D7):
            return S['attack']
        if m.u8(0xFFF173):
            m.write(0xFF7E77, 0, 1); m.write(0xFFF0E7, 0, 1)
            if m.u8(0xFFF0C1):
                if m.u16(0xFFF0B0) in (1, 2):
                    return S['cutscene_walk']
                m.write(0xFFF0CC, 0, 1)
                return S['cutscene_idle']
            return S['cutscene_fall']
        m.write(0xFF7E77, 0, 1); m.write(0xFFF0E7, 0, 1)
        if m.u8(0xFFF115):
            m.write(0xFF7E77, 0, 1); return S['special_115']
        if m.u8(0xFFF0CD):
            d3 = m.u8(0xFFF0D3)
            if 0x50 <= d3 < 0x52:
                m.write(0xFF7E77, 0, 1); return S['attack']
            if d3 == 0x60:
                m.write(0xFF7E77, 0, 1); return S['hang']
        if m.u8(0xFFF0D3) == 0x5E:
            m.write(0xFF7E77, 0, 1); return S['hang']
        if m.u8(0xFFF0DB):
            return S['special_tile']
        if m.u8(0xFFF0D0):
            index = (m.u16(PLAYER_Y) >> 2) & 0xF
            return int.from_bytes(self.rom[S['jump_table'] + 4 * index:S['jump_table'] + 4 * index + 4], 'big')
        if m.u8(0xFFF0D2):
            return S['d2']
        if not m.u8(0xFFF0C1):
            return S['fall']
        if m.u8(0xFFF0DE):
            return S['push_left']
        if m.u8(0xFFF0DF):
            return S['push_right']
        if m.u8(0xFFF0ED):
            return S['ed']
        return S['walk'] if m.u16(0xFFF0B0) in (1, 2) else S['idle']

    # ---- the animation channel (1AC784) -------------------------------------------
    def step_animation(self, obj: RecordView) -> None:
        if obj.kind == 0:
            return
        if obj.vram == 0:
            if not self.allocate_vram(obj):
                return
        pc = obj.script
        if pc == 0:
            return
        word = int.from_bytes(self.rom[pc:pc + 2], 'big')
        pc += 2
        descriptor = int.from_bytes(self.rom[word:word + 4], 'big')
        if descriptor != obj.frame:
            obj.frame = descriptor
            self.services.frame_changed(obj.slot, descriptor)
        if obj.delay:
            obj.delay -= 1
            return
        try:
            pc = self.run_ops(obj, pc, motion=False)
        except Stop:
            return
        obj.script = pc

    # ---- the motion channel and velocity integration (1ADE36) ---------------------
    def step_motion(self, obj: RecordView) -> None:
        m = self.mem
        if obj.kind == 0:
            return
        m.write(PREVIOUS_X, obj.x, 2); m.write(PREVIOUS_Y, obj.y, 2)
        if obj.frame != 0:
            if obj.kind != PLAYER_KIND:
                if not (obj.flags6 & 0x08) and self._off_screen(obj):
                    if not (obj.flags3c & 0x02):
                        self.despawn(obj)
                        self._store_delta(obj)
                        return
                self._integrate(obj)
            self._run_motion(obj)
        self._store_delta(obj)

    def _off_screen(self, obj) -> bool:
        cam_x, cam_y = self.mem.u16(CAMERA_X), self.mem.u16(CAMERA_Y)
        if (obj.y + 0xFF50) & 0xFFFF < cam_y:
            return True
        if (cam_y + 0x130) & 0xFFFF < (obj.y - 0x100) & 0xFFFF:
            return True
        if (obj.x + 0x50) & 0xFFFF < cam_x:
            return True
        return (cam_x + 0x190) & 0xFFFF < obj.x

    def _integrate(self, obj) -> None:
        vx = obj.vel_x
        if vx:
            if abs(vx) >= 0x28:
                obj.x = obj.x + _high_byte_signed(vx)
                if not (obj.flags3c & 0x01):
                    obj.vel_x = vx - 0x28 if vx > 0 else vx + 0x28
            else:
                obj.vel_x = 0
        if obj.flags6 & 0x40:
            obj.vel_y = obj.vel_y + 0x78
        vy = obj.vel_y
        if vy:
            if abs(vy) >= 0x3C:
                obj.y = obj.y + _high_byte_signed(vy)
                if not (obj.flags3c & 0x01):
                    obj.vel_y = vy - 0x3C if vy > 0 else vy + 0x3C
            else:
                obj.vel_y = 0

    def _run_motion(self, obj) -> None:
        pc = obj.motion_script
        if pc == 0 or obj.flags6 & 0x02:
            return
        dx = _signed(self.rom[pc]); dy = _signed(self.rom[pc + 1]); pc += 2
        if obj.kind == PLAYER_KIND:
            obj.x = obj.x + dx; self.mem.write(PLAYER_SCREEN_X, (self.mem.u16(PLAYER_SCREEN_X) + dx) & 0xFFFF, 2)
            obj.x = obj.x + dy; self.mem.write(PLAYER_SCREEN_Y, (self.mem.u16(PLAYER_SCREEN_Y) + dy) & 0xFFFF, 2)
        else:
            if obj.facing:
                dx = -dx
            obj.x = obj.x + dx
            if obj.flip:
                dy = -dy
            blocked_down = dy >= 0 and (obj.flags6 & 0x01) and (obj.flags7 & 0x10)
            if not blocked_down:
                obj.y = obj.y + dy
        if obj.motion_delay:
            obj.motion_delay -= 1
            return
        try:
            pc = self.run_ops(obj, pc, motion=True)
        except Stop:
            return
        obj.motion_script = pc

    def _store_delta(self, obj) -> None:
        m = self.mem
        dx = (obj.x - m.u16(PREVIOUS_X)) & 0xFFFF
        dy = (obj.y - m.u16(PREVIOUS_Y)) & 0xFFFF
        obj.delta_x = dx & 0xFF; obj.delta_y = dy & 0xFF
        if obj.flags3c & 0x04 and obj.rider:
            rider = RecordView(obj.rider, m.read, m.write)
            rider.x = rider.x + _signed_word(dx); rider.delta_x = dx & 0xFF
            rider.y = rider.y + _signed_word(dy); rider.delta_y = dy & 0xFF

    # ---- whole-table passes --------------------------------------------------------
    def animation_pass(self):
        if self.mem.u8(FRAME_COUNTER) & 1 == 0:
            return          # 1AC784 runs only on odd frames (btst #0, FF7E28 / beq)
        for slot in range(RECORD_COUNT):
            self.step_animation(self.mem.record(slot))

    def motion_pass(self):
        for slot in range(RECORD_COUNT):
            self.step_motion(self.mem.record(slot))


def _signed(b):
    return b - 256 if b & 0x80 else b


def _signed_word(w):
    w &= 0xFFFF
    return w - 0x10000 if w & 0x8000 else w


def _high_byte_signed(velocity):
    """``move.b 18(a1),d0 / ext.w``: the high byte of the velocity word as a signed pixel step."""
    return _signed((velocity >> 8) & 0xFF)


def _add_byte_to_word(word, delta):
    """``add.b d0,$1a(a1)``: a byte add into the high byte of the velocity word."""
    hi = ((word >> 8) + delta) & 0xFF
    return _signed_word((hi << 8) | (word & 0xFF))
