"""frontier_ledger: what the last cold comparison still hands to the original.

    python scripts/frontier_ledger.py ARTIFACT_DIR [--census CENSUS_DIR ...]
                                      [--boundary src/aladdin_sega/boundary.py]

Reads ``comparison.json`` from a verification directory, takes the candidate
worker's fallback reasons, classifies each one and joins explicit refusals to
the boundary function that raised them:

    UNRECOVERED_TARGET  a dispatcher child with no recipe at all (a census target)
    UNSUPPORTED_ARM     a recovered entry declined one of its arms (a branch to add)
    SCHEDULER           the scheduler could not admit the plan before its deadline
    DEADLINE            a sound seam handed its suffix to the original at the deadline
    OTHER               anything else (read the reason)

With ``--census`` directories (from ``recovery_census.py``) it also lists how
often each target fired per record kind and which fixtures exist, so the next
bite is chosen from recorded evidence rather than guessed.  Read-only.
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
            'fallbacks': stats.get('fallbacks'), 'hits': stats.get('candidate_hits'), 'rows': rows}


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


def render(summary, census=()):
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
    parser.add_argument('--boundary', default=str(Path(__file__).resolve().parents[1] / 'src' / 'aladdin_sega' / 'boundary.py'))
    args = parser.parse_args(argv)
    comparison = Path(args.artifact_dir) / 'comparison.json'
    if not comparison.exists():
        print('no comparison.json in %s; run history-verify first' % args.artifact_dir)
        return 1
    print(render(ledger(comparison, args.boundary), census_rows(args.census)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
