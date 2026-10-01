"""Classify retained observations without altering evidence or decisions."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import types

from .errors import ConfigurationError
from .stage_reports import safe_artifact, canonical, json_digest, execution_context
from .stage_presentation import targets
from .review_heuristic import prefix


class Heuristic:
    def __init__(self, module, source):
        rules = getattr(module, 'RULES', None)
        if not isinstance(rules, (tuple, list)) or any(not callable(rule) for rule in rules):
            raise ConfigurationError('A Python heuristic must define an ordered RULES list of callables')
        self.rules = tuple(rules)
        self.info = {'name': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                     'rules': [getattr(rule, '__name__', type(rule).__name__) for rule in rules],
                     'context': execution_context()}

    def classify(self, finding, stage):
        stage = {key: value for key, value in stage.items() if key != 'findings'}
        for rule in self.rules:
            name = getattr(rule, '__name__', type(rule).__name__)
            try:
                result = rule(deepcopy(finding), deepcopy(stage))
            except Exception as error:
                raise ConfigurationError(f'Heuristic rule {name} failed: {error}') from error
            if result is None:
                continue
            if isinstance(result, str):
                result = {'rule': result}
            if not isinstance(result, dict) or not isinstance(result.get('rule'), str) or not result['rule'].strip():
                raise ConfigurationError(f'Heuristic rule {name} must return None, a name, or a dictionary with rule')
            result = deepcopy(result)
            result['category'] = 'recognized'
            result.setdefault('subtype', result['rule'])
            result.setdefault('label', result['rule'])
            for field in ('subtype', 'label', 'criteria'):
                if field in result and not isinstance(result[field], str):
                    raise ConfigurationError(f'Heuristic {field} must be text')
            canonical(result)
            return result
        return {'category': 'unclassified'}


def load_heuristic(path=None):
    """Only explicit CLI selection executes custom Python; bundles never do."""
    if path is None:
        from . import review_heuristic as module
        source = Path(module.__file__)
    else:
        source = Path(path).absolute()
        module = types.ModuleType('selected_review_heuristic')
        module.__file__ = str(source)
        try:
            exec(compile(source.read_bytes(), str(source), 'exec'), module.__dict__)
        except Exception as error:
            raise ConfigurationError(f'Cannot load heuristic {source}: {error}') from error
    return Heuristic(module, source)


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


def classify(row, stage, indexes, heuristic):
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
    return heuristic.classify(finding, stage)


def classifications(reports, heuristic=None):
    heuristic = heuristic or load_heuristic()
    from .stage_presentation import group_supporting_observations
    result = {}
    for report, root in reports:
        for index, stage in enumerate(report['stages']):
            rows = group_supporting_observations([{'key': f"{report['run_id']}/{f['id']}", 'report': str(root), 'finding': f} for f in stage['findings']])
            indexes = capture_indexes(stage, root)
            repeated = {}
            for row in rows:
                result[row['key']] = classify(row, stage, indexes, heuristic)
                f = row['finding']
                if result[row['key']]['category'] == 'unclassified' and f['location'][:2] == ['html', 'events']:
                    signature = canonical([f['before'], f['after']])
                    repeated.setdefault(signature, []).append(row)
            for signature, matches in repeated.items():
                subjects = {row['finding']['subject'] for row in matches}
                if len(subjects) < 2:
                    continue
                for row in matches:
                    result[row['key']] = {'category': 'unclassified', 'rule': 'repeated-html-edit', 'subtype': 'repeated-html-edit',
                        'label': 'Unclassified repeated HTML edit',
                        'group': json_digest(signature), 'files': len(subjects), 'occurrences': len(matches)}
    return result


def counts(rows):
    numbers = Counter(row['classification']['category'] for row in rows)
    return {**{key: numbers[key] for key in ['unclassified', 'recognized', 'coverage', 'supporting', 'problem']},
            'differences': sum(numbers[k] for k in ['unclassified', 'recognized', 'coverage']),
            'raw_observations': sum(numbers[k] for k in ['unclassified', 'recognized', 'coverage', 'supporting']),
            'patterns': dict(Counter(row['classification'].get('subtype') for row in rows if row['classification']['category'] == 'recognized'))}


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
