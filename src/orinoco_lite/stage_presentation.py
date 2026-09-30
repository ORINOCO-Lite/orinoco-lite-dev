"""Readable CLI and browser views over unchanged comparison evidence."""
from collections import defaultdict
from difflib import unified_diff
import json

from .stage_reports import safe_artifact


def targets(stage):
    result = {}
    for side in ('left', 'right'):
        artifact = stage['artifacts'].get(side, {})
        operation = artifact.get('operation') or {}
        context = operation.get('context', {})
        label = {'upstream': 'Orinoco (selected upstream)', 'lite': 'Orinoco Lite'}.get(context.get('flavor'), operation.get('operation', side.title()))
        result[side] = {'label': label,
                        'package_revision': context.get('package_commit'),
                        **stage.get('targets', {}).get(side, {})}
    return result


def annotate(rows):
    """Group mechanical observations without changing IDs or decision scope."""
    by_subject = defaultdict(list)
    for row in rows:
        row['category'] = 'problems' if row['finding']['stage'] == 'site-check' else 'differences'
        row['supporting_keys'] = []
        row['supporting'] = False
        by_subject[(row['report'], row['finding']['stage'], row['finding']['subject'])].append(row)
    for group in by_subject.values():
        mechanical = [r for r in group if r['finding']['location'][:1] == ['bytes']]
        primary = [r for r in group if r not in mechanical]
        if not mechanical:
            continue
        owners = primary or mechanical[:1]
        support = mechanical if primary else mechanical[1:]
        for owner in owners:
            owner['supporting_keys'] = [r['key'] for r in support]
        for row in support:
            row['supporting'] = True
    return rows


def diff_text(finding, stage, root):
    labels = targets(stage)
    subject = finding['subject']
    name = subject + (' / ' + '/'.join(map(str, finding['location'])) if finding['location'] else '')
    texts = []
    file_view = finding['location'][:1] == ['bytes']
    for role, value_side in [('left', 'before'), ('right', 'after')]:
        if file_view:
            artifact = stage['artifacts'].get(role)
            path = safe_artifact(root, artifact['path']) if artifact else None
            if path and path.is_dir():
                path = safe_artifact(path, subject)
            if path and path.is_file():
                try:
                    raw = path.read_bytes()
                    if b'\0' in raw:
                        raise UnicodeError()
                    text = raw.decode('utf-8')
                except UnicodeError:
                    return 'Binary file differs; inspect the original artifacts.\n'
            else:
                text = ''
        elif not finding[value_side + '_present']:
            text = ''
        else:
            value = finding[value_side]
            # JSON spelling preserves strings vs numbers, null, order and multiplicity.
            text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
        texts.append(text.splitlines(keepends=True))
    lines = list(unified_diff(*texts, fromfile=labels['left']['label'] + ': ' + name,
                              tofile=labels['right']['label'] + ': ' + name, n=3))
    # Keep missing end-of-line visible, as in standard diff output.
    return ''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n' for line in lines)


def render_rows(rows, stages, *, category='differences', subject='', raw=False):
    """Plain output suitable for a pager, grep, or redirection; no ANSI controls."""
    lines = []
    for row in rows:
        if category != 'all' and row['category'] != category:
            continue
        if row['supporting'] and not raw:
            continue
        finding = row['finding']
        if subject and subject not in finding['subject']:
            continue
        stage, root = stages[row['key']]
        lines += [f"# {finding['stage']}: {finding['subject']} [{finding['id']}]",
                  f"# {stage['mode']} · {stage['status']}",
                  '# Targets: ' + json.dumps(targets(stage), ensure_ascii=False, sort_keys=True)]
        if row['category'] == 'problems':
            lines += [f"Possible problem ({finding.get('problem_status', 'not compared across targets')}): {' / '.join(map(str, finding['location']))}",
                      json.dumps(finding['after'], ensure_ascii=False, sort_keys=True)]
        else:
            lines.append(diff_text(finding, stage, root))
            if row['supporting_keys']:
                lines.append(f"# {len(row['supporting_keys'])} supporting observations retained (--raw)")
        for effect in row.get('effects', []):
            lines.append('# ' + effect['conclusion'])
        lines.append('')
    return '\n'.join(lines)
