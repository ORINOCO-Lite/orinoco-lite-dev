"""Inspect and execute named shell blocks from the selected upstream workflow.

A Pipeline is an ordered sequence of blocks, not a pipe between blocks.
Each block runs in a separate Bash process, as a workflow run step does.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys

from .errors import ConfigurationError

WORKFLOW = Path('.forgejo/workflows/update-from-pool.yaml')


@dataclass(frozen=True)
class Adjustment:
    reason: str
    before: str
    after: str

    def diff(self) -> str:
        return _diff(self.before, self.after)


def _diff(before: str, after: str) -> str:
    before_lines = [line + '\n' for line in before.splitlines()]
    after_lines = [line + '\n' for line in after.splitlines()]
    if before == after:
        return ''.join(' ' + line for line in before_lines) or '(empty)\n'
    # Keep the entire block as context, without synthetic file headers.
    lines = list(difflib.unified_diff(
        before_lines, after_lines, n=max(len(before_lines), len(after_lines)),
    ))
    return ''.join(lines[2:])


def _color_diff(text: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        shade = '\033[31m' if line.startswith('-') else '\033[32m' if line.startswith('+') else ''
        lines.append(shade + line.rstrip('\n') + '\033[0m' + ('\n' if line.endswith('\n') else '')
                     if shade else line)
    return ''.join(lines)


@dataclass(frozen=True, repr=False)
class CodeBlock:
    """A workflow step's run text and ordered text adjustments.

    A uses-only step has empty shell text; its action is not implemented here.
    Replacements return a new block and preserve the original text.
    """
    name: str
    raw: str
    adjustments: tuple[Adjustment, ...] = ()
    uses: str | None = None
    number: int | None = None
    skip_reason: str | None = None

    @property
    def adjusted(self) -> str:
        return self.adjustments[-1].after if self.adjustments else self.raw

    def replace(self, old: str, new: str, *, reason: str) -> CodeBlock:
        """Replace one exact occurrence; refuse missing or ambiguous text."""
        if not old or self.adjusted.count(old) != 1:
            raise ValueError(f'{self.name}: adjustment must match exactly once: {reason}')
        after = self.adjusted.replace(old, new, 1)
        return replace(self, adjustments=self.adjustments + (
            Adjustment(reason, self.adjusted, after),
        ))

    def diff(self) -> str:
        return _diff(self.raw, self.adjusted)

    def display(self, view: str = 'diff', *, color: bool = False) -> str:
        views = ('raw', 'adjustments', 'adjusted', 'diff') if view == 'all' else (view,)
        sections = [self.heading]
        if self.uses:
            sections.append(f'uses: {self.uses} (no shell block)')
        if self.skip_reason:
            sections.append(self.skip_reason)
        for current in views:
            if current == 'adjustments':
                text = ''.join(
                    f'{i}. {item.reason}\n{item.diff()}'
                    for i, item in enumerate(self.adjustments, 1)
                ) or '(none)\n'
            elif current == 'diff':
                text = self.diff()
            elif current in ('raw', 'adjusted'):
                text = getattr(self, current) or '(empty)\n'
            else:
                raise ValueError(f'Unknown view: {current}')
            if color and current in ('diff', 'adjustments'):
                text = _color_diff(text)
            sections.append(f'[{current}]\n{text.rstrip()}')
        return '\n'.join(sections) + '\n'

    @property
    def heading(self) -> str:
        prefix = f'{self.number}. ' if self.number is not None else ''
        return f'=== {prefix}{self.name} ==='

    def __repr__(self) -> str:
        return self.display()

    def execute(self, *, cwd: Path, environment: dict[str, str] | None = None, stdout=None) -> bool:
        """Run adjusted shell text; return False for an empty block."""
        if self.uses and not self.skip_reason:
            raise ValueError(f'{self.name}: action execution is unsupported: {self.uses}')
        if not self.adjusted.strip():
            return False
        print(f'Executing {self.name}...', file=sys.stderr, flush=True)
        env = os.environ.copy()
        if environment:
            env.update(environment)
        try:
            subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', self.adjusted],
                           cwd=cwd, env=env, stdout=stdout, check=True)
        except subprocess.CalledProcessError as error:
            raise BlockExecutionError(self.name, error.returncode) from error
        return True


class BlockExecutionError(RuntimeError):
    def __init__(self, name: str, returncode: int):
        super().__init__(f'{name}: shell exited with status {returncode}')
        self.returncode = returncode


@dataclass(frozen=True)
class Pipeline:
    blocks: tuple[CodeBlock, ...]

    def __post_init__(self):
        object.__setattr__(self, 'blocks', tuple(
            replace(block, number=i) if block.number is None else block
            for i, block in enumerate(self.blocks, 1)
        ))
        names = [block.name for block in self.blocks]
        if len(set(names)) != len(names):
            raise ValueError('Block names must be unique')

    def __getitem__(self, selector: str | int) -> CodeBlock:
        """Look up a name or stable one-based workflow number."""
        for block in self.blocks:
            if block.name == selector:
                return block
        number = int(selector) if str(selector).isdigit() else None
        for block in self.blocks:
            if number is not None and block.number == number:
                return block
        raise ValueError(f'Unknown block name or number: {selector}')

    def chain(self, *selectors: str | int) -> Pipeline:
        """Select and order blocks by name or one-based workflow number."""
        return Pipeline(tuple(self[selector] for selector in selectors))

    def execute(self, *, cwd: Path, environment: dict[str, str] | None = None, stdout=None) -> list[str]:
        """Execute in order with shared files; stop at the first failure."""
        for block in self.blocks:
            if block.uses and not block.skip_reason:
                raise ValueError(f'{block.name}: action execution is unsupported: {block.uses}')
        return [block.name for block in self.blocks
                if block.execute(cwd=cwd, environment=environment, stdout=stdout)]


def parse_workflow(path: Path, *, job: str = 'create_pages') -> Pipeline:
    import yaml
    try:
        document = yaml.safe_load(path.read_text())
        selected = document['jobs'][job]
        steps = selected['steps']
    except (KeyError, TypeError, yaml.YAMLError) as error:
        raise ValueError(f'{path}: cannot read steps for job {job}') from error
    if not isinstance(steps, list):
        raise ValueError(f'{path}: steps must be a list')
    # This is a shell-block adapter, not a Forgejo runner. Reject execution
    # semantics we cannot preserve before any command can write output.
    if ('defaults' in document or set(selected) - {'runs-on', 'if', 'steps'}
            or selected.get('if') not in (None, "${{ forgejo.repository == 'www/www-from-model' }}")):
        raise ValueError(f'{path}: unsupported workflow/job execution settings')
    environment = document.get('env', {})
    if not isinstance(environment, dict) or set(environment) - {'DUMPTHINGS_APIURL', 'QRI_RECORD_CACHE'}:
        raise ValueError(f'{path}: unsupported workflow environment; Lite supplies the Pool and cache')
    blocks = []
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get('name'), str) or not step['name'].strip():
            raise ValueError(f'{path}: every step needs a nonempty name')
        raw = step.get('run', '')
        uses = step.get('uses')
        if set(step) - {'name', 'run', 'uses'} or ('run' in step and 'uses' in step):
            raise ValueError(f'{step["name"]}: unsupported step execution settings')
        if not isinstance(raw, str) or (uses is not None and not isinstance(uses, str)):
            raise ValueError(f'{step["name"]}: run and uses must be text')
        if '${{' in raw:
            raise ValueError(f'{step["name"]}: workflow expressions are unsupported in shell blocks')
        blocks.append(CodeBlock(step['name'], raw, uses=uses))
    return Pipeline(tuple(blocks))


def adjust_for_lite(pipeline: Pipeline) -> Pipeline:
    """Apply text adjustments while preserving upstream blocks and order."""
    adjusted = []
    actions = {
        'actions/checkout@v4': 'Lite prepares the selected source in a scratch directory',
        'https://hub.psychoinformatics.de/orinoco/flow/forgejo/actions/prep-metadata-query@main':
            'The package environment supplies the pinned upstream commands',
        'https://hub.psychoinformatics.de/orinoco/flow/forgejo/actions/deposit-changes@main':
            'Projection produces local files; the caller owns publication',
    }
    for block in pipeline.blocks:
        if block.uses:
            if block.uses not in actions:
                raise ValueError(f'{block.name}: unsupported upstream action: {block.uses}')
            adjusted.append(replace(block, skip_reason=actions[block.uses]))
            continue
        if not block.raw.strip():
            adjusted.append(block)
            continue
        if block.name == 'git-annex init':
            block = block.replace(block.raw, '', reason='Lite projects into ordinary scratch files; no Annex initialization')
        elif block.name == 'Install jq':
            block = block.replace(block.raw, '', reason='The execution environment supplies jq')
        elif block.name == 'Deposit annex keys':
            block = block.replace(block.raw, '', reason='Projection does not publish Annex keys')
        elif block.name == 'Update navigation graph':
            block = block.replace(' \\\n&& git annex add static', '', reason='Keep graph generation; remove Annex storage')
        adjusted.append(block)
    return Pipeline(tuple(adjusted))


def read_adjustments(site: Path | None) -> list[dict[str, str]]:
    """Read only scoped adjustments; never load a second projection policy."""
    import yaml
    if site is None:
        return []
    path = site / 'projection.yaml'
    if not path.exists() and not path.is_symlink():
        return []
    try:
        value = yaml.safe_load(path.read_text())
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f'Cannot read projection adjustments: {path}') from error
    if (not isinstance(value, dict) or value.get('version') != 3
            or value.get('extends') != 'upstream'
            or set(value) - {'version', 'extends', 'adjustments'}):
        raise ConfigurationError(
            f'Unsupported projection override: {path}. Migrate the complete policy '
            'to version: 3, extends: upstream, and scoped adjustments; '
            'see docs/agents/projection-templates.md.'
        )
    adjustments = value.get('adjustments', [])
    if not isinstance(adjustments, list):
        raise ConfigurationError(f'{path}: adjustments must be a list')
    for item in adjustments:
        if (not isinstance(item, dict) or set(item) != {'step', 'old', 'new', 'reason'}
                or not all(isinstance(v, str) for v in item.values())
                or not all(item[key].strip() for key in ('step', 'old', 'reason'))):
            raise ConfigurationError(f'{path}: each adjustment needs step, old, new, and reason strings')
    return adjustments


def adjust_for_site(pipeline: Pipeline, site: Path | None) -> Pipeline:
    for item in read_adjustments(site):
        matches = [block for block in pipeline.blocks if block.name == item['step']]
        if len(matches) != 1 or not matches[0].adjusted.strip():
            raise ConfigurationError(f'Unknown or inactive projection step: {item["step"]}')
        try:
            changed = matches[0].replace(item['old'], item['new'], reason=item['reason'])
        except ValueError as error:
            raise ConfigurationError(str(error)) from error
        pipeline = Pipeline(tuple(changed if block.name == changed.name else block
                                  for block in pipeline.blocks))
    return pipeline


def load_pipeline(presentation: Path, site: Path | None = None) -> Pipeline:
    try:
        return adjust_for_site(adjust_for_lite(parse_workflow(presentation / WORKFLOW)), site)
    except (OSError, ValueError) as error:
        raise ConfigurationError(f'Cannot prepare upstream projection: {error}') from error


def register(commands) -> None:
    parser = commands.add_parser(
        'blocks', help='inspect or execute upstream projection shell blocks',
        description='Inspect the same upstream workflow and explicit adjustments used by projection. '
                    'Installed packages use the bundled workflow; editable installs use the selected '
                    'www-from-model submodule, including working edits. No site configuration is required.',
    )
    parser.add_argument('--workflow', type=Path,
                        help='inspect or run an explicit YAML file instead of the selected upstream workflow')
    parser.add_argument('--job', default='create_pages')
    parser.add_argument('--site', type=Path,
                        help='site-specific directory containing scoped projection.yaml adjustments')
    parser.add_argument('--upstream', action='store_true',
                        help='inspect unadjusted blocks; run also includes setup and publishing commands')
    commands = parser.add_subparsers(dest='blocks_command', required=True)
    commands.add_parser('list', help='list block names in execution order')
    show = commands.add_parser('show', help='show block text and changes; defaults to unified diffs for all blocks')
    show.add_argument('names', nargs='*', help='block names or one-based workflow numbers, in the requested order')
    show.add_argument('--view', choices=('raw', 'adjustments', 'adjusted', 'diff', 'all'), default='diff',
                      help='display state (diff is a unified raw-to-adjusted diff; default: diff)')
    show.add_argument('--color', choices=('auto', 'always', 'never'), default='auto',
                      help='red deletions and green additions (default: auto for terminals; respects NO_COLOR)')
    show.add_argument('--json', action='store_true', help='emit block states and adjustment history as JSON')
    run = commands.add_parser('run', help='execute adjusted shell in a prepared directory; empty blocks are skipped')
    run.add_argument('names', nargs='*', help='block names or one-based workflow numbers; defaults to workflow order')
    run.add_argument('--cwd', type=Path, required=True,
                     help='prepared directory with code/, page_templates/, content/, static/; '
                          'set DUMPTHINGS_APIURL and QRI_RECORD_CACHE in the environment')


def execute(args) -> int:
    try:
        if args.workflow is None:
            from .www_from_model import resolve_www_from_model
            workflow = resolve_www_from_model(args.root or Path.cwd()) / WORKFLOW
        else:
            workflow = args.workflow
        pipeline = parse_workflow(workflow, job=args.job)
        if args.site and args.upstream:
            raise ValueError('--site cannot be combined with --upstream; use --view raw to inspect the original')
        if not args.upstream:
            pipeline = adjust_for_site(adjust_for_lite(pipeline), args.site)
        if getattr(args, 'names', None):
            pipeline = pipeline.chain(*args.names)
        if args.blocks_command == 'list':
            for block in pipeline.blocks:
                print(block.heading)
        elif args.blocks_command == 'show':
            if args.json:
                print(json.dumps([{
                    'number': block.number, 'name': block.name, 'uses': block.uses, 'raw': block.raw,
                    'skip_reason': block.skip_reason,
                    'adjusted': block.adjusted, 'diff': block.diff(),
                    'adjustments': [dict(reason=a.reason, before=a.before, after=a.after)
                                    for a in block.adjustments],
                } for block in pipeline.blocks], ensure_ascii=False, indent=2))
            else:
                color = args.color == 'always' or (args.color == 'auto'
                        and sys.stdout.isatty() and 'NO_COLOR' not in os.environ
                        and os.environ.get('TERM') != 'dumb')
                for block in pipeline.blocks:
                    print(block.display(args.view, color=color), end='')
        else:
            pipeline.execute(cwd=args.cwd.resolve())
        sys.stdout.flush()
        return 0
    except BlockExecutionError as error:
        print(f'orinoco-lite projection blocks: {error}', file=sys.stderr)
        return error.returncode if error.returncode > 0 else 128 - error.returncode
    except BrokenPipeError:
        with open(os.devnull, 'w') as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())
        return 1
    except (OSError, ValueError, ConfigurationError) as error:
        print(f'orinoco-lite projection blocks: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
