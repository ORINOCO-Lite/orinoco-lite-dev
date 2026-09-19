// The server validates evidence and decision matching. This client edits a draft only.
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
};
const fmt = value => Number(value || 0).toLocaleString();
const json = value => JSON.stringify(value, null, 2);
const pretty = value => String(value || '').replaceAll('-', ' ');
const locationText = location => location?.length ? location.map(part => typeof part === 'number' ? `[${part}]` : part).join(' / ') : '(whole subject)';
const views = [
  ['queue', 'New & changed', 'Raw observations that need a fresh judgment; they are not a count of defects.'],
  ['outstanding', 'Known outstanding', 'Tolerated defects and deferred questions remain visible.'],
  ['matched', 'Carried decisions', 'Unchanged findings covered by an existing decision.'],
  ['all', 'All findings', 'Raw findings are observations, not a count of defects. Reviewed representation changes remain available.'],
  ['not-observed', 'Retirement candidates', 'Previously reviewed differences absent from a compatible, complete comparison.'],
  ['not-evaluated', 'Not evaluated', 'Decisions whose scope was not covered by the supplied comparisons.'],
];
const phases = [
  ['storage', 'Storage', 'Retained records'], ['rdf', 'RDF', 'Conversion check'],
  ['service', 'Service', 'Upload / return'], ['site-input-import', 'Site inputs', 'Authored content'],
  ['projection', 'Projection', 'Pages & graph'], ['assembly', 'Assembly', 'Hugo input tree'],
  ['rendering', 'Rendering', 'HTML & assets'], ['site-check', 'Site checks', 'Targets & browser'],
];
const state = {overview: null, view: 'queue', stage: '', query: '', offset: 0, limit: 50, items: [], total: 0,
  selected: null, tab: 'values', edits: new Map(), draftsByKey: new Map(), formCache: new Map(), dirtyForms: new Set(),
  rawDecisions: new Map(), preview: null, previewSerialized: null, author: '', listRequest: 0, detailRequest: 0, artifactRequest: 0};
