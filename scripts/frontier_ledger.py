"""frontier_ledger: what the last cold comparison still hands to the original.

    python scripts/frontier_ledger.py ARTIFACT_DIR [--index EVIDENCE_DIR ...] [--census CENSUS_DIR ...]
                                      [--boundary src/aladdin_sega/boundary.py]

Reads ``comparison.json`` from a verification directory, takes the candidate
worker's fallback reasons, classifies each one and joins explicit refusals to
the boundary function that raised them:

    UNRECOVERED_TARGET  a dispatcher child with no recipe at all (a census target)
    UNSUPPORTED_ARM     a recovered entry declined one of its arms (a branch to add)
    SCHEDULER           the scheduler could not admit the plan before its deadline
    DEADLINE            a sound seam handed its suffix to the original at the deadline
    OTHER               anything else (read the reason)

With ``--index`` evidence directories (``recovery_census.py`` output with an
``index.json``) it lists every recorded behavior class of the frontier: how
often it fired, its cost and native shape, and whether a child and a parent
fixture exist, joined to the fallback count of its entry.  ``--census`` reads
older plain census reports.  Scheduler refusals are listed by gate when the
comparison carries ``fallbacks_by_gate``.  Read-only.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_TARGET = re.compile(r'target ([0-9A-F]{6}) is not recovered')
_UNRESOLVED = re.compile(r'([0-9A-F]{6}) unresolved')


def refusal_sites(boundary_text):
    """Map every literal ``raise UnsupportedCandidate('...')`` message to (line, function)."""
    sites = {}
    functions = [(m.start(), m.group(1)) for m in re.finditer(r'^def (\w+)\(', boundary_text, re.M)]
    for match in re.finditer(r"raise UnsupportedCandidate\(f?'([^']*)'\)", boundary_text):
        line = boundary_text.count('\n', 0, match.start()) + 1
        function = None
        for start, name in functions:
            if start < match.start():
                function = name
        sites[match.group(1)] = (line, function)
    return sites


def classify_reason(reason):
    text = reason.replace('unsupported domain: ', '')
    if reason == 'scheduler admission':
        return 'SCHEDULER', text, None
    if reason == 'legacy deadline':
        return 'DEADLINE', text, None
    target = _TARGET.search(text) or _UNRESOLVED.search(text)
    if target:
        return 'UNRECOVERED_TARGET', text, target.group(1)
    if 'not recovered' in text or 'unsupported' in text or 'requires' in text or 'declin' in text:
        return 'UNSUPPORTED_ARM', text, None
    return 'OTHER', text, None


def _site_for(text, sites):
    for marker, where in sites.items():
        literal = marker.split('{')[0]
        if literal and (marker == text or (len(literal) >= 12 and text.startswith(literal))):
            return where
    return None


def ledger(comparison_path, boundary_path):
    """Rows of (count, kind, reason, site, target) sorted by count."""
    report = json.loads(Path(comparison_path).read_text(encoding='utf-8'))
    stats = report.get('candidate_receipt', {}).get('candidate_stats', {})
    reasons = stats.get('fallback_reasons', {})
    sites = refusal_sites(Path(boundary_path).read_text(encoding='utf-8'))
    rows = []
    for reason, count in reasons.items():
        kind, text, target = classify_reason(reason)
        where = _site_for(text, sites) if kind in ('UNSUPPORTED_ARM', 'OTHER') else None
        if kind == 'OTHER' and where is not None:
            kind = 'UNSUPPORTED_ARM'  # an explicit boundary refusal, however it is worded
        rows.append({'count': count, 'kind': kind, 'reason': text, 'target': target,
                     'site': None if where is None else 'boundary.py:%d %s' % where})
    rows.sort(key=lambda row: (-row['count'], row['reason']))
    return {'status': report.get('status'), 'history_id': report.get('history_id'),
            'frames': report.get('candidate_receipt', {}).get('executed_frames'),
            'fallbacks': stats.get('fallbacks'), 'hits': stats.get('candidate_hits'), 'rows': rows,
            'by_gate': dict(sorted(stats.get('fallbacks_by_gate', {}).items(), key=lambda kv: -kv[1]))}


def index_rows(directories, summary=None):
    """Evidence rows from census index files, joined to the ledger's per-target fallback counts."""
    by_target = defaultdict(int)
    for row in (summary or {}).get('rows', []):
        if row['target']:
            by_target[row['target']] += row['count']
    rows = []
    for directory in directories:
        index_path = Path(directory) / 'index.json'
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text(encoding='utf-8'))
        for row in index['rows']:
            rows.append({'entry': row['entry'], 'branch': row['branch'], 'path_class': row['path_class'],
                         'count': row['count'], 'first_frame': row['first_frame'],
                         'instructions': row['instructions'], 'cycles': row['cycles'], 'exit': row['exit'],
                         'natives': row['natives'], 'writes': row.get('writes'),
                         'fixture': row['fixture'], 'parent_fixture': row['parent_fixture'],
                         'ccr_variants': len(row.get('ccr_variants', {})),
                         'fallbacks': by_target.get(row['entry'], 0),
                         'status': 'unrecovered target' if row['entry'] in by_target else 'not named in fallbacks',
                         'directory': str(directory), 'history_id': index['history_id']})
    rows.sort(key=lambda row: (-row['fallbacks'], row['entry'], -row['count']))
    return rows


