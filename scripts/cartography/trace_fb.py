"""Group saved fallback snapshots by executed-path signature; keep one compact trace per class."""
import collections, json, os, re, subprocess, sys
fb = 'D:/Prog/aladdin_re/artifacts/grinder/scratch/fb'
py = 'D:/Prog/aladdin_re/.venv/Scripts/python.exe'
env = dict(os.environ, ALADDIN_NATIVE_LIBRARY='D:/Prog/aladdin_re/build/libaladdin_native.dll')
index = json.load(open(os.path.join(fb, 'index.json')))
want = sys.argv[1] if len(sys.argv) > 1 else ''
stop = sys.argv[2] if len(sys.argv) > 2 else None
classes = collections.OrderedDict()
for item in index:
    if want and want not in item['name']:
        continue
    out = subprocess.run([py, 'D:/Prog/aladdin_re/scripts/factcheck.py', 'facts', '--path',
                          os.path.join(fb, item['name'] + '.state')] + (['--stop', stop] if stop else []),
                         capture_output=True, text=True, env=env, cwd='D:/Prog/aladdin_re').stdout
    sig = next((l for l in out.splitlines() if l.startswith('signature:')), 'signature: ?')
    header = [l for l in out.splitlines() if l.startswith(('entry:', 'instructions:'))]
    path = [l for l in out.splitlines() if re.match(r'^ +\d+ [0-9A-F]{6} ', l)
            and not re.match(r'^ +\d+ 1E5[78]', l)]
    key = sig.split(' calls ')[0] + ' calls ' + sig.split(' calls ')[1].split(' changed ')[0] if ' calls ' in sig else sig
    entry = classes.setdefault(key, {'count': 0, 'names': [], 'header': header, 'path': path, 'sig': sig})
    entry['count'] += 1
    entry['names'].append(item['name'])
with open(os.path.join(fb, f'classes-{want or "all"}.txt'), 'w') as f:
    for key, entry in sorted(classes.items(), key=lambda kv: -kv[1]['count']):
        f.write(f"\n##### {entry['count']} x {key}\n")
        f.write('names: ' + ', '.join(entry['names'][:6]) + ('...' if len(entry['names']) > 6 else '') + '\n')
        f.write('\n'.join(entry['header']) + '\n' + entry['sig'] + '\n')
        f.write('\n'.join(entry['path']) + '\n')
print(len(classes), 'classes over', sum(e['count'] for e in classes.values()), 'states')
for key, entry in sorted(classes.items(), key=lambda kv: -kv[1]['count']):
    print(entry['count'], key, '|', entry['header'][1] if len(entry['header']) > 1 else '')
