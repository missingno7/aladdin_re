"""Extract the object asset graph: template -> scripts -> animations -> frames -> pieces -> tiles.

Writes artifacts/cartography/asset_graph.json and a sheet of every template's
first frame (artifacts/cartography/template_sheet.png) rendered from ROM.
"""
import json, os, sys, collections
from pathlib import Path
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'src'))
from aladdin_sega.profile import read_rom
from aladdin_sega.game import assets, scripts
from aladdin_sega.game.objects.script_engine import PLAYER_SCRIPTS
from PIL import Image, ImageDraw

rom = read_rom()
out = root / 'artifacts' / 'cartography'
graph = {'templates': [], 'scripts': {}, 'frames': {}, 'tile_sources': collections.Counter()}


def walk(script):
    """Yield every block of a decoded script graph."""
    yield script
    for block in script.blocks.values():
        yield from walk(block)


def animations_of(script):
    """Split a script graph into animations: maximal frame runs between control opcodes."""
    out = []
    for block in walk(script):
        run = []
        for item in block.items:
            if isinstance(item, scripts.Frame):
                run.append(item)
            elif run:
                out.append((block.address, run)); run = []
        if run:
            out.append((block.address, run))
    return out


def record_script(address, kind):
    if address in graph['scripts'] or not (0 < address < len(rom)):
        return
    sc = scripts.decode_animation(rom, address) if kind == 'animation' else scripts.decode_motion(rom, address)
    entry = {'kind': kind, 'blocks': {}, 'animations': []}
    for block in walk(sc):
        entry['blocks'][f'{block.address:06X}'] = [
            (f'{i.address:06X}', 'frame', f'{i.descriptor:06X}') if isinstance(i, scripts.Frame) else
            (f'{i.address:06X}', 'step', i.dx, i.dy) if isinstance(i, scripts.MotionStep) else
            (f'{i.address:06X}', i.name, [f'{a:06X}' if isinstance(a, int) and a > 0xFFFF else a for a in i.operands])
            for i in block.items]
        for op in block.ops():
            if op.name == 'spawn':
                entry.setdefault('spawns', []).append(f'{op.operands[1]:06X}')
                if op.operands[4]: record_script(op.operands[4], 'animation')
                if op.operands[5]: record_script(op.operands[5], 'motion')
            if op.name == 'sound':
                entry.setdefault('sounds', []).append(op.operands[0] & 0x7F)
    if kind == 'animation':
        for block_address, run in animations_of(sc):
            frames = [f'{f.descriptor:06X}' for f in run]
            entry['animations'].append({'block': f'{block_address:06X}', 'frames': frames, 'length': len(run)})
            for f in run:
                if f'{f.descriptor:06X}' not in graph['frames']:
                    fr = assets.SpriteFrame.from_rom(rom, f.descriptor)
                    graph['frames'][f'{f.descriptor:06X}'] = [
                        {'dx': p.dx, 'dy': p.dy, 'size': p.tile_record.size_tiles, 'source': f'{p.source:06X}',
                         'tiles': p.tile_record.tiles} for p in fr.pieces]
                    for p in fr.pieces:
                        graph['tile_sources'][f'{p.source:06X}'] += 1
    graph['scripts'][f'{address:06X}'] = entry


for t in assets.templates(rom):
    graph['templates'].append({'address': f'{t.address:06X}', 'kind': t.kind, 'hit_points': t.hit_points,
                               'script': f'{t.script:06X}', 'motion_script': f'{t.motion_script:06X}',
                               'attributes': t.attributes, 'vram_slots': t.vram_slots, 'flags': t.flags.hex(),
                               'flags3c': t.flags3c})
    if t.script: record_script(t.script, 'animation')
    if t.motion_script: record_script(t.motion_script, 'motion')
for name, address in PLAYER_SCRIPTS.items():
    if name != 'jump_table':
        record_script(address, 'animation')
for i in range(16):
    record_script(int.from_bytes(rom[PLAYER_SCRIPTS['jump_table'] + 4 * i:PLAYER_SCRIPTS['jump_table'] + 4 * i + 4], 'big'), 'animation')

shared = {s: n for s, n in graph['tile_sources'].items() if n > 1}
print('templates', len(graph['templates']), 'scripts', len(graph['scripts']), 'frames', len(graph['frames']),
      'tile sources', len(graph['tile_sources']), 'shared sources', len(shared))
graph['tile_sources'] = dict(graph['tile_sources'])
json.dump(graph, open(out / 'asset_graph.json', 'w'), indent=1)

# sheet: each template's first frame
cell, cols = 96, 10
ts = [t for t in assets.templates(rom) if t.script]
sheet = Image.new('RGBA', (cols * cell, ((len(ts) + cols - 1) // cols) * (cell + 14)), (40, 40, 40, 255)); d = ImageDraw.Draw(sheet)
for i, t in enumerate(ts):
    sc = scripts.decode_animation(rom, t.script, follow=False)
    frames = sc.frames()
    x, y = (i % cols) * cell, (i // cols) * (cell + 14)
    d.text((x + 2, y + 2), f'{t.address:06X} k{t.kind:02X}', fill='yellow')
    if frames:
        try:
            im, _ = assets.render_frame(rom, assets.SpriteFrame.from_rom(rom, frames[0].descriptor))
            im.thumbnail((cell - 4, cell - 4)); sheet.paste(im, (x + 2, y + 14), im)
        except Exception as error:
            d.text((x + 2, y + 40), 'render error', fill='red')
sheet.save(out / 'template_sheet.png'); print('sheet', sheet.size)
