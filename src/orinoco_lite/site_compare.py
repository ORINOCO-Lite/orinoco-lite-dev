"""Typed content, raw file, HTML and local-target checks for stage artifacts."""

from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import tomllib
from urllib.parse import unquote, urljoin, urlsplit

import yaml

from .errors import DriverError

MISSING = object()


class _FrontMatterLoader(yaml.SafeLoader):
    pass


_FrontMatterLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in entries
          if tag != "tag:yaml.org,2002:timestamp"]
    for key, entries in deepcopy(yaml.SafeLoader.yaml_implicit_resolvers).items()
}


def _same(before, after):
    if type(before) is not type(after):
        return False
    if isinstance(before, dict):
        return before.keys() == after.keys() and all(_same(before[key], after[key]) for key in before)
    if isinstance(before, list):
        return len(before) == len(after) and all(_same(a, b) for a, b in zip(before, after))
    return before == after



def finding(subject, location, before=MISSING, after=MISSING):
    return {"subject": subject, "location": location,
            "change": "added" if before is MISSING else "removed" if after is MISSING else "changed",
            "before": None if before is MISSING else before,
            "after": None if after is MISSING else after,
            "before_present": before is not MISSING, "after_present": after is not MISSING}


def values(subject, before, after, location):
    if _same(before, after):
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        return [change for key in sorted(before.keys() | after.keys(), key=str)
                for change in values(subject, before.get(key, MISSING), after.get(key, MISSING), [*location, str(key)])]
    # Arrays remain whole typed values: positions are order, not entity identity.
    return [finding(subject, location, before, after)]


def files(root: Path) -> dict[str, Path]:
    if root.is_symlink() or not root.is_dir():
        raise DriverError(f"Comparison input is not an ordinary directory: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            raise DriverError(f"Comparison artifact contains a symlink: {path}")
        if path.is_file():
            result[relative.as_posix()] = path
    return result


def _bytes(path):
    if path is None:
        return MISSING
    value = path.read_bytes()
    return {"sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)}


def markdown(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                frontmatter = yaml.load("".join(lines[1:index]), Loader=_FrontMatterLoader)
                # JSON-safe typed dates preserve their representation as YAML
                # strings; source bytes remain independently available.
                return frontmatter, "".join(lines[index + 1:])
        raise DriverError(f"Unclosed YAML front matter: {path}")
    return {}, text


class Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.ids = set()
        self.events = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if data.get("id"):
            self.ids.add(data["id"])
        if tag == "a" and data.get("name"):
            self.ids.add(data["name"])
        for attribute in ("href", "src", "poster"):
            if data.get(attribute):
                self.links.append(data[attribute])
        self.events.append(["start", tag, [[key, value] for key, value in attrs]])

    def handle_endtag(self, tag):
        self.events.append(["end", tag])

    def handle_data(self, data):
        self.events.append(["text", data])

    def handle_decl(self, decl):
        self.events.append(["declaration", decl])

    def handle_comment(self, comment):
        self.events.append(["comment", comment])


def html(path):
    parsed = Html()
    parsed.feed(path.read_text(encoding="utf-8"))
    parsed.close()
    return parsed


def compare_trees(left: Path, right: Path, *, rendered=False, subjects=None):
    old, new = files(left), files(right)
    names = sorted(set(old) | set(new)) if subjects is None else sorted(set(subjects))
    changes = []
    for name in names:
        before, after = old.get(name), new.get(name)
        changes.extend(values(name, _bytes(before), _bytes(after), ["bytes"]))
        if before is None or after is None or before.read_bytes() == after.read_bytes():
            continue
        try:
            if before.suffix.lower() == ".md":
                front_before, body_before = markdown(before)
                front_after, body_after = markdown(after)
                changes.extend(values(name, front_before, front_after, ["frontmatter"]))
                changes.extend(values(name, body_before, body_after, ["markdown"]))
            elif before.suffix.lower() == ".json":
                changes.extend(values(name, json.loads(before.read_text()), json.loads(after.read_text()), ["json"]))
            elif before.suffix.lower() in {".yaml", ".yml"}:
                changes.extend(values(name, yaml.load(before.read_text(), Loader=_FrontMatterLoader),
                                      yaml.load(after.read_text(), Loader=_FrontMatterLoader), ["yaml"]))
            elif before.suffix.lower() == ".toml":
                changes.extend(values(name, tomllib.loads(before.read_text()), tomllib.loads(after.read_text()), ["toml"]))
            elif rendered and before.suffix.lower() in {".html", ".htm"}:
                before_events, after_events = html(before).events, html(after).events
                encode = lambda event: json.dumps(event, ensure_ascii=False)
                matcher = SequenceMatcher(None, list(map(encode, before_events)),
                                          list(map(encode, after_events)))
                for change, start, stop, next_start, next_stop in matcher.get_opcodes():
                    if change != "equal":
                        changes.append(finding(name, ["html", "events", start, stop],
                                               before_events[start:stop], after_events[next_start:next_stop]))
        except (UnicodeError, ValueError, yaml.YAMLError) as error:
            raise DriverError(f"Cannot compare structured artifact {name}: {error}") from error
    return changes, names


def check_site(root: Path):
    entries = files(root)
    pages = {name: html(path) for name, path in entries.items() if path.suffix == ".html"}
    failures = []
    checked = 0
    for name, page in pages.items():
        route = "/" + (name[:-10] if name.endswith("index.html") else name)
        for link in page.links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or link.startswith("//"):
                continue
            target = urlsplit(urljoin(route, link))
            path = unquote(target.path).lstrip("/")
            path = posixpath.normpath(path)
            if path == ".":
                path = ""
            candidates = [path, path.rstrip("/") + "/index.html" if path else "index.html"]
            resolved = next((item for item in candidates if item in entries), None)
            checked += 1
            if resolved is None:
                failures.append(finding(name, ["links", link], link, {"error": "missing local target", "target": path}))
            elif target.fragment and resolved in pages and unquote(target.fragment) not in pages[resolved].ids:
                failures.append(finding(name, ["links", link], link, {"error": "missing fragment", "target": resolved, "fragment": unquote(target.fragment)}))
    if not pages:
        raise DriverError(f"Site has no HTML pages to check: {root}")
    return failures, {"pages": len(pages), "subjects": sorted(pages), "locations": [["links"]], "local_links_checked": checked,
                      "excluded": "external URLs, CSS URLs, JavaScript-generated targets"}
