"""Site-pair scope derived from retained artifacts and producing operations."""
from .stage_reports import json_digest
from .stage_presentation import targets


def identity(artifact):
    return artifact.get('digest'), json_digest(artifact['operation']) if artifact.get('operation') else None


def site_scopes(stages):
    """Follow exact producer+digest links backwards; display names are not lineage."""
    artifacts = [a for _, s, _ in stages.values() for a in s['artifacts'].values()]
    anchors = {key: s for key, (_, s, _) in stages.items()
               if s['stage'] == 'rendering' and not s['scope'].get('replay')}
    complete_targets = {json_digest(targets(s)) for s in anchors.values() if s['mode'] == 'complete-path'}
    anchors = {k: s for k, s in anchors.items()
               if s['mode'] == 'complete-path' or json_digest(targets(s)) not in complete_targets}
    result = {}
    for key, anchor in anchors.items():
        pair = json_digest({side: identity(anchor['artifacts'][side]) for side in ('left', 'right')})
        lineage = {}
        for side in ('left', 'right'):
            reached = {identity(anchor['artifacts'][side])}
            while True:
                dependencies = {(d.get('digest'), d.get('producer')) for a in artifacts if identity(a) in reached
                                for d in (a.get('operation') or {}).get('inputs', {}).values()}
                expanded = reached | dependencies
                if expanded == reached:
                    break
                reached = expanded
            lineage[side] = reached
        members = {key}
        for candidate, (_, s, _) in stages.items():
            if s['scope'].get('replay'):
                continue
            left, right = (identity(s['artifacts'].get(side, {})) for side in ('left', 'right'))
            if left in lineage['left'] and right in lineage['right']:
                members.add(candidate)
            # Checks are attached only to the exact output checked.
            if s['stage'] == 'site-check' and (left in lineage['left'] | lineage['right'] or right in lineage['left'] | lineage['right']):
                members.add(candidate)
        existing = result.setdefault(pair, {'anchor': key, 'members': set()})
        existing['members'].update(members)
    return result
