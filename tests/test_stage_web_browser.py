"""Real browser boundaries; use workspace Playwright or an explicit NODE_PATH.

Set ORINOCO_REQUIRE_BROWSER_TESTS=1 in browser-enabled CI so missing Chromium or
Playwright fails the job instead of skipping these optional local tests.
"""

from argparse import Namespace
import base64
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Thread

import pytest

from orinoco_lite import stage_reports, stage_review
from orinoco_lite.stage_bundle import ReviewModel, bundle
from orinoco_lite.stage_reports import artifact_digest, read_json, write_json, write_report
from orinoco_lite.stage_web import review_servers


PLAYWRIGHT = """
const {createRequire} = require('node:module');
const path = require('node:path');
const fromWorkspace = createRequire(path.join(process.cwd(), 'package.json'));
let chromium;
try { ({chromium} = fromWorkspace('playwright')); }
catch { ({chromium} = fromWorkspace('@playwright/test')); }
"""


@pytest.fixture(scope="module")
def browser_node():
    node = shutil.which("node")
    reason = "Node.js is unavailable"
    if node:
        probe = subprocess.run(
            [node, "-e", PLAYWRIGHT + "chromium.launch({headless:true}).then(b=>b.close()).catch(e=>{console.error(e.message);process.exit(1)});"],
            capture_output=True, text=True, timeout=30,
        )
        if probe.returncode == 0:
            return node
        reason = "Workspace Playwright/Chromium is unavailable: " + probe.stderr[-1500:]
    if os.environ.get("ORINOCO_REQUIRE_BROWSER_TESTS") == "1":
        pytest.fail(reason)
    pytest.skip(reason)


