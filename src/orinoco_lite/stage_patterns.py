"""Conservative deterministic categories over unchanged comparison observations."""
from collections import Counter
from urllib.parse import urlsplit
from .stage_presentation import targets
from .stage_reports import safe_artifact, canonical, json_digest

RULE = 'declared-url-prefix-change'
CRITERIA = ('Only declared deployment prefixes differ in href/src attributes of a, link, img, script, source, or iframe elements. '
            'The remaining path, query, fragment, event order, and every other attribute must match exactly. '
            'Canonical links, metadata, embedded data, and mixed edits are outside this rule. No human acceptance is implied.')


def prefix(stage, side):
    artifact = stage['artifacts'].get(side, {})
    value = targets(stage)[side].get('url') or (artifact.get('operation') or {}).get('context', {}).get('base_url')
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.query or parsed.fragment or (parsed.scheme not in {'http', 'https', ''}) or value.startswith('//'):
        return None
    if not parsed.scheme and not value.startswith('/'):
        return None
    return value.rstrip('/') + '/'


def url_pattern(finding, stage, *, metadata=False):
    if finding['location'][:2] != ['html', 'events'] or not finding['before_present'] or not finding['after_present']:
        return None
    bases = {side: prefix(stage, side) for side in ('left', 'right')}
    if not all(bases.values()) or bases['left'] == bases['right']:
        return None
    before, after = finding['before'], finding['after']
    if not isinstance(before, list) or not isinstance(after, list) or len(before) != len(after):
        return None
    matched = []
    permitted = {'a': 'href', 'link': 'href', 'img': 'src', 'script': 'src', 'source': 'src', 'iframe': 'src'}
    if metadata:
        permitted = {'link': 'href', 'meta': 'content'}
    for a, b in zip(before, after):
        if a == b:
            continue
        if (not isinstance(a, list) or not isinstance(b, list) or len(a) != 3 or len(b) != 3
                or a[:2] != b[:2] or a[0] != 'start' or a[1] not in permitted):
            return None
        canonical_link = any(k == 'rel' and v and 'canonical' in v.lower().split() for k, v in a[2] + b[2])
        if metadata:
            if a[1] == 'link' and not canonical_link:
                return None
            if a[1] == 'meta' and not any(k in {'property', 'name'} and v in {'og:url', 'og:image', 'twitter:url', 'twitter:image'} for k, v in a[2]):
                return None
        elif canonical_link:
            return None
        if len(a[2]) != len(b[2]):
            return None
        for old, new in zip(a[2], b[2]):
            if old == new:
                continue
            if old[0] != new[0] or old[0] != permitted[a[1]] or not isinstance(old[1], str) or not isinstance(new[1], str):
                return None
            if any(value.startswith('//') for value in (old[1], new[1])):
                return None
            if (not old[1].startswith(bases['left']) or not new[1].startswith(bases['right'])
                    or old[1][len(bases['left']):] != new[1][len(bases['right']):]):
                return None
            matched.append({'element': a[1], 'attribute': old[0], 'before': old[1], 'after': new[1]})
    if not matched:
        return None
    relative = any(not urlsplit(base).scheme for base in bases.values())
    return {'category': 'recognized', 'rule': 'declared-metadata-url-prefix-change' if metadata else RULE, 'label': 'Declared metadata URL prefix change' if metadata else 'Declared URL prefix change',
            'subtype': 'metadata-prefix' if metadata else 'absolute-root-relative' if relative else 'absolute-prefix',
            'criteria': PATTERNS['metadata-prefix']['criteria'] if metadata else CRITERIA, 'prefixes': bases, 'matches': matched}