def census_rows(directories):
    rows = []
    for directory in directories:
        report_path = Path(directory) / 'report.json'
        if not report_path.exists():
            continue
        report = json.loads(report_path.read_text(encoding='utf-8'))
        for key, count in report['counts'].items():
            entry, branch = key.split(':')
            rows.append({'entry': entry, 'branch': branch, 'count': count,
                         'fixtures': len(report['first'].get(key, [])),
                         'parents': len(report.get('parents', {}).get(key, [])),
                         'directory': str(directory), 'history_id': report['history_id']})
    rows.sort(key=lambda row: (-row['count'], row['entry']))
    return rows


def render(summary, census=(), index=()):
    lines = ['cold comparison %s: history %s, %s frames, %s candidate hits, %s fallbacks' % (
        summary['status'], (summary['history_id'] or '?')[:12], summary['frames'], summary['hits'], summary['fallbacks'])]
    lines.append('%6s  %-18s  %-8s  %-64s  %s' % ('count', 'class', 'target', 'reason', 'refusal site'))
    for row in summary['rows']:
        lines.append('%6d  %-18s  %-8s  %-64s  %s' % (
            row['count'], row['kind'], row['target'] or '-', row['reason'][:64], row['site'] or '-'))
    by_target = defaultdict(int)
    for row in summary['rows']:
        if row['target']:
            by_target[row['target']] += row['count']
    if by_target:
        lines.append('unrecovered targets by fallback count: ' + ', '.join(
            '%s (%d)' % item for item in sorted(by_target.items(), key=lambda item: -item[1])))
    arms = [row for row in summary['rows'] if row['kind'] == 'UNSUPPORTED_ARM']
    if arms:
        lines.append('unsupported arms by fallback count: ' + ', '.join(
            '%s (%d)' % (row['site'] or row['reason'][:30], row['count']) for row in arms[:8]))
    if summary.get('by_gate') and any(row['kind'] == 'SCHEDULER' for row in summary['rows']):
        lines.append('fallbacks by gate: ' + ', '.join('%s (%d)' % item for item in list(summary['by_gate'].items())[:6]))
    if index:
        lines.append('')
        lines.append('evidence index: %-6s %-6s %-5s %6s %9s %5s %6s %-13s %-7s %-8s %s' % (
            'entry', 'kind', 'path', 'count', 'first', 'instr', 'fallbk', 'native', 'child', 'parent', 'status'))
        for row in index:
            lines.append('                %-6s %-6s p%-4d %6d %9d %5d %6d %-13s %-7s %-8s %s' % (
                row['entry'], row['branch'][4:] if row['branch'].startswith('kind') else row['branch'], row['path_class'],
                row['count'], row['first_frame'], row['instructions'], row['fallbacks'],
                ','.join(row['natives'][:2]) or 'none', 'yes' if row['fixture'] else 'no',
                'yes' if row['parent_fixture'] else 'no', row['status']))
    if census:
        lines.append('')
        lines.append('recorded census: %-6s %-10s %6s  %8s  %7s  directory' % ('entry', 'branch', 'count', 'fixtures', 'parents'))
        for row in census:
            lines.append('                 %-6s %-10s %6d  %8d  %7d  %s' % (
                row['entry'], row['branch'], row['count'], row['fixtures'], row['parents'], row['directory']))
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('artifact_dir')
    parser.add_argument('--census', action='append', default=[])
    parser.add_argument('--index', action='append', default=[], help='census output directory with index.json')
    parser.add_argument('--boundary', default=str(Path(__file__).resolve().parents[1] / 'src' / 'aladdin_sega' / 'boundary.py'))
    args = parser.parse_args(argv)
    comparison = Path(args.artifact_dir) / 'comparison.json'
    if not comparison.exists():
        print('no comparison.json in %s; run history-verify first' % args.artifact_dir)
        return 1
    summary = ledger(comparison, args.boundary)
    print(render(summary, census_rows(args.census), index_rows(args.index, summary)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
