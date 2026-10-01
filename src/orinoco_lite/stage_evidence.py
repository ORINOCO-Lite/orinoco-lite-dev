"""Browse a saved overview or materialize an explicitly selected evidence bundle."""
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import tempfile

from .errors import ConfigurationError
from .progress import progress
from .stage_reports import read_json


def annex_content(path):
    """Resolve only a path Git Annex recognizes; never follow arbitrary links."""
    parent = path.parent
    for candidate in (parent, *parent.parents):
        if candidate.is_symlink():
            raise ConfigurationError(f'Evidence directory cannot be a symbolic link: {candidate}')
    if not path.is_symlink():
        if not path.is_file():
            raise ConfigurationError(f'Evidence file is unavailable: {path}')
        return path
    key = subprocess.run(['git', '-C', str(parent), 'annex', 'lookupkey', '--', path.name],
                         text=True, capture_output=True)
    if key.returncode or not key.stdout.strip():
        raise ConfigurationError(f'Evidence link is not a Git Annex file: {path}')
    location = subprocess.run(['git', '-C', str(parent), 'annex', 'contentlocation', key.stdout.strip()],
                              text=True, capture_output=True)
    if location.returncode or not location.stdout.strip():
        raise ConfigurationError(f'Annex content is not available locally: {path}. Retrieve it with datalad get or materialize --get.')
    content = (parent / location.stdout.strip()).resolve()
    if not content.is_file() or path.resolve() != content:
        raise ConfigurationError(f'Evidence link differs from its Annex content: {path}')
    return content


@progress('Materializing review evidence')
def materialize(source, destination, *, get=False):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    if source.is_symlink() or not source.is_dir():
        raise ConfigurationError('Select an ordinary bundle directory in the evidence dataset')
    if destination.exists() or destination.is_symlink() or source.resolve() in destination.resolve().parents or destination.resolve() in source.resolve().parents:
        raise ConfigurationError('Materialization requires a fresh output outside the evidence source')
    source = source.resolve()
    if get:
        completed = subprocess.run(['datalad', 'get', '--', str(source)], cwd=source)
        if completed.returncode:
            raise ConfigurationError('DataLad could not retrieve the selected bundle')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.review-materialize-', dir=destination.parent) as temp:
        target = Path(temp) / 'bundle'
        target.mkdir()
        for entry in sorted(source.rglob('*')):
            relative = entry.relative_to(source)
            if '.git' in relative.parts:
                continue
            if entry.is_symlink() and entry.is_dir():
                raise ConfigurationError(f'Evidence directory cannot be a symbolic link: {entry}')
            if entry.is_dir():
                (target / relative).mkdir(parents=True, exist_ok=True)
            else:
                output = target / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(annex_content(entry), output)
        from .stage_bundle import ReviewModel
        ReviewModel(target)  # Verify original artifacts and decisions before publishing output.
        target.rename(destination)
    return destination


class ReviewOverview:
    """Saved, unverified metadata only; never exposes evidence or decision writes."""
    def __init__(self, directory):
        source = Path(directory) / 'overview.json'
        if source.is_symlink():
            raise ConfigurationError('Keep overview.json in ordinary Git to browse without Annex content')
        self.data = read_json(source)
        if not isinstance(self.data, dict) or not {'comparisons', 'stages', 'classification_counts', 'title'} <= self.data.keys():
            raise ConfigurationError('Invalid saved review overview; regenerate with review bundle')
        self.data.update(metadata_only=True, evidence_status='Saved overview only. Evidence has not been retrieved or verified in this session.')
        self.data['evidence_command'] = ['orinoco-lite', 'dev', 'review', 'materialize', str(Path(directory).absolute()), 'DESTINATION/bundle', '--get']

    def overview(self, comparison='', stage_filter=''):
        return deepcopy(self.data)

    def unavailable(self, *args, **kwargs):
        raise ConfigurationError('Saved overview only. Materialize the evidence and open a full review first.')

    findings = finding = original_files = original_file = artifact_root = annotation_artifact = decision = preview = unavailable