def capture_indexes(stage, root):
    result = {}
    for side in ('left', 'right'):
        role = side + '-http-cdx'
        context = (stage['artifacts'].get(side, {}).get('operation') or {}).get('context', {})
        if 'capture' not in context:
            continue
        statuses = {}
        if role in stage['artifacts']:
            path = safe_artifact(root, stage['artifacts'][role]['path'])
            for line in path.read_text().splitlines()[1:]:
                fields = line.split()
                if len(fields) > 4 and fields[4].isdigit():
                    statuses[fields[0]] = int(fields[4])
        result[side] = statuses
    return result


def classify(row, stage, indexes):
    finding = row['finding']
    if row['category'] == 'problems':
        return {'category': 'problem'}
    if row['supporting']:
        return {'category': 'supporting'}
    for side, present in [('left', 'before_present'), ('right', 'after_present')]:
        if not finding[present] and side in indexes:
            name = finding['subject']
            route = name[:-10] if name.endswith('index.html') else name
            base = prefix(stage, side)
            url = base + route if base else None
            status = indexes[side].get(url)
            observed = status in {404, 410}
            return {'category': 'coverage', 'subtype': 'observed-absence' if observed else 'not-retained',
                    'label': f'Observed HTTP {status}' if observed else 'File not retained in capture',
                    'side': side, 'url': url, 'http_status': status,
                    'criteria': 'A retained 404/410 establishes absence at capture time. Other missing files do not establish absence online.'}
    return url_pattern(finding, stage) or url_pattern(finding, stage, metadata=True) or {'category': 'unclassified'}


def classifications(reports):
    from .stage_presentation import group_supporting_observations
    result = {}
    for report, root in reports:
        for index, stage in enumerate(report['stages']):
            rows = group_supporting_observations([{'key': f"{report['run_id']}/{f['id']}", 'report': str(root), 'finding': f} for f in stage['findings']])
            indexes = capture_indexes(stage, root)
            repeated = {}
            for row in rows:
                result[row['key']] = classify(row, stage, indexes)
                f = row['finding']
                if result[row['key']]['category'] == 'unclassified' and f['location'][:2] == ['html', 'events']:
                    signature = canonical([f['before'], f['after']])
                    repeated.setdefault(signature, []).append(row)
            for signature, matches in repeated.items():
                subjects = {row['finding']['subject'] for row in matches}
                if len(subjects) < 2:
                    continue
                for row in matches:
                    result[row['key']] = {'category': 'recognized', 'rule': 'repeated-html-edit', 'subtype': 'repeated-html-edit',
                        'label': 'Repeated HTML edit', 'criteria': PATTERNS['repeated-html-edit']['criteria'],
                        'group': json_digest(signature), 'files': len(subjects), 'occurrences': len(matches)}
    return result


def counts(rows):
    numbers = Counter(row['classification']['category'] for row in rows)
    return {**{key: numbers[key] for key in ['unclassified', 'recognized', 'coverage', 'supporting', 'problem']},
            'differences': sum(numbers[k] for k in ['unclassified', 'recognized', 'coverage']),
            'raw_observations': sum(numbers[k] for k in ['unclassified', 'recognized', 'coverage', 'supporting']),
            'patterns': dict(Counter(row['classification'].get('subtype') for row in rows if row['classification']['category'] == 'recognized'))}


PATTERNS = {
    'absolute-prefix': {'label': 'Absolute deployment prefixes', 'criteria': CRITERIA},
    'absolute-root-relative': {'label': 'Absolute versus root-relative URLs', 'criteria': CRITERIA},
    'metadata-prefix': {'label': 'Canonical and social metadata URL prefixes', 'criteria': 'Only declared prefixes differ in canonical link href or og:url, og:image, twitter:url, twitter:image content. URL suffix and all other event values match exactly. This recognizes a representation pattern, not correctness.'},
    'repeated-html-edit': {'label': 'Repeated HTML edits', 'criteria': 'The exact same before/after HTML event hunk occurs in at least two distinct files in this comparison. Paths, queries, asset references, integrity, or content may differ within that repeated edit. Grouping establishes repetition only, not its cause or correctness. Every complete hunk remains inspectable.'},
}
