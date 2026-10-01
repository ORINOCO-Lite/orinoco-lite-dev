"""Original-file comparisons derived from retained bytes, independent of decisions."""
from difflib import unified_diff
from .stage_reports import artifact_digest, safe_artifact, json_digest
from .stage_presentation import targets


def original_files(report, stage, root, index):
    from .site_compare import files
    if stage['stage'] == 'site-check' or not {'left', 'right'} <= stage['artifacts'].keys():
        return []
    sides = {side: safe_artifact(root, stage['artifacts'][side]['path']) for side in ('left', 'right')}
    trees = {side: files(path) if path.is_dir() else {'': path} for side, path in sides.items()}
    result = []
    for name in sorted(trees['left'].keys() | trees['right'].keys()):
        paths = {side: tree.get(name) for side, tree in trees.items()}
        digests = {side: artifact_digest(path) if path else None for side, path in paths.items()}
        if digests['left'] == digests['right']:
            continue
        subject = name or f"{sides['left'].name} → {sides['right'].name}"
        change = 'added' if paths['left'] is None else 'removed' if paths['right'] is None else 'changed'
        result.append({'key': json_digest([report['run_id'], index, name]), 'run_id': report['run_id'],
                       'stage_index': index, 'subject': subject, 'path': name, 'change': change,
                       'digests': digests, 'targets': targets(stage),
                       'scope': stage['scope'], 'status': stage['status']})
    return result


def original_diff(item, stage, root):
    texts = []
    binary = False
    for side in ('left', 'right'):
        base = safe_artifact(root, stage['artifacts'][side]['path'])
        path = safe_artifact(base, item['path']) if base.is_dir() and item['path'] else base
        raw = path.read_bytes() if item['digests'][side] is not None and path.is_file() else b''
        try:
            text = raw.decode('utf-8')
            if '\0' in text:
                binary = True
        except UnicodeDecodeError:
            binary = True
            text = ''
        texts.append(text.splitlines(keepends=True))
    if binary:
        text = f"Binary file {item['change']}: {item['subject']}\n"
    else:
        labels = [item['targets'][side]['label'] + ': ' + item['subject']
                  if item['digests'][side] is not None else '/dev/null' for side in ('left', 'right')]
        lines = unified_diff(*texts, fromfile=labels[0], tofile=labels[1], n=3)
        text = ''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n' for line in lines)
        if not text:
            text = f"Empty file {item['change']}: {item['subject']}\n"
    return {**item, 'binary': binary, 'unified_diff': text}
