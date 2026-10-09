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
        return [block.name for block in self.blocks
                if block.execute(cwd=cwd, environment=environment, stdout=stdout)]


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


def adjust_for_lite(pipeline: Pipeline) -> Pipeline:
    """Apply text adjustments while preserving upstream blocks and order."""
    adjusted = []
    for block in pipeline.blocks:
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
    args = parser.parse_args(argv)
    try:
        pipeline = parse_workflow(args.workflow, job=args.job)
        if not args.upstream:
            pipeline = adjust_for_lite(pipeline)
        if getattr(args, 'names', None):
            pipeline = pipeline.chain(*args.names)
        if args.command == 'list':
            for block in pipeline.blocks:
                print(block.heading)
        elif args.command == 'show':
            if args.json:
                print(json.dumps([{
                    'number': block.number, 'name': block.name, 'uses': block.uses, 'raw': block.raw,
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
