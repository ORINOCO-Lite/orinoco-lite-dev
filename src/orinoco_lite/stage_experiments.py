"""Questions and experimental controls shared by CLI and browser review."""
from copy import deepcopy
import shlex

# These describe operations, not a scheduler or an acceptance policy.
EXPERIMENTS = {
    'snapshot': {
        'question': 'What differs between these retained outputs?',
        'fixed': 'Nothing is assumed equal unless recorded in the inputs.',
        'varied': 'The two selected outputs, including their software and data.',
        'requires': 'Two retained files or trees and their comparison scope.',
        'establishes': 'Observed differences within the retained coverage.',
        'limits': 'Does not identify which software or input change caused a difference.',
        'prepare': 'Select the outputs to compare; capture live sites first if necessary.',
    },
    'software-change': {
        'question': 'What changes when the software changes?',
        'fixed': 'Captured records, authored site inputs, and relevant execution settings.',
        'varied': 'The selected software revision, including its dependency selections.',
        'requires': 'Both software selections, the same retained inputs, and their outputs.',
        'establishes': 'The observed effect of the software update for these inputs.',
        'limits': 'Does not establish compatibility with every downstream or attribute the effect to one patch.',
        'prepare': 'Build the same retained inputs with each software selection using the ordinary build commands.',
    },
    'input-change': {
        'question': 'What changes when the data changes?',
        'fixed': 'Software selection and relevant execution settings.',
        'varied': 'The selected records or authored site inputs.',
        'requires': 'One software selection, both input revisions, and their outputs.',
        'establishes': 'The observed effect of the input update under the selected software.',
        'limits': 'Incompatible inputs prevent this experiment; they do not constitute agreement.',
        'prepare': 'Build each input revision with the same software selection.',
    },
    'selected-change': {
        'question': 'Does this selected change explain a later difference?',
        'fixed': 'Renderer, other assembly inputs, and deployment settings.',
        'varied': 'One generated file with a single semantic change.',
        'requires': 'A completed projection or assembly finding and its matching right-side assembly.',
        'establishes': 'The effect of that substitution, after checking an unchanged baseline.',
        'limits': 'The built-in replay tests one file; interactions or patch removal need a separately retained experiment.',
        'prepare': 'Select the sole semantic change in a file. For patch removal, retain a script that builds with and without the patch while holding the other inputs fixed.',
    },
    'repeat': {
        'question': 'Does repeated execution produce different outputs?',
        'fixed': 'Software, input bytes, and controllable execution settings.',
        'varied': 'Execution instance.',
        'requires': 'Two independently generated outputs from unchanged selections.',
        'establishes': 'Whether variation occurred in these repetitions.',
        'limits': 'Agreement in a finite number of runs does not prove determinism.',
        'prepare': 'Run the same producing command into separate fresh output directories.',
    },
    'downstream-update': {
        'question': 'Can this existing downstream adopt the update?',
        'fixed': 'The downstream starting state and its intended content.',
        'varied': 'Software and any explicit migration required by the supported update path.',
        'requires': 'An existing downstream, the candidate selection, migration steps if needed, validation and build results.',
        'establishes': 'Compatibility and observed changes for this downstream and update path.',
        'limits': 'A website comparison alone does not establish record preservation or successful validation.',
        'prepare': 'Apply the update in a disposable copy; retain record comparisons, validation outcomes, and ordinary build outputs.',
    },
}


def experiment_kind(stage):
    if stage.get('scope', {}).get('replay'):
        return 'selected-change'
    return stage.get('scope', {}).get('experiment', 'snapshot')


def comparison_purpose(stage):
    result = deepcopy(EXPERIMENTS.get(experiment_kind(stage), EXPERIMENTS['snapshot']))
    result['basis'] = 'Declared experiment design; inspect inputs and commands to establish that its controls were met.'
    if stage.get('mode') == 'isolated':
        result['limits'] += ' This isolated-stage comparison does not establish complete-path agreement.'
    if stage.get('scope', {}).get('captures'):
        result['limits'] += ' Live captures cover retained routes and assets only.'
    return result


def guidance(stages=(), *, directory='sourcedata', report='REPORT', finding='FINDING'):
    result = []
    for name, spec in EXPERIMENTS.items():
        supplied = [s for s in stages if experiment_kind(s) == name]
        states = {s['status'] for s in supplied}
        status = ('not run in this review' if not supplied else 'failed' if 'failed' in states
                  else 'skipped' if 'skipped' in states else 'completed')
        if name == 'selected-change':
            command = ['orinoco-lite', 'dev', 'review', 'replay', report, finding,
                       '--directory', str(directory), '--assembly', 'ASSEMBLY', '--name', 'NEW_NAME']
        else:
            command = ['orinoco-lite', 'dev', 'review', 'compare', 'LEFT', 'RIGHT',
                       '--directory', str(directory), '--name', 'NEW_NAME', '--experiment', name]
        result.append({'id': name, **spec, 'status': status, 'command': command,
                       'command_text': shlex.join(command),
                       'command_note': 'Replace uppercase placeholders. The compare command consumes prepared outputs; it does not perform the preceding experiment.',
                       'status_note': 'Status describes supplied comparison runs; it does not verify that the experimental controls were met.',
                       'reports': [{'run_id': s.get('run_id'), 'stage': s['stage'], 'status': s['status']} for s in supplied]})
    return result


def render_guidance(items):
    lines = []
    for item in items:
        lines.extend([f"{item['id']}: {item['question']} [{item['status']}]"])
        for label, key in [('Hold fixed', 'fixed'), ('Change', 'varied'), ('Requires', 'requires'),
                           ('What it establishes', 'establishes'), ('Limits', 'limits'), ('Prepare', 'prepare')]:
            lines.append(f"  {label}: {item[key]}")
        lines.extend([f"  Command: {item['command_text']}", f"  {item['command_note']}", f"  {item['status_note']}", ''])
    return '\n'.join(lines)
