"""Deterministic rules over unchanged observations, in deliberate precedence order.

1. Problem checks and supporting byte observations are not primary differences.
2. Missing captured files are snapshot evidence questions, before content rules.
3. Narrow ordinary URL-prefix matches require an otherwise identical hunk.
4. Narrow canonical/social metadata-prefix matches use the same exactness test.
5. Graph array and named HTML rules require complete matches.
6. Only remaining complete HTML hunks may enter repeated-edit groups (>=2 files).
7. Everything else stays unclassified, including any unmatched mixed hunk.

First matching rule owns each entire hunk. Repetition never absorbs a partial
match or hides a remainder. Recognition changes neither evidence nor decisions.
"""
from collections import Counter
from copy import deepcopy
import re
from urllib.parse import urlsplit, parse_qsl
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


def recognized(kind):
    return {'category': 'recognized', 'rule': kind, 'subtype': kind, **PATTERNS[kind]}


def graph_pattern(finding):
    """Compare complete arrays without treating IDs or multiplicity as disposable."""
    if finding.get('subject') not in {'graph.json', 'static/graph.json'} or not all(
            finding.get(k) for k in ('before_present', 'after_present')):
        return None
    location = finding['location']
    if location not in [['json', 'nodes'], ['json', 'edges']]:
        return None
    before, after = finding['before'], finding['after']
    if not all(isinstance(xs, list) and all(isinstance(x, dict) and isinstance(x.get('id'), str)
               for x in xs) and len({x['id'] for x in xs}) == len(xs) for xs in (before, after)):
        return None
    if Counter(map(canonical, before)) == Counter(map(canonical, after)):
        return recognized('graph-node-order' if location[-1] == 'nodes' else 'graph-edge-order')
    if location[-1] == 'edges' and all(re.fullmatch(r'e[0-9]+', x['id']) and
            isinstance(x.get('source'), str) and isinstance(x.get('target'), str)
            for xs in (before, after) for x in xs):
        def content(xs):
            return Counter(canonical({k: v for k, v in x.items() if k != 'id'}) for x in xs)
        if content(before) == content(after):
            return recognized('graph-edge-ids')
    return None


def editor_link_pattern(finding, stage):
    """Match the complete upstream-to-Lite link edit, including raw query bytes."""
    if finding['location'][:2] != ['html', 'events'] or not all(
            finding.get(k) for k in ('before_present', 'after_present')):
        return None
    before, after = finding['before'], finding['after']
    base = prefix(stage, 'right')
    if not base or not isinstance(before, list) or len(before) != 2:
        return None
    anchor = before[1]
    if not isinstance(anchor, list) or len(anchor) != 3 or anchor[:2] != ['start', 'a']:
        return None
    attrs = anchor[2]
    if not isinstance(attrs, list) or len(attrs) != 3 or attrs[:2] != [
            ['class', 'text-primary-500'], ['target', '_blank']]:
        return None
    if len(attrs[2]) != 2 or attrs[2][0] != 'href' or not isinstance(attrs[2][1], str):
        return None
    href = attrs[2][1]
    source = 'https://pool.psychoinformatics.de/ui/?'
    if not href.startswith(source) or urlsplit(href).fragment:
        return None
    query = href[len(source):]
    pairs = parse_qsl(query, keep_blank_values=True)
    fields = dict(pairs)
    if len(pairs) != 3 or set(fields) != {'sh:NodeShape', 'pid', 'edit'} or (
            fields['sh:NodeShape'] != 'dlthings:Thing' or not fields['pid'] or fields['edit'] != 'true'):
        return None
    if before[0] != ['start', 'div', [['class', 'text-xs']]]:
        return None
    expected = [['start', 'div', [['class', 'orinoco-record-editor-link text-xs']]],
        ['start', 'a', [['class', 'text-primary-500'], ['target', '_blank'],
        ['rel', 'noopener noreferrer'], ['href', base + 'edit/?' + query]]]]
    if after == expected:
        return recognized('record-editor-link')
    return None


