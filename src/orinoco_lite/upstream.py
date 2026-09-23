"""Commands for acquiring inputs from the selected upstream."""

from pathlib import Path
import subprocess

from .pool_capture import DEFAULT_API
from .diagnostics import explicit_path
from .errors import ConfigurationError
from .presentation import resolve_presentation
from .resources import resolve_resources
from .site_inputs import import_site_inputs


def register(commands):
    upstream = commands.add_parser("upstream", help="import and record inputs for upstream comparison")
    groups = upstream.add_subparsers(dest="upstream_command", required=True)
    export = groups.add_parser("import-from-www", description=(
        "Create or refresh an upstream-derived site-input dataset for repinning, testing, "
        "and comparison with Orinoco Lite. "
        "Map upstream Hugo settings into site.yaml and copy authored content, identity images, "
        "and site overrides from the installed package's pinned www-from-model revision. "
        "Retrieve upstream Annex media as ordinary site files. Imported content/assets/static "
        "are synchronized, including deletions; metadata is preserved."))
    export.add_argument("--source", type=Path, help="upstream website checkout (default: package-selected presentation)")
    export.add_argument("--media-remote", help="Annex source Git URL (default: upstream host for package-selected www; existing remotes with --source)")
    export.add_argument("--revision", help="require this Git revision at the source checkout's HEAD")
    export.add_argument("--destination", type=Path, help="site-input directory (default: site-specific)")
    populate = groups.add_parser("populate", description=(
        "Record acquisition, record conversion, and site import as separate DataLad runs. "
        "Use --snapshot to retain a supplied capture, or --reuse-capture to transform "
        "the retained Pool records without refetching them; site and media import still runs. "
        "Run individual record or import commands to repeat only that stage. Does not build, compare, or deploy."))
    populate.add_argument("--directory", type=Path, default=Path("sourcedata"), help="capture directory (default: sourcedata)")
    populate.add_argument("--destination", type=Path, default=Path("site-specific"), help="site-input directory (default: site-specific)")
    acquisition = populate.add_mutually_exclusive_group()
    acquisition.add_argument("--snapshot", type=Path, help="retain this JSONL capture instead of fetching")
    acquisition.add_argument("--reuse-capture", action="store_true", help="reuse DIRECTORY/downloaded/records.jsonl (must be committed and unchanged) without refetching Pool records; still import site files")
    populate.add_argument("--api", default=DEFAULT_API, help="public Dump Things API for acquisition")
    populate.add_argument("--site-layout", choices=("submodule", "directory"), default="submodule", help="storage for a new site-input directory; existing layout is preserved")
    populate.add_argument("--site-specific", type=Path, help="install this existing dataset as a submodule; skip capture and imports")



def execute(args):
    root = (args.root or Path.cwd()).resolve()
    if args.upstream_command == "populate":
        # Public operations are recorded by the shared Bash workflow, not here.
        # Store paths relative to the dataset, even when callers supply absolutes.
        import os
        def relative(path):
            return os.path.relpath(explicit_path(args, path), root)
        command = ["orinoco-lite-populate-upstream.sh",
                   "--directory", relative(args.directory), "--destination", relative(args.destination),
                   "--api", args.api, "--site-layout", args.site_layout]
        if args.snapshot:
            command.extend(["--snapshot", relative(args.snapshot)])
        if args.reuse_capture:
            command.append("--reuse-capture")
        if args.site_specific:
            if args.snapshot or args.reuse_capture:
                raise ConfigurationError("Choose --site-specific or a capture input, not both.")
            command.extend(["--site-specific", relative(args.site_specific)])
        return subprocess.run(command, cwd=root).returncode
    source = (explicit_path(args, args.source) if args.source else
              resolve_presentation(root, resolve_resources().root))
    def git(*arguments):
        result = subprocess.run(["git", "-C", str(source), *arguments], capture_output=True, text=True)
        if result.returncode:
            raise ConfigurationError(f"Cannot export upstream site: {result.stderr.strip() or 'source files differ from HEAD'}")
        return result.stdout.strip()
    revision = git("rev-parse", "HEAD")
    if args.revision and git("rev-parse", f"{args.revision}^{{commit}}") != revision:
        raise ConfigurationError("Upstream site checkout does not match --revision")
    git("diff", "--exit-code", "HEAD", "--", "config", "content", "assets", "static")
    destination = (explicit_path(args, args.destination) if args.destination else
                   root / "site-specific")
    if (destination.resolve() == source.resolve()
            or destination.resolve().is_relative_to(source.resolve())
            or source.resolve().is_relative_to(destination.resolve())):
        raise ConfigurationError("Site export destination must not overlap the upstream checkout")
    print(f"Upstream site: {source}\nCommit: {revision}\nDestination: {destination}")
    media_remote = args.media_remote or (None if args.source else "https://hub.psychoinformatics.de/www/www-from-model.git")
    result = import_site_inputs(source, destination, retrieve_media=True, media_remote=media_remote)
    print(f"Exported {result['files']} site files; metadata was preserved.")
    return 0
