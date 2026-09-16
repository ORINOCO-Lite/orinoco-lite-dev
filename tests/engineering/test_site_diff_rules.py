"""Exercise comparison rules with SiteDiff, without a website or network access."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


TOOL = Path(__file__).resolve().parents[2] / "tools/site-diff"
PROFILE = TOOL / "psychoinformatics.yaml"
RUBY = """
require 'json'
require 'yaml'
require 'sitediff'
config = SiteDiff::Config.normalize(YAML.load_file(ARGV.fetch(0)))
results = JSON.parse(STDIN.read).map do |side, path, html|
  SiteDiff::Sanitizer.new(html, config.fetch(side), path: path).sanitize
end
STDOUT.write(JSON.generate(results))
"""


@pytest.fixture(scope="module")
def sanitize():
    ruby = shutil.which("ruby")
    if ruby is None or subprocess.run(
        [ruby, "-e", "require 'sitediff'"], cwd=TOOL,
        capture_output=True, text=True,
    ).returncode:
        pytest.skip(
            "SiteDiff Ruby bundle unavailable; run pytest through "
            "tools/site-diff's bundle exec"
        )

    def run(*inputs):
        result = subprocess.run(
            [ruby, "-e", RUBY, str(PROFILE)], input=json.dumps(inputs),
            cwd=TOOL, capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)

    return run


COPYRIGHT = '<p class="text-sm">© 2026 Psychoinformatics</p>'
BUILD = (
    '<p class="text-xs text-neutral-500 dark:text-neutral-400">Orinoco Lite 0.3.0rc6 '
    '(<a class="hover:underline hover:decoration-primary-400 hover:text-primary-500" '
    'href="https://github.com/ORINOCO-Lite/orinoco-lite-dev/commit/'
    + "a" * 40 + '">v0.3.0rc6</a>)</p>'
)
QUERY = 'sh:NodeShape=dlthings:Thing&amp;pid=example:one&amp;edit=true'
NATIVE_EDITOR = (
    '<div class="text-xs"><a href="https://pool.psychoinformatics.de/ui/?' + QUERY
    + '">Edit this record </a>in the knowledge pool.</div>'
)
LITE_EDITOR = (
    '<div class="orinoco-record-editor-link text-xs"><a href="/edit/?' + QUERY
    + '" rel="noopener noreferrer">Edit this record</a></div>'
)
HUB_LABEL = (
    '<span class="decoration-primary-500 group-hover:underline group-hover:decoration-2 '
    'group-hover:underline-offset-2">Collaboration hub</span>'
)
HUB = (
    '<div id="menu-wrapper"><a href="https://hub.psychoinformatics.de" '
    'title="Collaboration hub">{}</a></div>'
)
NATIVE_GRAPH = (
    '<div id="sigma-container" '
    'class="w-full h-screen m-0 p-0 bg-neutral-100 dark:bg-neutral-600"></div>'
)
LITE_GRAPH = (
    '<div id="sigma-container" style="height:55vh;min-height:320px" '
    'class="w-full m-0 p-0 bg-neutral-100 dark:bg-neutral-600"></div>'
)
HTTP_CHARSET = '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
CHARSET = '<meta charset="utf-8">'


def document(head):
    return f'<!doctype html><html><head>{head}</head><body></body></html>'


@pytest.mark.parametrize("before,after,path", [
    (f"<footer>{NATIVE_EDITOR}</footer>", f"<footer>{LITE_EDITOR}</footer>",
     "/persons/one/index.html"),
    (f"<footer>{COPYRIGHT}</footer>", f"<footer>{COPYRIGHT}{BUILD}</footer>",
     "/index.html"),
    (HUB.format(""), HUB.format(HUB_LABEL), "/index.html"),
    ('<header><nav><a href="" title="">Outputs</a></nav></header>',
     '<header><nav><a href="" title="Outputs">Outputs</a></nav></header>', "/index.html"),
    ('<script src="/graph.js"></script>',
     '<script src="/graph.js?v=' + "b" * 64 + '"></script>', "/index.html"),
    (NATIVE_GRAPH, LITE_GRAPH, "/explore/index.html"),
    (document(HTTP_CHARSET + CHARSET), document(CHARSET), "/index.html"),
])
def test_accepted_changes_compare_equal(sanitize, before, after, path):
    left, right = sanitize(("before", path, before), ("after", path, after))
    assert left == right


PAGE = (
    '<!doctype html><html><head><script src="/graph.js?v=' + "b" * 64 + '"></script>'
    '<script src="/assets/app-0123456789abcdef.js"></script></head><body>'
    '<header><nav><a href="https://institution.example/">Institution'
    '<img src="/img/logo.png" alt="Logo"></a>' + HUB.format(HUB_LABEL)
    + '<a href="" title="Outputs">Outputs</a></nav></header>'
    '<article><h1>Röder</h1><p>Original page body</p>' + LITE_GRAPH + '</article>'
    '<footer>' + COPYRIGHT + LITE_EDITOR + BUILD + '</footer></body></html>'
)


def test_identical_html_compares_equal_on_both_sides(sanitize):
    before, after = sanitize(
        ("before", "/explore/index.html", PAGE),
        ("after", "/explore/index.html", PAGE),
    )
    assert before == after


@pytest.mark.parametrize("original,changed", [
    ("Röder", "Roder"),
    ("/img/logo.png", "/img/other.png"),
    ("https://institution.example/", "https://wrong.example/"),
    ("© 2026 Psychoinformatics", "© 2026 Someone else"),
    (COPYRIGHT, ""),
    ('href="https://hub.psychoinformatics.de"', 'href="https://wrong.example/hub"'),
    (">Collaboration hub</span>", ">Wrong menu label</span>"),
    ('title="Outputs"', 'title="Wrong tooltip"'),
    ("pid=example:one", "pid=example:other"),
    ("Original page body", "Changed page body"),
    ("/graph.js?v=", "/other.js?v="),
    ("/assets/app-0123456789abcdef.js", "/assets/app-fedcba9876543210.js"),
    ("height:55vh", "height:56vh"),
    ("https://github.com/ORINOCO-Lite/orinoco-lite-dev/commit/",
     "https://wrong.example/commit/"),
])
def test_meaningful_mutations_remain_visible(sanitize, original, changed):
    assert original in PAGE
    baseline, mutated = sanitize(
        ("after", "/explore/index.html", PAGE),
        ("after", "/explore/index.html", PAGE.replace(original, changed)),
    )
    assert baseline != mutated


def test_explore_rule_does_not_apply_on_other_paths(sanitize):
    left, right = sanitize(
        ("before", "/projects/one/index.html", NATIVE_GRAPH),
        ("after", "/projects/one/index.html", LITE_GRAPH),
    )
    assert left != right


def test_footer_rule_does_not_remove_article_content(sanitize):
    left, right = sanitize(
        ("before", "/index.html", "<article></article>"),
        ("after", "/index.html", f"<article>{BUILD}</article>"),
    )
    assert left != right


def test_missing_dataset_jsonld_remains_visible(sanitize):
    metadata = (
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"Dataset","name":"Röder"}'
        '</script>'
    )
    before, after = sanitize(
        ("before", "/datasets/one/index.html", document(metadata)),
        ("after", "/datasets/one/index.html", document("")),
    )
    assert before != after


@pytest.mark.parametrize("head", [
    HTTP_CHARSET,
    HTTP_CHARSET.replace("charset=UTF-8", "charset=ISO-8859-1") + CHARSET,
    HTTP_CHARSET.replace('http-equiv="Content-Type"', 'http-equiv="Other"') + CHARSET,
])
def test_meta_rule_keeps_nonduplicate_or_different_declarations(sanitize, head):
    rendered, = sanitize(("after", "/index.html", document(head)))
    assert "http-equiv=" in rendered