def browser(node, server, script, **options):
    program = PLAYWRIGHT + """
const assert = require('node:assert/strict');
const fs = require('node:fs');
const options = JSON.parse(fs.readFileSync(0, 'utf8'));
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    page.setDefaultTimeout(10000);
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.goto(options.url);
    await page.locator('#findings[aria-busy="false"]').waitFor();
    if (await page.getByRole('button', {name:'All comparisons',exact:true}).count()) await page.getByRole('button', {name:'All comparisons',exact:true}).click();
    await page.locator('#findings[aria-busy="false"]').waitFor();
""" + script + """
    assert.deepEqual(pageErrors, []);
  } finally { await browser.close(); }
})().catch(error => {console.error(error.stack); process.exit(1)});
"""
    result = subprocess.run(
        [node, "-e", program], input=json.dumps({
            "url": f"http://127.0.0.1:{server.server_port}/", **options,
        }), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


@pytest.fixture(autouse=True)
def selected_schema(monkeypatch):
    monkeypatch.setattr(stage_reports, "execution_context", lambda: {"schema_digest": "browser-test-schema"})


def finding(subject, after, *, before="source"):
    return {"subject": subject, "location": ["title"], "change": "changed",
            "before": before, "after": after, "before_present": True, "after_present": True}


def report(tmp_path, name, findings, *, stage="storage", subjects=None, status="complete"):
    inputs = tmp_path / name
    inputs.mkdir()
    left, right = inputs / "left.json", inputs / "right.json"
    write_json(left, {row["subject"]: row["before"] for row in findings})
    write_json(right, {row["subject"]: row["after"] for row in findings})
    output = inputs / "report"
    document = write_report(
        output, stage=stage, left=left, right=right, findings=findings,
        comparator="records-v1", status=status,
        scope={"complete": status == "complete", "all_locations": True,
               "subjects": subjects or [row["subject"] for row in findings]},
        diagnostics=["Fixture conversion failed before evaluating its records"] if status == "failed" else [],
    )
    return output, document


def decision(document, row):
    return stage_review.decision_for(
        document["stages"][0], row, report=document, disposition="undecided",
        rationale="Earlier fixture judgment", reconsider_when="The fixture behavior changes",
        author="Codex browser test",
    )


def test_hostile_artifact_cannot_execute_read_parent_or_contact_network(tmp_path, browser_node):
    requests = []

    class Sink(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    sink = ThreadingHTTPServer(("127.0.0.1", 0), Sink)
    thread = Thread(target=sink.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{sink.server_port}"
    tree = tmp_path / "site"
    (tree / "pages").mkdir(parents=True)
    stylesheet = b"h1 { color: rgb(12, 34, 56); } body { background-image: url(/pixel.svg); }"
    (tree / "theme.css").write_bytes(stylesheet)
    (tree / "pixel.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>')
    integrity = base64.b64encode(hashlib.sha256(stylesheet).digest()).decode()
    (tree / "pages/attack.html").write_text(f"""<!doctype html>
      <base href="{address}/"><meta http-equiv="refresh" content="0;url={address}/redirect">
      <style>@import url('{address}/stylesheet');body{{background:url('{address}/background')}}</style>
      <link rel="stylesheet" href="{address}/linked-style">
      <link rel="stylesheet" href="/theme.css" integrity="sha256-{integrity}">
      <body onload="window.evidenceExecuted=true;parent.reportExecuted=true">
      <script>window.evidenceExecuted=true;parent.reportExecuted=parent.reviewSecret;
        fetch('{address}/script');parent.postMessage('evidence-executed','*');</script>
      <img src="{address}/image" onerror="parent.reportExecuted=true">
      <h1>Hostile evidence remains readable</h1>
      <button onclick="fetch('{address}/click')">Untrusted action</button>
      <a href="{address}/navigation">Untrusted link</a></body>""")
    output = tmp_path / "report"
    attack = "<img src=x onerror=window.reportExecuted=true>"
    write_report(output, stage="rendering", left=tree, right=tree,
                 comparator="html-test/1", findings=[finding("pages/attack.html", attack)],
                 scope={"complete": True, "subjects": ["pages/attack.html"]})
    destination = tmp_path / "bundle"
    bundle([output], destination)
    before = artifact_digest(destination)
    try:
        with review_servers(ReviewModel(destination), port=0) as server:
            result = browser(browser_node, server, r"""
    await page.evaluate(() => {window.reviewSecret='private-review-state';window.reportExecuted=false;window.evidenceMessages=[];addEventListener('message',event=>window.evidenceMessages.push(event.data));});
    await page.getByRole('button').filter({hasText:'pages/attack.html'}).click();
    assert.match(await page.locator('#detail').innerText(), /<img src=x onerror=window.reportExecuted=true>/);
    assert.equal(await page.locator('#detail img').count(), 0);
    const difference = page.getByRole('tab', {name:'Difference', exact:true});
    await difference.focus(); await difference.press('ArrowRight');
    assert.equal(await page.getByRole('tab',{name:'Artifacts',exact:true}).getAttribute('aria-selected'),'true');
    await page.getByRole('button',{name:'Open affected file',exact:true}).click();
    await page.locator('summary').filter({hasText:'Open isolated rendered preview'}).click();
    const handle = await page.locator('iframe').elementHandle();
    const frame = await handle.contentFrame();
    await frame.getByRole('heading',{name:'Hostile evidence remains readable'}).waitFor();
    assert.equal(await page.locator('iframe').getAttribute('sandbox'),'');
    assert.notEqual(new URL(frame.url()).origin, new URL(options.url).origin);
    await frame.getByRole('button',{name:'Untrusted action'}).click();
    const untrustedLink = frame.getByText('Untrusted link',{exact:true});
    assert.equal(await untrustedLink.getAttribute('href'),null);
    await untrustedLink.click();
    await page.waitForLoadState('networkidle');
    assert.equal(await frame.getByRole('heading',{name:'Hostile evidence remains readable'}).evaluate(node=>getComputedStyle(node).color),'rgb(12, 34, 56)');
    assert.equal(await frame.evaluate(()=>Boolean(window.evidenceExecuted)),false);
    assert.equal(await frame.evaluate(()=>{try{return parent.reviewSecret==='private-review-state'}catch{return false}}),false);
    assert.equal(await page.evaluate(()=>window.reportExecuted),false);
    assert.deepEqual(await page.evaluate(()=>window.evidenceMessages),[]);
    console.log(JSON.stringify({isolated:true}));
""")
        assert result == {"isolated": True}
        assert requests == []
        assert artifact_digest(destination) == before
    finally:
        sink.shutdown()
        sink.server_close()
        thread.join()


def test_draft_preview_export_changed_conflict_and_absent_workflows(tmp_path, browser_node, capsys):
    subjects = ["record:new", "record:changed", "record:conflict", "record:retired"]
    _, prior = report(tmp_path, "prior", [finding(subject, "old") for subject in subjects[1:]])
    saved = [decision(prior, row) for row in prior["stages"][0]["findings"]]
    by_subject = {item["subject"]: item for item in saved}
    conflicting = deepcopy(by_subject["record:conflict"])
    conflicting["id"] = "conflict-second"
    conflicting["disposition"] = "tolerated"
    saved.append(conflicting)
    _, missing = report(tmp_path, "prior-rdf", [finding("record:unevaluated", "old")], stage="rdf")
    saved.append(decision(missing, missing["stages"][0]["findings"][0]))
    exact_numbers = [1, 1.0, True, None, 9007199254740993,
                     {"decimal": 1.0, "integer": 9007199254740993}]
    current, _ = report(tmp_path, "current", [finding("record:new", exact_numbers),
                                           finding("record:changed", "current"),
                                           finding("record:conflict", "old")], subjects=subjects)
    failed, _ = report(tmp_path, "failed-rdf", [], stage="rdf", status="failed",
                       subjects=["record:unevaluated"])
    decision_path = tmp_path / "decisions.json"
    write_json(decision_path, {"schema_version": 1, "decisions": saved})
    original = decision_path.read_bytes()
    destination = tmp_path / "bundle"
    bundle([current, failed], destination, decisions=decision_path)
    model = ReviewModel(destination)
    before = artifact_digest(destination)
    with review_servers(model, port=0) as server:
        result = browser(browser_node, server, r"""
    const select = async subject => {await page.locator('#findings button').filter({hasText:subject}).click();};
    const fill = async reason => {
      await page.getByLabel('Decision author',{exact:true}).fill('Browser reviewer');
      await page.getByLabel('Why this judgment?',{exact:true}).fill(reason);
      await page.getByLabel('Reconsider when',{exact:true}).fill('The tested values change');
    };
    const save = async name => {
      const response=page.waitForResponse(r=>r.url().endsWith('/api/decision'));
      await page.getByRole('button',{name,exact:true}).click();
      assert.equal((await response).status(),200);
      await page.getByText('Saved to this draft. Preview matching before exporting.',{exact:true}).waitFor();
    };
    assert.equal(await page.locator('#integration').count(), 0);
    assert.match(await page.locator('#stage-flow button').filter({hasText:'RDF outputs'}).innerText(),/incomplete/);
    await select('record:new');
    assert.match(await page.getByLabel('Unified diff', {exact:true}).innerText(), /9007199254740993/);
    await page.getByText('Exact left and right values', {exact:true}).click();
    assert.match(await page.locator('.value-panel.after').innerText(),/true/);
    assert.match(await page.locator('.value-panel.after').innerText(),/1\.0/);
    assert.match(await page.locator('.value-panel.after').innerText(),/9007199254740993/);
    await fill('Review the typed new value');
    await page.getByLabel(/^Disposition/).selectOption('intended');
    await save('Save to draft');
    await select('record:changed');
    assert.match(await page.locator('#detail').innerText(),/1 previous decision/);
    await fill('Review the current changed value');
    await save('Update to current finding');
    await select('record:conflict');
    const target=page.getByLabel(/^Decision to update/);
    assert.equal(await target.inputValue(),'');
    assert.equal(await target.evaluate(node=>node.checkValidity()),false);
    await target.selectOption(options.conflictId);
    await fill('Remove the overlapping fixture decision');
    await page.getByRole('button',{name:'Remove decision…',exact:true}).click();
    await page.getByRole('button',{name:/^Retirement candidates/}).click();
    await select('record:retired');
    assert.match(await page.locator('#detail').innerText(),/compatible evaluated scope/);
    await fill('Unpatched fixture confirms this difference is absent');
    await page.getByRole('button',{name:'Remove decision…',exact:true}).click();
    await page.getByRole('button',{name:/^Not evaluated/}).click();
    await select('record:unevaluated');
    assert.match(await page.locator('#detail').innerText(),/absence does not establish that the difference is gone/);
    await page.getByRole('button',{name:/^Draft changes/}).click();
    const previewResponse=page.waitForResponse(r=>r.url().endsWith('/api/preview'));
    await page.getByRole('button',{name:'Preview matching',exact:true}).click();
    const preview=await (await previewResponse).json();
    await page.getByRole('heading',{name:'Matching preview',exact:true}).waitFor();
    const downloadPromise=page.waitForEvent('download');
    await page.getByRole('button',{name:'Validate & export JSON',exact:true}).click();
    const download=await downloadPromise;
    const changesJSON=fs.readFileSync(await download.path(),'utf8');
    const changes=JSON.parse(changesJSON);
    assert.equal(changes.edits.length,4);
    console.log(JSON.stringify({changes_json:changesJSON,counts:preview.counts}));
""", conflictId=conflicting["id"])
    changes = json.loads(result["changes_json"])
    assert result["counts"] == model.preview(changes)["counts"]
    assert result["counts"] == {"matched": 3, "not-evaluated": 1}
    new = next(edit["decision"] for edit in changes["edits"] if edit["action"] == "add")
    assert new["expected"]["after"] == exact_numbers
    assert type(new["expected"]["after"][0]) is int
    assert type(new["expected"]["after"][1]) is float
    assert type(new["expected"]["after"][5]["decimal"]) is float
    updated = next(edit["decision"] for edit in changes["edits"] if edit["action"] == "update")
    assert updated["id"] == by_subject["record:changed"]["id"]
    assert updated["expected"]["after"] == "current"
    assert artifact_digest(destination) == before
    assert decision_path.read_bytes() == original
    change_path = tmp_path / "decision-edits.json"
    write_json(change_path, changes)
    assert stage_review.execute(Namespace(review_command="apply", directory=tmp_path, write=True)) == 0
    assert read_json(decision_path) == stage_review.apply_changes(json.loads(original), changes)
    capsys.readouterr()


def test_unified_diff_problem_separation_and_target_selection(tmp_path, browser_node):
    from orinoco_lite.site_compare import compare_trees, finding as delta
    a, b = tmp_path / 'left', tmp_path / 'right'
    for directory, value in [(a, 'Library'), (b, 'https://example.org/library')]:
        directory.mkdir()
        write_json(directory / 'person.json', {'creator': value})
    changes, names = compare_trees(a, b)
    diff = tmp_path / 'diff'
    write_report(diff, stage='projection', left=a, right=b, findings=changes, comparator='hugo-content/1',
                 targets={'left': {'label': 'Orinoco'}, 'right': {'label': 'Lite candidate', 'revision': 'abc123'}},
                 scope={'complete': True, 'subjects': names})
    checks = tmp_path / 'checks'
    write_report(checks, stage='site-check', left=a, right=b,
                 findings=[delta('broken.html', ['links', '/missing'], '/missing', {'error': 'missing target'})],
                 comparator='local-html-targets/2')
    destination = tmp_path / 'bundle'
    bundle([diff, checks], destination)
    with review_servers(ReviewModel(destination), port=0) as server:
        browser(browser_node, server, r"""
        assert.equal(await page.locator('#findings .finding-row').count(),1);
        await page.locator('#findings .finding-row').click();
        assert.match(await page.getByLabel('Unified diff',{exact:true}).innerText(), /-"Library"/);
        assert.match(await page.locator('#detail').innerText(), /Downstream effect not tested/);
        await page.getByRole('button',{name:/^Possible problems/}).click();
        await page.getByText('broken.html',{exact:true}).waitFor();
        assert.equal(await page.locator('#findings .finding-row').count(),1);
        await page.locator('#findings .finding-row').click();
        assert.match(await page.locator('#detail').innerText(), /not compared across targets/);
        await page.getByRole('button',{name:/^Changes to inspect/}).click();
        await page.getByRole('button',{name:'Orinoco → Lite candidate (1)',exact:true}).click();
        await page.locator('#target-context > summary').click();
        await page.getByText('Reported revision: abc123',{exact:true}).waitFor();
        await page.locator('#findings .finding-row').filter({hasText:'person.json'}).waitFor();
        assert.equal(await page.locator('#findings .finding-row').count(),1);
        console.log('{}');
        """)


def test_original_file_view_and_agent_notes_remain_separate(tmp_path, browser_node):
    source, data = report(tmp_path, 'annotated', [finding('record', 'candidate')])
    evidence = tmp_path/'experiment.py'; evidence.write_text('print("inspectable experiment")\n')
    notes = tmp_path/'notes.json'
    write_json(notes, {'annotations':[{'finding_key':data['run_id']+'/storage:1', 'author':'Codex',
        'explanation':'An attributed investigation.', 'hypothesis':'A possible cause.',
        'conclusion':'Not established.', 'limits':'One fixture only.', 'tags':['unresolved'],
        'evidence':[{'label':'Retained experiment','path':'experiment.py'}],
        'commands':[['python','experiment.py']]}]})
    output=tmp_path/'bundle'; bundle([source], output, annotations=notes)
    with review_servers(ReviewModel(output), port=0) as server:
        result=browser(browser_node, server, '''
    await page.locator('.finding-row').first().click();
    assert.match(await page.locator('#detail').innerText(), /Agent annotations/);
    assert.match(await page.locator('#detail').innerText(), /An attributed investigation/);
    assert.match(await page.locator('#detail').innerText(), /Human disposition/);
    await page.getByRole('button', {name:'Retained experiment',exact:true}).click();
    await page.getByText('print("inspectable experiment")', {exact:true}).waitFor();
    await page.getByRole('button', {name:/^Original-file diffs/}).click();
    await page.locator('#findings[aria-busy="false"]').waitFor();
    await page.locator('.finding-row').first().click();
    await page.getByLabel('Original-file unified diff', {exact:true}).waitFor();
    assert.match(await page.locator('#detail').innerText(), /candidate/);
    assert.equal(await page.getByRole('button',{name:'Save to draft',exact:true}).count(), 0);
    assert.equal(await page.getByRole('link',{name:/Download .* original/}).count(),2);
    console.log(JSON.stringify({ok:true}));
''')
    assert result['ok']


def test_site_buttons_and_sidebar_are_scoped_to_one_pair(tmp_path, browser_node):
    from orinoco_lite.site_compare import compare_trees
    reports = []
    for name, count in [('Orinoco', 1), ('Orinoco Lite', 2)]:
        directory = tmp_path/name
        left, right = directory/'left', directory/'right'
        left.mkdir(parents=True); right.mkdir()
        for index in range(count):
            (left/f'{index}.html').write_text('<script src="https://old.example/a.js"></script>')
            (right/f'{index}.html').write_text('<script src="https://new.example/a.js"></script>')
        if count == 1:
            (left/'unique.txt').write_text('old')
            (right/'unique.txt').write_text('new')
        changes, _ = compare_trees(left, right, rendered=True)
        output = directory/'report'
        write_report(output, stage='rendering', left=left, right=right,
            findings=changes, comparator='site-files/1',
            targets={'left':{'label':name, 'url':'https://old.example/'},
                     'right':{'label':'Draft site', 'url':'https://new.example/'}})
        reports.append(output)
    support, _ = report(tmp_path, 'support', [finding('metadata', 'new')], stage='projection')
    output = tmp_path/'bundle'; bundle([*reports, support], output)
    model = ReviewModel(output)
    pairs = [p for p in model.overview()['comparisons'] if p['deployment']]
    with review_servers(model, port=0) as server:
        browser(browser_node, server, """
        assert.equal(await page.locator('#comparison-buttons button').count(), 2);
        assert.equal(await page.getByText('Supporting investigations',{exact:true}).count(), 0);
        const first = options.pairs[0], second = options.pairs[1];
        for (const pair of [second, first]) {
          await page.getByRole('button',{name:pair.label+' ('+pair.counts.unclassified+')',exact:true}).click();
          await page.locator('#findings[aria-busy="false"]').waitFor();
          assert.equal(await page.locator('#view-nav button').filter({hasText:'Changes to inspect'}).locator('.nav-count').innerText(), String(pair.counts.unclassified));
          assert.equal(await page.locator('#view-nav button').filter({hasText:'Recognized patterns'}).locator('.nav-count').innerText(), String(pair.counts.recognized));
          await page.getByRole('button',{name:/^Recognized patterns/}).click();
          await page.locator('#findings[aria-busy="false"]').waitFor();
          assert.equal(await page.locator('#findings .finding-row').count(), pair.counts.recognized);
          await page.getByRole('button',{name:/^Changes to inspect/}).click();
          await page.locator('#findings[aria-busy="false"]').waitFor();
        }
        assert.equal(await page.locator('.comparison-choice #stage-flow').count(),1);
        console.log('{}');
        """, pairs=pairs)


def test_complete_site_stage_pattern_diff_evidence_and_return(tmp_path, browser_node):
    from orinoco_lite.site_compare import compare_trees
    from orinoco_lite.stage_reports import write_operation
    reports = []
    sources = []
    for side, flavor in [('upstream','upstream'),('lite','lite')]:
        source = tmp_path/side/'projection'; source.mkdir(parents=True)
        (source/'page.json').write_text(json.dumps(side))
        write_operation(source, operation='projection', inputs={}, context={'flavor':flavor})
        site = tmp_path/side/'website'; site.mkdir()
        for name in ['a.html','b.html']:
            (site/name).write_text(f'<p>{side}</p>')
        write_operation(site, operation='rendering', inputs={'projection':source}, context={'flavor':flavor})
        sources.append((source,site))
    for index, stage in [(0,'projection'),(1,'rendering')]:
        left,right = sources[0][index],sources[1][index]
        changes,_=compare_trees(left,right,rendered=stage=='rendering')
        output=tmp_path/(stage+'-report')
        write_report(output,stage=stage,left=left,right=right,findings=changes,comparator='site-files/1',mode='complete-path')
        reports.append(output)
    output=tmp_path/'bundle';bundle(reports,output)
    model=ReviewModel(output)
    assert len(model.overview()['comparisons']) == 1
    pair=model.overview()['comparisons'][0]
    assert {s['stage'] for s in model.overview(pair['id'])['stages']} == {'projection','rendering'}
    with review_servers(model,port=0) as server:
        browser(browser_node,server,'''
        assert.match(await page.locator('#selected-comparison').innerText(), /Locally built Orinoco → Locally built Lite/);
        assert.equal(await page.locator('#view-nav button').filter({hasText:'Changes to inspect'}).locator('.nav-count').innerText(),'0');
        await page.locator('#stage-flow button').filter({hasText:'Projection'}).click();
        await page.locator('#findings[aria-busy="false"]').waitFor();
        await page.waitForFunction(() => document.querySelector('#scope-label').textContent.endsWith('projection'));
        assert.equal(await page.locator('#view-nav button').filter({hasText:'Changes to inspect'}).locator('.nav-count').innerText(),'1');
        await page.locator('#stage-flow button').filter({hasText:'Rendering'}).click();
        await page.waitForFunction(() => document.querySelector('#scope-label').textContent.endsWith('rendering'));
        await page.getByRole('button',{name:/^Recognized patterns/}).click();
        await page.locator('#findings[aria-busy="false"]').waitFor();
        await page.locator('#pattern-summary button').filter({hasText:'Repeated HTML edits'}).click();
        await page.locator('#findings[aria-busy="false"]').waitFor();
        await page.locator('#findings .finding-row').first().click();
        await page.getByLabel('Unified diff',{exact:true}).waitFor();
        const selectedScope=await page.locator('#scope-label').innerText();
        await page.getByRole('button',{name:'Open original-file diffs',exact:true}).click();
        await page.getByLabel('Original-file unified diff',{exact:true}).waitFor();
        await page.getByRole('button',{name:'Back to selected difference',exact:true}).click();
        await page.getByLabel('Unified diff',{exact:true}).waitFor();
        assert.equal(await page.locator('#scope-label').innerText(),selectedScope);
        assert.equal(await page.locator('#findings .finding-row').count(),2);
        await page.getByRole('tab',{name:'Artifacts',exact:true}).click();
        assert.equal(await page.locator('#scope-label').innerText(),selectedScope);
        console.log('{}');
        ''')