let toastTimer;
function toast(message) {
  $('#toast').textContent = message; $('#toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4500);
}
async function api(path, payload, serialized) {
  const options = {headers: {'Accept': 'application/json'}};
  if (payload !== undefined) {
    options.method = 'POST'; options.headers['Content-Type'] = 'application/json';
    options.headers['X-Review-Token'] = state.overview.csrf_token;
    options.body = serialized ?? JSON.stringify(payload);
  }
  const response = await fetch(path, options);
  let body;
  try { body = await response.json(); } catch { throw new Error(`Server returned an unreadable response (${response.status}).`); }
  if (!response.ok) throw new Error(body.error || body.message || `Request failed (${response.status}).`);
  return body;
}
function safeURL(value) {
  if (typeof value !== 'string') return null;
  try { const url = new URL(value, window.location.href); return url.origin === location.origin && ['http:', 'https:'].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}
function pill(value, label = pretty(value)) { return el('span', `state-pill ${value}`, label); }
function details(title, data) {
  const box = el('details', 'json-details'); box.append(el('summary', '', title), el('pre', '', json(data))); return box;
}
function decisionDetails(title, decision) {
  const raw = state.rawDecisions.get(decision.id) || state.overview.decision_json?.[decision.id];
  const box = el('details', 'json-details'); box.append(el('summary', '', title), el('pre', '', raw || json(decision))); return box;
}
function empty(target, title, description) {
  const box = el('div', 'empty-state'); box.append(el('span', 'empty-symbol', '↔'), el('h3', '', title), el('p', '', description));
  target.replaceChildren(box);
}
const decisions = () => Array.isArray(state.overview.decisions) ? state.overview.decisions : state.overview.decisions?.decisions || [];
const stageFor = row => state.overview.stages.find(stage => stage.run_id === row.run_id && stage.stage_index === row.stage_index)
  || state.overview.stages.find(stage => row.key?.startsWith(`${stage.run_id}/`) && row.finding?.id?.startsWith(`${stage.stage}:`));
const decisionById = id => state.edits.get(id)?.decision || decisions().find(decision => decision.id === id);
function viewCount(view) {
  const counts = state.overview.counts;
  if (view === 'queue') return (counts.new || 0) + (counts.changed || 0);
  if (view === 'all') return ['new', 'changed', 'matched'].reduce((total, key) => total + (counts[key] || 0), 0);
  if (view === 'outstanding') return counts.outstanding;
  return counts[view] || 0;
}
function renderNavigation() {
  $('#view-nav').replaceChildren(...views.map(([key, title]) => {
    const button = el('button', `nav-button${(state.view === key || (key === 'queue' && ['new', 'changed'].includes(state.view))) ? ' active' : ''}`); button.type = 'button';
    if (state.view === key) button.setAttribute('aria-current', 'page');
    button.append(el('span', '', title), el('span', 'nav-count', viewCount(key) == null ? '↗' : fmt(viewCount(key))));
    button.addEventListener('click', () => { state.view = key; state.offset = 0; renderNavigation(); loadFindings(); });
    return button;
  }));
  const view = views.find(([key]) => key === state.view) || [state.view, state.view === 'new' ? 'New findings' : 'Changed behavior', state.view === 'new' ? 'Findings with no saved decision.' : 'Prior decisions need to be reconsidered against this evidence.'];
  $('#state-filter').value = state.view;
  $('#queue-heading').textContent = view[1]; $('#queue-description').textContent = view[2];
  if (state.view === 'matched') { const rules = decisions().filter(decision => decision.rule); if (rules.length) $('#queue-description').textContent += ` ${rules.length} named equivalence rule${rules.length === 1 ? '' : 's'} in this review; every raw finding remains accessible.`; }
}
function renderStages() {
  const known = new Set(phases.map(([name]) => name));
  const extras = [...new Set(state.overview.stages.map(stage => stage.stage))].filter(name => !known.has(name)).map(name => [name, pretty(name), 'Additional comparison']);
  $('#stage-flow').replaceChildren(...[...phases, ...extras].map(([name, label, description], index) => {
    const available = state.overview.stages.filter(stage => stage.stage === name);
    const selected = state.stage === name || available.some(stage => state.stage === `${stage.run_id}/${stage.stage_index}`);
    const button = el('button', `stage-card${available.length ? '' : ' unavailable'}${selected ? ' selected' : ''}`);
    button.type = 'button'; button.disabled = !available.length;
    button.setAttribute('aria-pressed', String(selected));
    const incomplete = available.filter(stage => stage.status !== 'complete').length;
    const status = !available.length ? 'Not supplied' : incomplete ? `${incomplete} incomplete / ${available.length}` : `${available.length} complete`;
    const step = el('span', 'stage-step'); step.append(el('span', '', String(index + 1).padStart(2, '0')), el('span', '', available.length ? '→' : '—'));
    button.append(step, el('span', 'stage-name', label), el('span', 'stage-status', status));
    const modes = el('span', 'stage-modes');
    for (const [mode, label] of [['isolated', 'Isolated'], ['complete-path', 'Full path']]) {
      if (available.some(stage => stage.mode === mode)) modes.append(el('span', 'tag', label));
    }
    button.append(modes); button.title = `${description}. ${available.map(stage => `${stage.mode}: ${stage.status}`).join('; ') || 'No report supplied'}`;
    button.addEventListener('click', () => setStage(selected ? '' : name)); return button;
  }));
  const filter = $('#stage-filter');
  filter.replaceChildren(new Option('All reports and stages', ''));
  for (const [name, label] of [...phases, ...extras]) {
    const matches = state.overview.stages.filter(stage => stage.stage === name);
    if (!matches.length) continue;
    const group = el('optgroup'); group.label = label;
    group.append(new Option(`All ${label.toLowerCase()} reports`, name));
    for (const stage of matches) group.append(new Option(`${label} · ${pretty(stage.mode)} · ${stage.status} · ${stage.run_id.slice(0, 8)} / ${stage.stage_index}`, `${stage.run_id}/${stage.stage_index}`));
    filter.append(group);
  }
  filter.value = state.stage;
  $('#integration').replaceChildren(el('strong', '', `Integration: ${pretty(state.overview.integration || 'not-established')}`),
    el('p', '', state.overview.integration_reason || 'Review complete-path evidence before making an integration judgment.'));
}
function setStage(value) {
  stashEditor(); state.selected = null; ++state.detailRequest; state.stage = value; state.offset = 0; renderStages(); loadFindings();
}
function stashEditor() {
  const form = $('#decision-form');
  if (form && state.selected) state.formCache.set(selectionKey(state.selected), Object.fromEntries(new FormData(form)));
}
const selectionKey = row => row.key || `decision:${row.decision.id}`;
function matchesStage(row) {
  if (!state.stage) return true;
  if (!state.stage.includes('/')) return row.decision.stage === state.stage;
  const stage = state.overview.stages.find(item => `${item.run_id}/${item.stage_index}` === state.stage);
  return stage?.stage === row.decision.stage;
}
async function loadFindings() {
  const request = ++state.listRequest;
  $('#findings').setAttribute('aria-busy', 'true');
  $('#findings').replaceChildren(el('p', 'list-empty', 'Loading findings…'));
  $('#page-prev').disabled = $('#page-next').disabled = true;
  try {
    let result;
    if (state.view.startsWith('not-')) {
      const rows = state.overview.absent.filter(row => row.state === state.view && matchesStage(row) && (!state.query || json(row).toLowerCase().includes(state.query.toLowerCase())));
      result = {items: rows.slice(state.offset, state.offset + state.limit), total: rows.length};
    } else {
      const params = new URLSearchParams({state: state.view, stage: state.stage, q: state.query, offset: state.offset, limit: state.limit});
      result = await api(`/api/findings?${params}`);
    }
    if (request !== state.listRequest) return;
    state.items = result.items; state.total = result.total; renderList();
    if (!state.selected && state.stage) renderStageSummary();
    $('#queue-total').textContent = `${fmt(result.total)} ${state.view.startsWith('not-') ? (result.total === 1 ? 'decision' : 'decisions') : (result.total === 1 ? 'raw finding' : 'raw findings')}`;
    $('#page-range').textContent = result.total ? `${fmt(state.offset + 1)}–${fmt(Math.min(state.offset + state.limit, result.total))} of ${fmt(result.total)}` : '0 results';
    $('#page-prev').disabled = state.offset === 0; $('#page-next').disabled = state.offset + state.limit >= result.total;
    $('#active-filter').hidden = !state.stage && !state.query;
    $('#active-filter').textContent = [state.stage && `Stage: ${$('#stage-filter').selectedOptions[0]?.textContent || state.stage}`, state.query && `Search: “${state.query}”`].filter(Boolean).join(' · ');
  } catch (error) {
    if (request === state.listRequest) $('#findings').replaceChildren(el('p', 'form-error', error.message));
  } finally { if (request === state.listRequest) $('#findings').setAttribute('aria-busy', 'false'); }
}
function renderStageSummary() {
  const selected = state.overview.stages.filter(stage => state.stage === stage.stage || state.stage === `${stage.run_id}/${stage.stage_index}`);
  const body = el('div', 'detail-body'); body.append(el('div', 'eyebrow', 'COMPARISON COVERAGE'), el('h3', '', selected.length === 1 ? pretty(selected[0].stage) : 'Selected stage reports'), el('p', 'inline-note', 'A comparison remains inspectable even when it has no findings in this queue.'));
  for (const stage of selected) {
    const item = el('section', 'context-stage'), heading = el('div', 'context-stage-heading');
    heading.append(el('h3', '', `${pretty(stage.mode)} · ${stage.run_id.slice(0, 8)}`), pill(stage.status === 'complete' ? 'matched' : 'changed', stage.status)); item.append(heading);
    item.append(el('p', 'inline-note', `Stage ${stage.stage_index} · ${stage.comparator}`));
    if (stage.diagnostics?.length) item.append(el('p', 'notice', stage.diagnostics.join(' · ')));
    item.append(details('Evaluated scope', stage.scope), details(stage.command?.length ? 'Comparison command' : 'Comparison command · not recorded', stage.command || []));
    const inspect = el('button', 'text-button', 'Browse this comparison’s artifacts'); inspect.type = 'button'; inspect.addEventListener('click', () => { const target = el('div'); item.append(target); renderArtifacts(target, stage, {}); inspect.remove(); }); item.append(inspect); body.append(item);
  }
  $('#detail').replaceChildren(body);
}
function renderList() {
  if (!state.items.length) { $('#findings').replaceChildren(el('p', 'list-empty', 'No results in this selection. Try another stage or view.')); return; }
  $('#findings').replaceChildren(...state.items.map(row => {
    const key = selectionKey(row), finding = row.finding || row.decision, stage = row.finding ? stageFor(row) : null;
    const button = el('button', `finding-row${state.selected && selectionKey(state.selected) === key ? ' selected' : ''}`); button.type = 'button';
    button.setAttribute('aria-pressed', String(Boolean(state.selected && selectionKey(state.selected) === key)));
    const top = el('span', 'row-top');
    top.append(el('span', 'row-stage', `${pretty(stage?.stage || finding.stage || finding.first_boundary || '')}${row.mode ? ` · ${pretty(row.mode)}` : ''}`), pill(row.state));
    const drafted = state.draftsByKey.has(key) || state.edits.has(row.decision?.id) || row.previous_decisions?.some(id => state.edits.has(id));
    if (drafted) top.append(pill('drafted', 'Draft'));
    button.append(top, el('span', 'row-subject', finding.subject), el('div', 'row-location', locationText(finding.location)));
    button.append(el('div', 'row-summary', row.decision ? `${pretty(row.decision.disposition)} · ${row.decision.author}` : `${pretty(finding.change)} · ${row.run_id?.slice(0, 8) || ''} / ${row.stage_index ?? ''}${row.previous_decisions?.length ? ` · ${row.previous_decisions.length} prior decision${row.previous_decisions.length === 1 ? '' : 's'}` : ''}`));
    button.addEventListener('click', () => openRow(row)); return button;
  }));
}
async function openFinding(key) {
  stashEditor(); const request = ++state.detailRequest;
  try { const row = await api(`/api/finding?${new URLSearchParams({key})}`); if (request === state.detailRequest) openRow(row, false); }
  catch (error) { toast(error.message); }
}
function openRow(row, invalidate = true) {
  stashEditor(); if (invalidate) ++state.detailRequest;
  ++state.artifactRequest; state.selected = row; state.tab = 'values';
  renderList(); renderDetail();
  if (matchMedia('(max-width: 650px)').matches) $('#detail').scrollIntoView({behavior: 'smooth', block: 'start'});
}
function valuePanel(label, present, value, className, view) {
  const panel = el('div', `value-panel ${className}`), heading = el('div', 'value-heading');
  const type = view?.type || (!present ? 'absent' : value === null ? 'null' : Array.isArray(value) ? `array · ${value.length}` : typeof value);
  heading.append(el('span', '', label), el('span', 'value-type', type)); panel.append(heading);
  panel.append(!present ? el('div', 'missing', 'Field is missing') : el('pre', '', view?.text ?? (value === undefined ? 'undefined' : json(value))));
  return panel;
}
function renderDetail() {
  const row = state.selected; if (!row) return;
  const finding = row.finding || row.decision, stage = row.finding ? stageFor(row) : null;
  const head = el('div', 'detail-head'), meta = el('div', 'detail-meta');
  meta.append(pill(row.state), el('span', 'tag', pretty(stage?.stage || finding.stage || finding.first_boundary)));
  if (stage) meta.append(el('span', 'tag', pretty(stage.mode)), el('span', 'tag', stage.status));
  head.append(meta, el('h3', 'subject', finding.subject), el('p', 'detail-location', locationText(finding.location)));
  if (stage) head.append(el('p', 'inline-note', `Run ${stage.run_id.slice(0, 8)} · stage ${stage.stage_index} · ${finding.id}`));
  const tabs = el('div', 'detail-tabs'); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', 'Finding detail');
  for (const [value, label] of [['values', row.finding ? 'Difference' : 'Decision'], ['evidence', 'Artifacts'], ['context', 'Scope & context']]) {
    const button = el('button', '', label); button.type = 'button'; button.setAttribute('role', 'tab');
    button.id = `tab-${value}`; button.setAttribute('aria-controls', 'detail-panel'); button.setAttribute('aria-selected', String(state.tab === value)); button.tabIndex = state.tab === value ? 0 : -1;
    button.disabled = !stage && value === 'evidence';
    button.addEventListener('click', () => { stashEditor(); state.tab = value; renderDetail(); $(`#tab-${value}`).focus(); });
    button.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault(); const buttons = $$('[role=tab]:not(:disabled)', tabs); const index = buttons.indexOf(button);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next].click();
    }); tabs.append(button);
  }
  head.append(tabs); const body = el('div', 'detail-body'); body.id = 'detail-panel'; body.setAttribute('role', 'tabpanel'); body.setAttribute('aria-labelledby', `tab-${state.tab}`);
  $('#detail').replaceChildren(head, body);
  if (state.tab === 'values') {
    if (row.finding) {
      if (finding.identity === 'ambiguous' || finding.identity === 'unmatched') body.append(el('div', 'identity-warning', `Identity is ${finding.identity}. An exact reusable decision cannot be established for this finding.`));
      const delta = el('div', 'delta-grid'); delta.append(valuePanel('Before', finding.before_present !== false, finding.before, 'before', row.value_views?.before), valuePanel('After', finding.after_present !== false, finding.after, 'after', row.value_views?.after)); body.append(delta);
      if (finding.representation_equivalence) body.append(el('p', 'inline-note', `Supported representation rule: ${finding.representation_equivalence}. This rule never accepts a resulting page change.`));
      renderCausal(body, row);
    } else {
      body.append(el('div', 'retirement-summary', row.state === 'not-observed' ? 'This difference was not observed within compatible evaluated scope. Check whether its adaptation can be removed before retiring the decision.' : 'The supplied reports did not evaluate this decision’s compatible scope. Its absence does not establish that the difference is gone.'));
      body.append(decisionDetails('Previously reviewed decision and expected values', row.decision));
    }
    const previous = (row.previous_decisions || []).map(id => decisions().find(decision => decision.id === id)).filter(Boolean);
    if (previous.length) {
      const prior = el('details', 'json-details'); prior.append(el('summary', '', `${previous.length} previous decision${previous.length === 1 ? '' : 's'} · inspect rationale and scope`));
      previous.forEach(decision => { const item = el('div', 'detail-body'); item.append(el('strong', '', `${decision.author} · ${decision.disposition}`), el('p', 'inline-note', decision.rationale), el('p', 'inline-note', `Reconsider when: ${decision.reconsider_when}`), decisionDetails(`Decision ${decision.id}`, decision)); prior.append(item); });
      if (previous.length > 1) prior.open = true; body.append(prior);
    }
    renderEditor(body, row);
  } else if (state.tab === 'evidence') renderArtifacts(body, stage, row);
  else {
    if (stage) {
      body.append(details(stage.command?.length ? 'Comparison command' : 'Comparison command · not recorded', stage.command || []), details('Evaluated scope', stage.scope), details('Comparator and status', {comparator: stage.comparator, status: stage.status, mode: stage.mode, diagnostics: stage.diagnostics}));
      const contexts = state.overview.contexts || [];
      const context = Array.isArray(contexts) ? contexts.find(item => item.run_id === stage.run_id)?.context : contexts[stage.run_id];
      body.append(details('Report context', context || {}));
      for (const [role, artifact] of Object.entries(stage.artifacts || {})) body.append(details(`${role} · artifact and producing operation`, artifact));
    }
    if (row.finding) {
      const metadata = {...finding}; delete metadata.before; delete metadata.after;
      body.append(details('Finding metadata', metadata));
      for (const side of ['before', 'after']) { const box = el('details', 'json-details'); box.append(el('summary', '', `${side} · exact value`), el('pre', '', row.value_views?.[side]?.text ?? json(finding[side]))); body.append(box); }
    } else body.append(decisionDetails('Saved decision', finding));
  }
}
function renderCausal(body, row) {
  const links = (state.overview.groups || []).filter(group => group.origin === row.key || group.effect === row.key);
  if (!links.length) return;
  const panel = el('section', 'links-panel'); panel.append(el('h4', '', 'Follow the cause and its effects'), el('p', '', 'Linked effects keep their own review state. An accepted cause does not accept a new consequence.'));
  for (const link of links) {
    const isOrigin = link.origin === row.key, key = isOrigin ? link.effect : link.origin;
    const button = el('button', 'causal-link'); button.type = 'button';
    button.append(pill(link.status === 'verified' ? 'matched' : 'changed', link.status), el('span', '', isOrigin ? 'Downstream effect →' : '← Possible origin'), el('span', 'link-key', key.split('/').at(-1)));
    if (!isOrigin && link.status === 'verified') button.children[1].textContent = '← Verified origin';
    button.title = key; button.addEventListener('click', () => openFinding(key)); panel.append(button);
    api(`/api/finding?${new URLSearchParams({key})}`).then(linked => {
      if (!button.isConnected) return;
      button.querySelector('.link-key').textContent = `${linked.finding.subject} · ${locationText(linked.finding.location)}`;
      button.append(pill(linked.state));
    }).catch(() => { /* Navigation still presents the full server diagnostic. */ });
  }
  body.append(panel);
}
function labeled(form, title, name, tag = 'input', options = []) {
  const label = el('label', '', title), control = el(tag); control.name = name; control.id = `decision-${name}`;
  if (tag === 'select') for (const [value, text] of options) control.append(new Option(text, value));
  if (tag !== 'select') control.required = true;
  label.append(control); form.append(label); return control;
}
function renderEditor(body, row) {
  const key = selectionKey(row), cached = state.formCache.get(key), draftId = state.draftsByKey.get(key);
  const previous = row.previous_decisions || [];
  const existing = draftId ? decisionById(draftId) : row.decision || (previous.length === 1 ? decisionById(previous[0]) : null);
  const section = el('section', 'editor'), heading = el('div', 'editor-heading');
  heading.append(el('h4', '', existing ? 'Review the decision' : 'Record a decision'), el('span', 'tag', 'Draft only')); section.append(heading);
  const form = el('form'); form.id = 'decision-form';
  let target;
  if (row.finding && previous.length > 1) {
    section.append(el('p', 'identity-warning', 'Multiple prior decisions overlap this finding. Select one explicitly to update, or remove the conflicting decisions in the draft.'));
    target = labeled(form, 'Decision to update', 'target', 'select', [['', 'Choose an existing decision…'], ...previous.map(id => { const d = decisionById(id); return [id, `${d?.author || 'Unknown author'} · ${d?.disposition || ''} · ${id.slice(0, 8)}`]; })]);
    target.required = true;
  }
  const pair = el('div', 'form-pair'); form.append(pair);
  const disposition = labeled(pair, 'Disposition', 'disposition', 'select', [['undecided', 'Undecided · keep open'], ['tolerated', 'Tolerated · known defect'], ['intended', 'Intended · accept this behavior']]);
  const author = labeled(pair, 'Decision author', 'author'); author.autocomplete = 'name'; author.placeholder = 'Your name';
  const rationale = labeled(form, 'Why this judgment?', 'rationale', 'textarea'); rationale.placeholder = 'Explain the behavior, its impact, and the evidence behind your judgment.';
  const reconsider = labeled(form, 'Reconsider when', 'reconsider_when', 'textarea'); reconsider.placeholder = 'A specific upstream change, new evidence, or condition that reopens this decision.';
  let rule;
  if (!existing && row.finding?.representation_equivalence && previous.length <= 1) {
    rule = labeled(form, 'Decision scope', 'rule', 'select', [['', 'This exact subject and structured change'], [row.finding.representation_equivalence, `Named rule: ${row.finding.representation_equivalence}`]]);
    rule.parentElement.append(el('small', '', 'The server checks complete record semantics and comparison coverage. Page effects always remain separate.'));
  } else form.append(el('div', 'scope-label', existing?.rule ? `Scope: named rule ${existing.rule}` : `Scope: ${row.finding?.subject || row.decision.subject} · ${locationText(row.finding?.location || row.decision.location)}`));
  const values = cached || existing || {author: state.author, disposition: 'undecided'};
  for (const control of [disposition, author, rationale, reconsider, rule, target].filter(Boolean)) control.value = values[control.name] || (control.name === 'disposition' ? 'undecided' : '');
  if (target) target.addEventListener('change', () => {
    const choice = decisionById(target.value); if (!choice) return;
    for (const control of [disposition, author, rationale, reconsider]) control.value = choice[control.name] || '';
  });
  const actions = el('div', 'editor-actions'); const save = el('button', 'button primary', row.state === 'changed' && existing ? 'Update to current finding' : 'Save to draft'); save.type = 'submit'; actions.append(save);
  const removalCandidates = row.decision ? [row.decision.id] : previous;
  if (draftId && !removalCandidates.includes(draftId)) removalCandidates.push(draftId);
  if (removalCandidates.length) {
    const remove = el('button', 'danger-button', 'Remove decision…'); remove.type = 'button';
    remove.addEventListener('click', () => {
      const id = target ? target.value : removalCandidates[0];
      if (!id) { feedback.textContent = 'Select the decision to remove first.'; feedback.className = 'form-error'; return; }
      if (!author.value.trim() || !rationale.value.trim()) { feedback.textContent = 'Enter an author and explain the removal in “Why this judgment?” first.'; feedback.className = 'form-error'; return; }
      const addedOnly = state.edits.get(id)?.action === 'add';
      if (addedOnly) { state.edits.delete(id); state.rawDecisions.delete(id); state.draftsByKey.delete(key); }
      else { state.edits.set(id, {id, action: 'remove', reason: rationale.value.trim(), author: author.value.trim()}); state.draftsByKey.set(key, id); }
      state.preview = null; state.dirtyForms.delete(key); stashEditor(); draftChanged();
      feedback.textContent = addedOnly ? 'New decision removed from this draft.' : 'Removal added to the draft. The saved decision is unchanged until you apply the export.'; feedback.className = 'form-feedback';
    }); actions.append(remove);
  }
  const feedback = el('p'); feedback.setAttribute('role', 'status'); form.append(actions, feedback);
  form.addEventListener('input', () => { state.dirtyForms.add(key); });
  form.addEventListener('submit', async event => {
    event.preventDefault(); feedback.textContent = ''; save.disabled = true;
    try {
      const values = Object.fromEntries(new FormData(form));
      const id = target?.value || existing?.id;
      const payload = {author: values.author.trim(), disposition: values.disposition, rationale: values.rationale.trim(), reconsider_when: values.reconsider_when.trim()};
      if (row.finding) payload.finding_key = row.key;
      if (id && decisions().some(decision => decision.id === id)) payload.decision_id = id;
      if (existing?.rule || values.rule) payload.rule = existing?.rule || values.rule;
      const result = await api('/api/decision', payload), decision = result.decision || result;
      const priorDraft = state.draftsByKey.get(key);
      if (priorDraft && state.edits.get(priorDraft)?.action === 'add' && priorDraft !== decision.id) state.edits.delete(priorDraft);
      if (typeof result.decision_json !== 'string') throw new Error('The server did not preserve decision JSON types. Reload with a compatible review server.');
      state.rawDecisions.set(decision.id, result.decision_json);
      state.edits.set(decision.id, {id: decision.id, action: decisions().some(item => item.id === decision.id) ? 'update' : 'add', decision});
      state.draftsByKey.set(key, decision.id); state.author = payload.author; state.preview = null; state.dirtyForms.delete(key);
      state.formCache.set(key, values); draftChanged();
      feedback.className = 'form-feedback'; feedback.textContent = 'Saved to this draft. Preview matching before exporting.'; toast('Decision added to draft');
    } catch (error) { feedback.className = 'form-error'; feedback.textContent = error.message; }
    finally { save.disabled = false; }
  });
  section.append(form); body.append(section);
}
function renderArtifacts(body, stage, row) {
  if (!stage) return;
  const toolbar = el('div', 'artifact-toolbar'), select = el('select'); select.setAttribute('aria-label', 'Artifact role');
  for (const [role, artifact] of Object.entries(stage.artifacts || {})) select.append(new Option(`${role}${artifact.operation ? ` · ${artifact.operation.operation}` : ''}`, role));
  const rootButton = el('button', 'button quiet', 'Root'); rootButton.type = 'button';
  const upButton = el('button', 'button quiet', '↑ Parent'); upButton.type = 'button';
  toolbar.append(select, rootButton, upButton); body.append(toolbar);
  const pathLabel = el('div', 'artifact-path', '/'), output = el('div'); body.append(pathLabel, output);
  let currentPath = '';
  const load = async path => {
    const request = ++state.artifactRequest; currentPath = path; pathLabel.textContent = `${select.value} / ${path}`; upButton.disabled = !path;
    output.replaceChildren(el('p', 'inline-note', 'Loading evidence…'));
    try {
      const artifact = await api(`/api/artifact?${new URLSearchParams({run_id: stage.run_id, stage_index: stage.stage_index, role: select.value, path})}`);
      if (request !== state.artifactRequest) return;
      output.replaceChildren();
      if (artifact.kind === 'directory') {
        if (!artifact.entries.length) output.append(el('p', 'inline-note', 'This directory is empty.'));
        for (const entry of artifact.entries) {
          const button = el('button', 'artifact-entry'); button.type = 'button';
          button.append(el('span', '', `${entry.kind === 'directory' ? '▸ ' : ''}${entry.name}`), el('small', '', entry.kind === 'directory' ? 'directory' : `${fmt(entry.size)} bytes`));
          button.addEventListener('click', () => load(entry.path)); output.append(button);
        }
      } else {
        const links = el('div', 'artifact-links'), downloadURL = safeURL(artifact.download_url);
        if (downloadURL) { const link = el('a', '', 'Download original'); link.href = downloadURL; link.download = ''; links.append(link); }
        links.append(el('span', '', `${artifact.media_type || artifact.kind}${artifact.size != null ? ` · ${fmt(artifact.size)} bytes` : ''}`)); output.append(links);
        if (artifact.kind === 'image') {
          const url = safeURL(artifact.url); if (url) { const image = el('img', 'artifact-image'); image.src = url; image.alt = `Evidence: ${path || select.value}`; output.append(image); }
        } else if (artifact.kind === 'text') {
          if (artifact.truncated) output.append(el('p', 'notice', 'This text preview is truncated. Download the original for the complete bytes.'));
          if (artifact.preview_url) {
            let url;
            try { const parsed = new URL(artifact.preview_url); if (parsed.protocol === 'http:' && parsed.hostname === '127.0.0.1' && parsed.origin !== location.origin) url = parsed.href; } catch { /* Keep raw text available. */ }
            if (url) {
              const preview = el('details', 'json-details'); preview.append(el('summary', '', 'Open isolated rendered preview · scripts disabled'));
              preview.addEventListener('toggle', () => {
                if (preview.open && !preview.querySelector('iframe')) {
                  const frame = el('iframe', 'artifact-preview'); frame.setAttribute('sandbox', ''); frame.title = `Rendered evidence: ${path || select.value}`; frame.referrerPolicy = 'no-referrer'; frame.src = url; preview.append(frame);
                }
              }); output.append(preview);
            }
          }
          output.append(el('pre', 'artifact-text', artifact.text));
        } else output.append(el('p', 'inline-note', 'This binary artifact is available as an original-file download.'));
      }
    } catch (error) { if (request === state.artifactRequest) output.replaceChildren(el('p', 'form-error', error.message)); }
  };
  if (row.finding && /\.[a-z0-9]+$/i.test(row.finding.subject)) {
    const affected = el('button', 'text-button', 'Open affected file'); affected.type = 'button'; affected.addEventListener('click', () => load(row.finding.subject)); toolbar.append(affected);
  }
  select.addEventListener('change', () => load('')); rootButton.addEventListener('click', () => load(''));
  upButton.addEventListener('click', () => load(currentPath.split('/').slice(0, -1).join('/')));
  load('');
}
const changes = () => ({schema_version: 1, base_digest: state.overview.base_digest, edits: [...state.edits.values()]});
function serializedChanges() {
  const edits = [...state.edits.values()].map(edit => {
    const fields = Object.entries(edit).map(([name, value]) => {
      const raw = name === 'decision' ? state.rawDecisions.get(edit.id) : JSON.stringify(value);
      if (raw === undefined) throw new Error('Decision JSON types are unavailable; recreate this draft entry.');
      return `${JSON.stringify(name)}: ${raw}`;
    });
    return `    {${fields.join(', ')}}`;
  });
  return `{\n  "schema_version": 1,\n  "base_digest": ${JSON.stringify(state.overview.base_digest)},\n  "edits": [\n${edits.join(',\n')}\n  ]\n}`;
}
function draftChanged() {
  $('#draft-count').textContent = state.edits.size; renderList();
  if ($('#draft-dialog').open) renderDraft();
}
function undoEdit(id) {
  state.edits.delete(id); state.rawDecisions.delete(id); state.preview = null;
  for (const [key, value] of state.draftsByKey) if (value === id) state.draftsByKey.delete(key);
  draftChanged(); if (state.selected) renderDetail();
}
function renderDraft() {
  const list = $('#draft-list'); list.replaceChildren();
  if (!state.edits.size) list.append(el('p', 'list-empty', 'No draft changes yet. Select a finding to record or revise a decision.'));
  for (const edit of state.edits.values()) {
    const row = el('div', 'draft-row'), info = el('div', 'draft-info'), decision = edit.decision || decisionById(edit.id);
    info.append(el('strong', '', decision?.subject || edit.id), el('p', '', `${decision?.stage || ''} · ${decision ? locationText(decision.location) : edit.id}`), el('p', '', edit.action === 'remove' ? `${edit.author}: ${edit.reason}` : `${decision.author} · ${decision.disposition}: ${decision.rationale}`));
    if (decision?.rule) info.append(el('p', '', `Named rule: ${decision.rule}`));
    const undo = el('button', 'text-button', 'Undo'); undo.type = 'button'; undo.setAttribute('aria-label', `Undo ${edit.action} for ${decision?.subject || edit.id}`); undo.addEventListener('click', () => undoEdit(edit.id));
    row.append(el('span', 'tag', edit.action), info, undo); list.append(row);
  }
  $('#draft-json').textContent = serializedChanges();
  $('#draft-preview').disabled = $('#draft-export').disabled = !state.edits.size;
  $('#draft-status').textContent = state.preview ? 'Preview is current' : state.edits.size ? 'Preview required before export' : '';
  renderPreview();
}
function renderPreview() {
  const output = $('#preview-result'); output.replaceChildren(); if (!state.preview) return;
  const box = el('div', 'preview-box'); box.append(el('h3', '', 'Matching preview'), el('p', 'inline-note', `${fmt(state.preview.decision_count)} decisions after these edits. Integration remains a separate judgment.`));
  const counts = el('div', 'preview-counts');
  for (const [name, count] of Object.entries(state.preview.counts || {})) { const item = el('div'); item.append(el('strong', '', fmt(count)), el('span', '', pretty(name))); counts.append(item); }
  box.append(counts);
  if (state.preview.diagnostics?.length) { const list = el('ul'); for (const diagnostic of state.preview.diagnostics) list.append(el('li', '', typeof diagnostic === 'string' ? diagnostic : json(diagnostic))); box.append(list); }
  if (state.preview.absent?.length) box.append(details('Absent decisions after matching', state.preview.absent));
  output.append(box);
}
async function previewDraft(exportAfter = false) {
  $('#draft-preview').disabled = $('#draft-export').disabled = true; $('#draft-status').textContent = 'Checking scope and matching…';
  try {
    const serialized = serializedChanges();
    const preview = await api('/api/preview', changes(), serialized);
    if (serialized !== serializedChanges()) throw new Error('The draft changed during preview. Preview the current draft again.');
    state.preview = preview; state.previewSerialized = preview.changes_json || serialized;
    renderDraft();
    if (exportAfter) {
      const blob = new Blob([state.previewSerialized + '\n'], {type: 'application/json'});
      const url = URL.createObjectURL(blob), link = el('a'); link.href = url; link.download = 'orinoco-review-changes.json';
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast('Validated draft exported. Apply it separately with the CLI.');
    }
  } catch (error) {
    state.preview = null; $('#preview-result').replaceChildren(el('p', 'form-error', error.message)); $('#draft-status').textContent = 'Preview failed · draft retained';
    $('#draft-preview').disabled = $('#draft-export').disabled = !state.edits.size;
  }
}
function renderContext() {
  const body = $('#context-body'); body.replaceChildren(el('p', 'notice', `${pretty(state.overview.integration || 'not-established')}. ${state.overview.integration_reason || ''}`));
  const problems = state.overview.incompatibilities || [];
  if (problems.length) { body.append(el('h3', 'context-section-title', 'Incomplete or incompatible evidence')); const list = el('ul', 'diagnostic-list'); for (const problem of problems) list.append(el('li', '', typeof problem === 'string' ? problem : json(problem))); body.append(list); }
  body.append(el('h3', 'context-section-title', 'Stages and their execution context'));
  for (const stage of state.overview.stages) {
    const item = el('section', 'context-stage'), heading = el('div', 'context-stage-heading'); heading.append(el('h3', '', pretty(stage.stage)), el('span', 'tag', pretty(stage.mode)), pill(stage.status === 'complete' ? 'matched' : 'changed', stage.status)); item.append(heading);
    item.append(el('p', 'inline-note', `Run ${stage.run_id} · stage ${stage.stage_index}`));
    const button = el('button', 'text-button', 'Inspect this comparison'); button.type = 'button'; button.addEventListener('click', () => { $('#context-dialog').close(); setStage(`${stage.run_id}/${stage.stage_index}`); }); item.append(button);
    const scope = {...stage.scope}; if (Array.isArray(scope.subjects)) scope.subjects = `${fmt(scope.subjects.length)} subjects; expand full report scope below`;
    item.append(details('Scope summary', scope), details('Complete comparison details', stage)); body.append(item);
  }
  body.append(el('h3', 'context-section-title', 'Explicit data-flow links'), el('p', 'inline-note', 'These links connect matching artifact bytes and recorded operations. They do not by themselves prove a finding caused a later effect.'), details(`${fmt(state.overview.data_flow?.length)} artifact dependencies`, state.overview.data_flow || []));
  body.append(el('h3', 'context-section-title', 'Causal attribution'), details('Verified and possible origin / effect links', state.overview.groups || []), details('Report contexts', state.overview.contexts || []));
  const ruleDecisions = decisions().filter(decision => decision.rule);
  if (ruleDecisions.length) body.append(el('h3', 'context-section-title', 'Named equivalence decisions'), el('p', 'inline-note', 'These bounded rules can cover many raw findings. They never hide the findings or accept downstream effects.'), details(`${ruleDecisions.length} saved rule decisions`, ruleDecisions));
}
function wire() {
  $('#state-filter').addEventListener('change', event => { state.view = event.target.value; state.offset = 0; renderNavigation(); loadFindings(); });
  $('#stage-filter').addEventListener('change', event => setStage(event.target.value));
  $('#stage-reset').addEventListener('click', () => setStage(''));
  let searchTimer;
  $('#search').addEventListener('input', event => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.query = event.target.value.trim(); state.offset = 0; loadFindings(); }, 240); });
  $('#page-prev').addEventListener('click', () => { state.offset = Math.max(0, state.offset - state.limit); loadFindings(); });
  $('#page-next').addEventListener('click', () => { state.offset += state.limit; loadFindings(); });
  $('#draft-open').addEventListener('click', () => { stashEditor(); renderDraft(); $('#draft-dialog').showModal(); });
  $('#context-open').addEventListener('click', () => { renderContext(); $('#context-dialog').showModal(); });
  $('[aria-label="Orinoco review home"]').addEventListener('click', event => { event.preventDefault(); state.view = 'queue'; state.stage = ''; state.query = ''; state.offset = 0; $('#search').value = ''; renderNavigation(); renderStages(); loadFindings(); });
  for (const button of $$('[data-close]')) button.addEventListener('click', () => document.getElementById(button.dataset.close).close());
  $('#draft-preview').addEventListener('click', () => previewDraft()); $('#draft-export').addEventListener('click', () => previewDraft(true));
  window.addEventListener('beforeunload', event => { if (state.edits.size || state.dirtyForms.size) { event.preventDefault(); event.returnValue = ''; } });
}
async function init() {
  try {
    state.overview = await api('/api/review');
    $('#review-title').textContent = state.overview.title || 'Staged comparison'; document.title = `${state.overview.title || 'Change review'} · Orinoco`;
    const outstanding = await api('/api/findings?state=outstanding&offset=0&limit=1');
    state.overview.counts.outstanding = outstanding.total;
    $('#base-label').textContent = `Decision base ${state.overview.base_digest.slice(0, 12)}`;
    renderNavigation(); renderStages(); wire(); await loadFindings();
  } catch (error) { $('#fatal').textContent = `This review could not be opened. ${error.message}`; $('#fatal').hidden = false; }
}
init();
