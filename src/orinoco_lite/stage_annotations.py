"""Optional authored investigation notes; never part of decision matching."""
from copy import deepcopy
from pathlib import Path
import shutil
from .errors import ConfigurationError
from .stage_reports import read_json, artifact_digest, safe_artifact


def load_annotations(path, reports, *, document=None):
    if path is None:
        return []
    path = Path(path).absolute()
    data = read_json(path) if document is None else document
    if not isinstance(data, dict) or set(data) != {'annotations'} or not isinstance(data['annotations'], list):
        raise ConfigurationError('Annotation file requires an annotations list')
    known = {f"{r['run_id']}/{f['id']}" for r, _ in reports for s in r['stages'] for f in s['findings']}
    result = deepcopy(data['annotations'])
    allowed = {'finding_key', 'author', 'tags', 'explanation', 'hypothesis', 'conclusion', 'limits', 'evidence', 'commands'}
    for note in result:
        if not isinstance(note, dict) or set(note) - allowed:
            raise ConfigurationError('Unknown annotation fields; human dispositions belong in decisions')
        if note.get('finding_key') not in known:
            raise ConfigurationError('Annotation must reference a finding in the supplied reports')
        for field in ('author', 'explanation', 'limits'):
            if not isinstance(note.get(field), str) or not note[field].strip():
                raise ConfigurationError(f'Annotation requires nonempty {field}')
        for field in ('hypothesis', 'conclusion'):
            if field in note and not isinstance(note[field], str):
                raise ConfigurationError(f'Annotation {field} must be text')
        if not isinstance(note.get('tags', []), list) or any(not isinstance(t, str) for t in note.get('tags', [])):
            raise ConfigurationError('Annotation tags must be a list of text labels')
        if not isinstance(note.get('commands', []), list) or any(not isinstance(c, list) or not c or any(not isinstance(a, str) for a in c) for c in note.get('commands', [])):
            raise ConfigurationError('Annotation commands must be argument lists; they are displayed, never executed')
        if not isinstance(note.get('evidence'), list) or not note['evidence']:
            raise ConfigurationError('Annotation requires inspectable evidence, including for an opinion')
        for evidence in note['evidence']:
            if not isinstance(evidence, dict) or set(evidence) != {'label', 'path'} or any(not isinstance(evidence[k], str) or not evidence[k] for k in evidence):
                raise ConfigurationError('Annotation evidence requires label and path')
            source = path.parent / evidence['path']
            evidence['digest'] = artifact_digest(source)
            evidence['path'] = str(source.absolute())
    return result


def copy_annotations(notes, destination):
    result = deepcopy(notes)
    for i, note in enumerate(result):
        for j, evidence in enumerate(note['evidence']):
            source = Path(evidence['path'])
            relative = f'annotations/{i}/{j}/{source.name}'
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copyfile(source, target)
            if artifact_digest(target) != evidence['digest']:
                raise ConfigurationError('Annotation evidence changed while copying')
            evidence['path'] = relative
    return result


def validate_copied(notes, root, reports):
    if not isinstance(notes, list):
        raise ConfigurationError('Bundle annotations must be a list')
    source = deepcopy(notes)
    for note in source:
        if not isinstance(note, dict):
            raise ConfigurationError('Annotation must be an object')
        for evidence in note.get('evidence', []):
            path = safe_artifact(root, evidence['path'])
            if artifact_digest(path) != evidence.pop('digest', None):
                raise ConfigurationError('Annotation evidence differs from its retained digest')
            evidence['path'] = str(path)
    load_annotations(root / 'review.json', reports, document={'annotations': source})
