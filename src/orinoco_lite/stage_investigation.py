"""Explicit artifact comparisons and bounded generated-file replay."""
from pathlib import Path
import shutil

from .errors import ConfigurationError
from .stage_reports import (artifact_digest, canonical, json_digest, load_report,
                            safe_artifact, write_operation, write_report)


def register(commands):
    from .diagnostics import options
    compare = commands.add_parser('compare', help='compare retained artifacts from any two revisions or deployments')
    compare.add_argument('left', type=Path)
    compare.add_argument('right', type=Path)
    options(compare, replace=False)
    compare.add_argument('--name', required=True, help='new report name')
    compare.add_argument('--stage', choices=('storage', 'projection', 'assembly', 'rendering'), default='rendering')
    from .stage_experiments import EXPERIMENTS
    compare.add_argument('--experiment', choices=tuple(EXPERIMENTS), default='snapshot',
                         help='question and controls for this comparison; declaring a design does not verify its controls')
    compare.add_argument('--check-links', action='store_true', help='also compare local-link problems, in a separate report')
    compare.add_argument('--left-base-url', default='/')
    compare.add_argument('--right-base-url', default='/')
    compare.add_argument('--mode', choices=('isolated', 'complete-path'), default='complete-path')
    for side in ('left', 'right'):
        compare.add_argument(f'--{side}-label', help='e.g. Orinoco, Lite candidate, Official site, Draft deployment')
        for field, help_text in (
            ('url', 'site URL for retained deployment artifacts; does not fetch the site'),
            ('branch-url', 'related upstream hub branch; does not establish the deployed revision'),
            ('revision', 'revision identified by the retained build evidence, if known'),
            ('captured-at', 'recorded capture timestamp, if known'),
            ('deployed-at', 'recorded deployment timestamp, if known'),
        ):
            compare.add_argument(f'--{side}-{field}', help=help_text)
    replay = commands.add_parser('replay', help='replace one generated-file difference and compare fresh Hugo builds')
    replay.add_argument('report', help='projection/assembly comparison name')
    replay.add_argument('finding', help='exact finding ID; all other semantic changes must be absent from the file')
    options(replay, replace=False)
    replay.add_argument('--assembly', required=True, type=Path, help='retained right-side Hugo input tree')
    replay.add_argument('--name', required=True, help='new rendering report name; outputs retained beside it')
    replay.add_argument('--base-url', default='/')
    for parser in (compare, replay):
        parser.add_argument('--heuristic', type=Path, help='trusted Python classification heuristic with ordered RULES')
    replay.add_argument('--flavor', choices=('upstream', 'lite'), default='lite', help='same rendering operation used for every replay build')


def report_output(root, name):
    if Path(name).name != name or name in {'.', '..'}:
        raise ConfigurationError('Report name must be a single directory name')
    output = root / 'reports' / name
    if output.exists():
        raise ConfigurationError(f'Report already exists: {output}; choose a new --name')
    return output