def named_html_pattern(finding):
    """Recognize complete, bounded edits before generic exact repetition."""
    if finding['location'][:2] != ['html', 'events'] or not all(
            finding.get(k) for k in ('before_present', 'after_present')):
        return None
    before, after = finding['before'], finding['after']
    if not isinstance(before, list) or not isinstance(after, list):
        return None
    if len(before) == len(after) == 1 and before[0][:2] == after[0][:2] == ['start', 'a']:
        attrs = before[0][2]
        if ['target', '_blank'] in attrs and after[0][2] == [a for a in attrs if a != ['target', '_blank']]:
            return recognized('link-target-removal')
        if before == [['start', 'a', [['href', None], ['title', None]]]] and after == [['start', 'a', [['href', None], ['title', 'Outputs']]]]:
            return recognized('navigation-title')
    if before == [['end', 'span']] and after == [['text', '\n'], ['end', 'span'], ['end', 'span'],
            ['start', 'span', [['class', 'decoration-primary-500 group-hover:underline group-hover:decoration-2 group-hover:underline-offset-2']]], ['text', 'Collaboration hub']]:
        return recognized('navigation-label')
    if before == [['text', 'Edit this record\n'], ['end', 'a'], ['text', 'in the knowledge pool.']] and after == [['text', 'Edit this record'], ['end', 'a']]:
        return recognized('edit-link-text')
    if len(before) == len(after) == 1 and before[0][:2] == after[0][:2] == ['start', 'script']:
        expected = deepcopy(before)
        for attr in expected[0][2]:
            if attr == ['src', '/graph.js']:
                candidates = [v for k, v in after[0][2] if k == 'src']
                if len(candidates) == 1 and re.fullmatch(r'/graph\.js\?v=[0-9a-f]{64}', candidates[0]):
                    attr[1] = candidates[0]
                    if expected == after:
                        return recognized('graph-script-version')
    # Match the entire known contact navigation subtree, not an arbitrary deletion.
    contact = [['start', 'nav', [['class', 'pb-4 text-base font-medium text-neutral-500 dark:text-neutral-400']]],
        ['start', 'ul', [['class', 'flex list-none flex-col sm:flex-row']]],
        ['start', 'li', [['class', 'group mb-1 text-end sm:mb-0 sm:me-7 sm:last:me-0']]],
        ['start', 'a', [['href', '/contact/'], ['title', 'Contact and location']]],
        ['start', 'span', [['class', 'decoration-primary-500 group-hover:underline group-hover:decoration-2 group-hover:underline-offset-2']]],
        ['text', 'Contact and location'], ['end', 'span'], ['end', 'a'], ['end', 'li'], ['end', 'ul'], ['end', 'nav']]
    if before == contact and after == []:
        return recognized('contact-navigation-removal')
    return None


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
            capture = (stage['artifacts'][side].get('operation') or {}).get('context', {}).get('capture', {})
            requested = route in capture.get('routes', [])
            failed = status is not None and status >= 400 and not observed
            return {'category': 'coverage', 'subtype': 'observed-absence' if observed else 'retrieval-failed' if failed else 'not-retained',
                    'selected_route': requested,
                    'request_outcome': 'http-response' if status is not None else 'unknown',
                    'label': f'Observed HTTP {status}' if observed else f'Retrieval failed: HTTP {status}' if failed else f'HTTP {status} recorded; file not retained' if status is not None else 'No retained file; request outcome unknown',
                    'side': side, 'url': url, 'http_status': status,
                    'criteria': 'A retained 404/410 establishes absence at capture time. Other missing files do not establish absence online.'}
    return (url_pattern(finding, stage) or url_pattern(finding, stage, metadata=True)
            or graph_pattern(finding) or editor_link_pattern(finding, stage) or named_html_pattern(finding) or {'category': 'unclassified'})


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
    'graph-node-order': {'label': 'Graph node order change', 'criteria': 'The complete node objects, IDs, properties, and multiplicities match; only array order differs. Order-dependent display effects are not evaluated.'},
    'graph-edge-order': {'label': 'Graph edge order change', 'criteria': 'The complete edge objects, IDs, endpoints, properties, and multiplicities match; only array order differs.'},
    'graph-edge-ids': {'label': 'Graph edge order and ID change', 'criteria': 'All edge properties and multiplicities match after excluding only unique generated e-number IDs. Endpoints and direction are preserved. Consumer dependence on ordering or IDs is not evaluated.'},
    'link-target-removal': {'label': 'Link target attribute removal', 'criteria': 'The entire hunk removes only target="_blank" from an anchor; its URL and every other attribute are unchanged. This changes the browsing context and is not automatically accepted.'},
    'navigation-title': {'label': 'Navigation title addition', 'criteria': 'The complete anchor event changes only its empty title to Outputs. Its empty href is preserved.'},
    'navigation-label': {'label': 'Navigation label markup addition', 'criteria': 'The complete known hunk adds Collaboration hub text with its span and whitespace changes.'},
    'record-editor-link': {'label': 'Record editor link adaptation', 'criteria': 'The complete two-event hunk replaces the upstream knowledge-pool editor URL with edit/ under the declared destination base, adds the orinoco-record-editor-link wrapper class and rel="noopener noreferrer", and preserves the raw three-field record query, target, and anchor class exactly. Wording is classified separately; editor operation and acceptance are not established.'},
    'edit-link-text': {'label': 'Record edit-link text change', 'criteria': 'The complete known hunk removes the trailing knowledge-pool wording and newline. Editor URL changes are separate.'},
    'graph-script-version': {'label': 'Graph script version query addition', 'criteria': 'Only a 64-character hexadecimal v parameter is added to /graph.js in the complete script event. Other attributes match; script contents and the version value are not verified by this rule.'},
    'contact-navigation-removal': {'label': 'Contact navigation removal', 'criteria': 'The complete known Contact and location navigation subtree is removed. This does not describe the whole footer or accept the removal.'},
    'repeated-html-edit': {'label': 'Repeated HTML edits', 'criteria': 'The exact same before/after HTML event hunk occurs in at least two distinct files in this comparison. Paths, queries, asset references, integrity, or content may differ within that repeated edit. Grouping establishes repetition only, not its cause or correctness. Every complete hunk remains inspectable.'},
}


