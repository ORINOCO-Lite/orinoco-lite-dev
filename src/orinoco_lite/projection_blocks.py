"""Inspect and execute named shell blocks from the selected upstream workflow.

A Pipeline is an ordered sequence of blocks, not a pipe between blocks.
Each block runs in a separate Bash process, as a workflow run step does.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys


WORKFLOW = Path('submodules/www-from-model/.forgejo/workflows/update-from-pool.yaml')


@dataclass(frozen=True)
class Adjustment:
    reason: str
    before: str
    after: str

    def diff(self, name: str) -> str:
        return _diff(self.before, self.after, f'{name}: before', f'{name}: after')


def _diff(before: str, after: str, before_name: str, after_name: str) -> str:
    if before == after:
        return '(unchanged)\n'
    return ''.join(difflib.unified_diff(
        [line + '\n' for line in before.splitlines()],
        [line + '\n' for line in after.splitlines()],
        fromfile=before_name, tofile=after_name,
    ))


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
        return _diff(self.raw, self.adjusted, f'{self.name}: raw', f'{self.name}: adjusted')

    def display(self, view: str = 'all') -> str:
        views = ('raw', 'adjustments', 'adjusted', 'diff') if view == 'all' else (view,)
        sections = [f'=== {self.name} ===']
        if self.uses:
            sections.append(f'uses: {self.uses} (no shell block)')
        for current in views:
            if current == 'adjustments':
                text = ''.join(
                    f'{i}. {item.reason}\n{item.diff(self.name)}'
                    for i, item in enumerate(self.adjustments, 1)
                ) or '(none)\n'
            elif current == 'diff':
                text = self.diff()
            elif current in ('raw', 'adjusted'):
                text = getattr(self, current) or '(empty)\n'
            else:
                raise ValueError(f'Unknown view: {current}')
            sections.append(f'[{current}]\n{text.rstrip()}')
        return '\n'.join(sections) + '\n'

    def __repr__(self) -> str:
        return self.display()

    def execute(self, *, cwd: Path, environment: dict[str, str] | None = None) -> bool:
        """Run adjusted shell text; return False for an empty block."""
        if not self.adjusted.strip():
            return False
        print(f'Executing {self.name}...', file=sys.stderr, flush=True)
        env = os.environ.copy()
        if environment:
            env.update(environment)
        try:
            subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', self.adjusted],
                           cwd=cwd, env=env, check=True)
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
        names = [block.name for block in self.blocks]
        if len(set(names)) != len(names):
            raise ValueError('Block names must be unique')

    def chain(self, *names: str) -> Pipeline:
        """Select and order blocks explicitly by name, before any execution."""
        blocks = {block.name: block for block in self.blocks}
        unknown = [name for name in names if name not in blocks]
        if unknown:
            raise ValueError(f'Unknown block name: {unknown[0]}')
        return Pipeline(tuple(blocks[name] for name in names))

    def execute(self, *, cwd: Path, environment: dict[str, str] | None = None) -> list[str]:
        """Execute in order with shared files; stop at the first failure."""
        return [block.name for block in self.blocks
                if block.execute(cwd=cwd, environment=environment)]


def parse_workflow(path: Path, *, job: str = 'create_pages') -> Pipeline:
    import yaml
    try:
        steps = yaml.safe_load(path.read_text())['jobs'][job]['steps']
    except (KeyError, TypeError, yaml.YAMLError) as error:
        raise ValueError(f'{path}: cannot read steps for job {job}') from error
    if not isinstance(steps, list):
        raise ValueError(f'{path}: steps must be a list')
    blocks = []
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get('name'), str) or not step['name'].strip():
            raise ValueError(f'{path}: every step needs a nonempty name')
        raw = step.get('run', '')
        uses = step.get('uses')
        if not isinstance(raw, str) or (uses is not None and not isinstance(uses, str)):
            raise ValueError(f'{step["name"]}: run and uses must be text')
        blocks.append(CodeBlock(step['name'], raw, uses=uses))
    return Pipeline(tuple(blocks))


# Names make the selected workflow order and every Lite adjustment inspectable.
# Page selection and pipeline commands remain in the upstream file.
LITE_BLOCKS = (
    'Checkout project', 'Prepare environment', 'git-annex init',
    'Update navigation graph', 'Install jq', 'Identify project members',
    'Update objectives', 'Update topics', 'Update persons', 'Update projects',
    'Update publications', 'Update instruments', 'Update datasets',
    'Update frontpage', 'Deposit changes', 'Deposit annex keys',
)


def adjust_for_lite(pipeline: Pipeline) -> Pipeline:
    ordered = pipeline.chain(*LITE_BLOCKS)
    extra = set(block.name for block in pipeline.blocks) - set(LITE_BLOCKS)
    if extra:
        raise ValueError(f'Unreviewed upstream block: {sorted(extra)[0]}')
    adjusted = []
    for block in ordered.blocks:
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workflow', type=Path, default=WORKFLOW,
                        help=f'upstream YAML file (default: {WORKFLOW})')
    parser.add_argument('--job', default='create_pages')
    parser.add_argument('--upstream', action='store_true',
                        help='inspect unadjusted blocks; run also includes setup and publishing commands')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list', help='list block names in execution order')
    show = commands.add_parser('show', help='show block text and changes; defaults to all blocks and states')
    show.add_argument('names', nargs='*', help='exact block names, in the requested order')
    show.add_argument('--view', choices=('raw', 'adjustments', 'adjusted', 'diff', 'all'), default='all')
    show.add_argument('--json', action='store_true', help='emit block states and adjustment history as JSON')
    run = commands.add_parser('run', help='execute adjusted shell in a prepared directory; empty blocks are skipped')
    run.add_argument('names', nargs='*', help='exact block names; defaults to the complete named chain')
    run.add_argument('--cwd', type=Path, required=True,
                     help='prepared directory with code/, page_templates/, content/, static/; '
                          'set DUMPTHINGS_APIURL and QRI_RECORD_CACHE in the environment')
    args = parser.parse_args(argv)
    try:
        pipeline = parse_workflow(args.workflow, job=args.job)
        if not args.upstream:
            pipeline = adjust_for_lite(pipeline)
        if getattr(args, 'names', None):
            pipeline = pipeline.chain(*args.names)
        if args.command == 'list':
            for block in pipeline.blocks:
                print(block.name)
        elif args.command == 'show':
            if args.json:
                print(json.dumps([{
                    'name': block.name, 'uses': block.uses, 'raw': block.raw,
                    'adjusted': block.adjusted, 'diff': block.diff(),
                    'adjustments': [dict(reason=a.reason, before=a.before, after=a.after)
                                    for a in block.adjustments],
                } for block in pipeline.blocks], ensure_ascii=False, indent=2))
            else:
                for block in pipeline.blocks:
                    print(block.display(args.view), end='')
        else:
            pipeline.execute(cwd=args.cwd.resolve())
        sys.stdout.flush()
        return 0
    except BlockExecutionError as error:
        print(f'projection-blocks: {error}', file=sys.stderr)
        return error.returncode if error.returncode > 0 else 128 - error.returncode
    except BrokenPipeError:
        with open(os.devnull, 'w') as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())
        return 1
    except (OSError, ValueError) as error:
        print(f'projection-blocks: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