def execute(args, root):
    from .diagnostics import explicit_path, report_paths
    from .site_compare import compare_trees
    output = report_output(root, args.name)
    if args.review_command == 'compare':
        left, right = explicit_path(args, args.left), explicit_path(args, args.right)
        if args.stage == 'storage':
            from .upstream_snapshot import load_jsonl
            from .record_stages import compare_records
            findings = compare_records(load_jsonl(left), load_jsonl(right))
            comparator = 'records-v1'
            scope = {'complete': True, 'selection': 'all records', 'all_subjects': True, 'all_locations': True}
        else:
            findings, names = compare_trees(left, right, rendered=args.stage == 'rendering')
            comparator = 'site-files/1' if args.stage == 'rendering' else 'content-files/1'
            scope = {'complete': True, 'subjects': names, 'all_locations': True}
        scope['experiment'] = getattr(args, 'experiment', 'snapshot')
        if args.check_links and args.stage != 'rendering':
            raise ConfigurationError('--check-links requires --stage rendering')
        if args.check_links:
            report_output(root, args.name + '-checks')
        from .stage_reports import operation_receipt
        receipts = {side: operation_receipt(path, allow_failed=True) for side, path in [('left', left), ('right', right)]}
        targets = {side: {field: getattr(args, f'{side}_{field}') for field in
                         ('label', 'url', 'branch_url', 'revision', 'captured_at', 'deployed_at')
                         if getattr(args, f'{side}_{field}') is not None}
                   for side in ('left', 'right')}
        for side in ('left', 'right'):
            retained = (receipts[side] or {}).get('context', {}).get('target', {})
            targets[side] = {**retained, **targets[side]}
            targets[side].setdefault('label', 'Reference output' if side == 'left' else 'Candidate output')
        captures = {side: r['context']['capture'] for side, r in receipts.items() if r and 'capture' in r['context']}
        scope['captures'] = captures
        if captures:
            scope['complete'] = False
            scope['selection'] = 'Retained capture files only; missing files may be outside capture coverage'
        evidence = {}
        for side, source in [('left', left), ('right', right)]:
            if side in captures:
                for suffix in ('http.warc.gz', 'http.cdx', 'wget.log'):
                    candidate = source.parent / suffix
                    if candidate.is_file():
                        evidence[side + '-' + suffix.replace('.', '-')] = candidate
        incomplete = any((r or {}).get('context', {}).get('status') == 'failed' for r in receipts.values())
        report = write_report(output, stage=args.stage, left=left, right=right, findings=findings,
                              comparator=comparator, scope=scope, mode=args.mode, targets=targets,
                              status='failed' if incomplete else 'complete', evidence=evidence,
                              diagnostics=['Capture retrieval was incomplete; inspect retained HTTP evidence.'] if incomplete else [],
                              command=getattr(args, 'invocation', []))
        if args.check_links:
            from .site_compare import check_site, finding
            from urllib.parse import urlsplit
            checked = []
            scopes = []
            for path, url in [(left, args.left_base_url), (right, args.right_base_url)]:
                problems, scope = check_site(path, base_url=url)
                prefix = urlsplit(scope['base_url']).path
                def key(problem):
                    link = problem['location'][1]
                    # Only strip the known local mount, preserving the actual link in evidence.
                    if link.startswith(prefix):
                        link = '/' + link[len(prefix):]
                    return problem['subject'], link
                checked.append({key(p): p for p in problems})
                scopes.append(scope)
            problems = []
            for key in sorted(checked[0].keys() | checked[1].keys()):
                before, after = checked[0].get(key), checked[1].get(key)
                row = finding(key[0], ['links', key[1]], before, after)
                row['problem_status'] = 'existing' if before and after else 'introduced' if after else 'resolved'
                problems.append(row)
            write_report(root / 'reports' / (args.name + '-checks'), stage='site-check',
                         left=left, right=right, findings=problems, comparator='paired-local-html-targets/1',
                         scope={'complete': not bool(captures), 'checks': scopes}, mode=args.mode, targets=targets,
                         status='failed' if incomplete else 'complete',
                         command=getattr(args, 'invocation', []))
    else:
        source = report_paths(root, [args.report])[0]
        report = replay(source, args.finding, explicit_path(args, args.assembly), output,
                        base_url=args.base_url, flavor=args.flavor, workspace_root=args.root or Path.cwd(),
                        command=getattr(args, 'invocation', []))
    from .stage_review import summarize, load_decisions
    from .stage_presentation import render_rows
    result = summarize([output], load_decisions(None))
    from .stage_patterns import classifications, load_heuristic
    selected = getattr(args, 'heuristic', None)
    heuristic = load_heuristic(explicit_path(args, selected) if selected else None)
    classified = classifications([(report, output)], heuristic)
    for row in result['findings']:
        row['classification'] = classified[row['key']]
    stages = {f"{report['run_id']}/{f['id']}": (s, output) for s in report['stages'] for f in s['findings']}
    print(render_rows(result['findings'], stages) or 'No differences.')
    if args.review_command == 'replay':
        print('No downstream effect observed in replay.' if not report['stages'][0]['findings'] else
              'Downstream differences observed; inspect the replay report.')
    if report['stages'][0]['status'] != 'complete':
        print('Incomplete capture: differences describe retained files only; inspect HTTP evidence.')
    print(f'Report: {output}')
    if args.review_command == 'compare' and args.check_links:
        from collections import Counter
        print('Possible problems: ' + canonical(dict(Counter(p['problem_status'] for p in problems))))
        print(f"Checks report: {root / 'reports' / (args.name + '-checks')}")
    return int(bool(report['stages'][0]['findings']))