def snapshot_scope(stage, root):
    """Describe the saved snapshot, not the completeness of the online website."""
    from .site_compare import files
    indexes = capture_indexes(stage, root)
    result = []
    for side in ('left', 'right'):
        artifact = stage['artifacts'].get(side)
        if not artifact:
            continue
        context = (artifact.get('operation') or {}).get('context', {})
        item = {'side': side, 'label': targets(stage)[side]['label']}
        path = safe_artifact(root, artifact['path'])
        if side not in indexes:
            item.update(kind='local', description='Complete retained local output tree; no network retrieval was involved.',
                        files=len(files(path)) if path.is_dir() else 1)
        else:
            capture = context['capture']; responses = indexes[side]
            base = prefix(stage, side)
            requested = [base + route for route in capture.get('routes', [])] if base else []
            item.update(kind='capture', description='Selected routes and discovered same-host page assets. Other routes may exist; no exhaustive crawl or JavaScript execution.',
                requested_routes=capture.get('requested_routes'), routes=capture.get('routes', []),
                successful_responses=sum(200 <= c < 300 for c in responses.values()),
                confirmed_absences=sum(c in {404, 410} for c in responses.values()),
                error_responses=sum(c >= 400 and c not in {404,410} for c in responses.values()),
                requested_without_response=sum(url not in responses for url in requested),
                retrieval_complete=capture.get('retrieval_complete'),
                files=len(files(path)) if path.is_dir() else 1,
                evidence_roles=[role for role in stage['artifacts'] if role.startswith(side + '-http') or role == side + '-wget-log'])
        result.append(item)
    return result