def replay(source, finding_id, assembly, output, *, base_url, flavor, workspace_root, command=None):
    from .site_compare import compare_trees
    from .site import build_hugo
    from .config import load_workspace
    from .resources import resolve_resources
    report, root = load_report(source)
    selected = [(stage, f) for stage in report['stages'] for f in stage['findings'] if f['id'] == finding_id]
    if len(selected) != 1:
        raise ConfigurationError('Select exactly one finding from the source report')
    stage, finding = selected[0]
    if stage['stage'] not in {'projection', 'assembly'} or stage['status'] != 'complete':
        raise ConfigurationError('Replay requires a completed projection or assembly comparison')
    subject = finding['subject']
    sides = {side: safe_artifact(safe_artifact(root, stage['artifacts'][side]['path']), subject)
             for side in ('left', 'right')}
    if not all(p.is_file() for p in sides.values()):
        raise ConfigurationError('This replay requires a file present on both sides')
    semantic = [f for f in stage['findings'] if f['subject'] == subject and f['location'][:1] != ['bytes']]
    if len(semantic) != 1 or semantic[0]['id'] != finding_id:
        raise ConfigurationError('Select the sole semantic change in this file; a whole-file swap would not isolate this finding')
    actual, _ = compare_trees(safe_artifact(root, stage['artifacts']['left']['path']),
                              safe_artifact(root, stage['artifacts']['right']['path']), subjects=[subject])
    actual_semantic = [f for f in actual if f['location'][:1] != ['bytes']]
    fields = ('location', 'before', 'after', 'before_present', 'after_present')
    if len(actual_semantic) != 1 or any(canonical(actual_semantic[0][key]) != canonical(finding[key]) for key in fields):
        raise ConfigurationError('The selected finding does not describe the retained file difference')
    baseline_file = safe_artifact(assembly, subject)
    if not baseline_file.is_file() or artifact_digest(baseline_file) != artifact_digest(sides['right']):
        raise ConfigurationError('Assembly file must equal the comparison’s right-side file')
    work = output.with_name(output.name + '-replay')
    if work.exists() or output.exists() or assembly.resolve() in work.resolve().parents:
        raise ConfigurationError('Replay needs a fresh output outside the supplied assembly')
    # Validate the source tree before copying; never follow symlinks into other inputs.
    artifact_digest(assembly)
    work.mkdir(parents=True)
    baseline, variant = work / 'baseline-input', work / 'variant-input'
    shutil.copytree(assembly, baseline)
    shutil.copytree(assembly, variant)
    shutil.copyfile(sides['left'], safe_artifact(variant, subject))
    workspace = load_workspace(Path(workspace_root))
    resources = resolve_resources().root
    for name, inputs in [('baseline', baseline), ('repeat', baseline), ('variant', variant)]:
        destination = work / name
        build_hugo(workspace, resources, inputs, destination, base_url, flavor=flavor)
        write_operation(destination, operation='review-replay-build', inputs={'assembly': inputs},
                        context={'flavor': flavor, 'base_url': base_url}, command=command)
    if artifact_digest(work / 'baseline') != artifact_digest(work / 'repeat'):
        raise ConfigurationError(f'Unchanged-input builds differ; replay is inconclusive. Evidence: {work}')
    findings, names = compare_trees(work / 'baseline', work / 'variant', rendered=True)
    return write_report(output, stage='rendering', left=work / 'baseline', right=work / 'variant',
                        findings=findings, comparator='site-files/1', mode='isolated',
                        scope={'complete': True, 'subjects': names, 'all_locations': True,
                               'replay': {'origin': f"{report['run_id']}/{finding_id}",
                                          'report_digest': json_digest(report), 'subject': subject,
                                          'direction': 'right file replaced with left file'}},
                        targets={'left': {'label': 'Unchanged right-side assembly'},
                                 'right': {'label': 'Right-side assembly with selected left-side value'}},
                        evidence={'baseline-input': baseline, 'variant-input': variant,
                                  'repeat': work / 'repeat'}, command=command)


def effects(reports):
    """Check the retained replay against the selected origin and operation receipts."""
    origins = {f"{r['run_id']}/{f['id']}": (r, s, f, root)
               for r, root in reports for s in r['stages'] for f in s['findings']}
    result = {}
    for report, root in reports:
        for stage in report['stages']:
            replay = stage['scope'].get('replay')
            if not isinstance(replay, dict) or replay.get('origin') not in origins:
                continue
            origin_report, origin_stage, finding, origin_root = origins[replay['origin']]
            if replay.get('report_digest') != json_digest(origin_report) or stage['status'] != 'complete':
                continue
            artifacts = stage['artifacts']
            if not {'baseline-input', 'variant-input', 'repeat', 'left', 'right'} <= artifacts.keys():
                continue
            baseline = safe_artifact(root, artifacts['baseline-input']['path'])
            variant = safe_artifact(root, artifacts['variant-input']['path'])
            from .site_compare import compare_trees
            changes, _ = compare_trees(baseline, variant)
            semantic = [f for f in changes if f['location'][:1] != ['bytes']]
            origin_changes = [f for f in origin_stage['findings'] if f['subject'] == finding['subject'] and f['location'][:1] != ['bytes']]
            if len(semantic) != 1 or len(origin_changes) != 1 or origin_changes[0]['id'] != finding['id']:
                continue
            delta = semantic[0]
            if (delta['location'] != finding['location'] or canonical(delta['before']) != canonical(finding['after'])
                    or canonical(delta['after']) != canonical(finding['before'])):
                continue
            if any(f['subject'] != finding['subject'] for f in changes):
                continue
            if any(artifact_digest(safe_artifact(inputs, finding['subject'])) != artifact_digest(
                    safe_artifact(safe_artifact(origin_root, origin_stage['artifacts'][side]['path']), finding['subject']))
                   for inputs, side in [(baseline, 'right'), (variant, 'left')]):
                continue
            ops = [artifacts[side].get('operation') or {} for side in ('left', 'right', 'repeat')]
            if not all(op.get('operation') == 'review-replay-build' for op in ops):
                continue
            if len({canonical(op.get('context')) for op in ops}) != 1:
                continue
            if any(op.get('inputs') != {'assembly': {'digest': artifacts[role]['digest'], 'producer': None}}
                   for op, role in zip(ops, ('baseline-input', 'variant-input', 'baseline-input'))):
                continue
            if artifacts['repeat']['digest'] != artifacts['left']['digest']:
                continue
            unchanged = artifacts['left']['digest'] == artifacts['right']['digest']
            result.setdefault(replay['origin'], []).append({
                'run_id': report['run_id'], 'stage': stage['stage'],
                'conclusion': 'No downstream effect observed in replay.' if unchanged else 'Verified downstream effect in replay.',
                'scope': 'Selected file substitution through the same renderer; repeated baseline agrees.',
                'status': 'no-effect' if unchanged else 'verified',
            })
    return result
