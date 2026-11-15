'use strict';
const $ = id => document.getElementById(id);
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function link(label, href) {
  const a = node('a', label); a.href = href; a.target = '_blank'; a.rel = 'noopener'; return a;
}
function validate(value, schema, path = '$') {
  const type = Array.isArray(value) ? 'array' : value === null ? 'null' : Number.isInteger(value) ? 'integer' : typeof value;
  if (type !== schema.type) throw Error(`${path}: expected ${schema.type}`);
  if ('const' in schema && value !== schema.const) throw Error(`${path}: invalid constant`);
  if (type === 'object') {
    for (const key of schema.required || []) if (!(key in value)) throw Error(`${path}: missing ${key}`);
    for (const [key, item] of Object.entries(value)) {
      if (!(key in schema.properties)) throw Error(`${path}: unexpected ${key}`);
      validate(item, schema.properties[key], `${path}.${key}`);
    }
  } else if (type === 'array') {
    if (value.length < (schema.minItems || 0)) throw Error(`${path}: empty array`);
    value.forEach((item, i) => validate(item, schema.items, `${path}[${i}]`));
  } else if (type === 'string') {
    if (value.length < (schema.minLength || 0) || (schema.pattern && !new RegExp(schema.pattern).test(value))) throw Error(`${path}: invalid string`);
  }
}
async function main() {
  const responses = await Promise.all(['/report.json', '/report.schema.json'].map(path => fetch(path)));
  if (responses.some(r => !r.ok)) throw Error('Could not load the saved report or schema.');
  const [r, schema] = await Promise.all(responses.map(res => res.json()));
  validate(r, schema);
  const artifacts = new Map(r.artifacts.map(a => [a.id, a]));
  const runs = new Map(r.runs.map(run => [run.id, run]));
  function evidenceLinks(parent, ids) {
    for (const id of ids) {
      const a = artifacts.get(id);
      if (!a) throw Error(`Unknown artifact ${id}`);
      parent.append(link(a.label, '/' + a.path));
    }
  }
  $('title').textContent = 'Closed generic metadata structs: prevent generator and analyzer crashes';
  $('provenance').textContent = `Recorded ${r.recordedOn} · Review ${r.reviewVersion} · AI has not issued an approval.`;
  $('requirement-text').textContent = r.source.requirement;
  $('issue-link').textContent = r.source.label + ' ↗'; $('issue-link').href = r.source.url;
  $('original-env').textContent = 'Original report: ' + r.source.originalEnvironment;
  $('base').textContent = r.change.base; $('head').textContent = r.change.head;
  $('change-summary').textContent = r.change.summary; $('excluded').textContent = r.change.excluded;
  for (const file of r.change.scope) $('scope').append(node('li', file));
  evidenceLinks($('change-links'), ['diff', 'setup']);
  const limitations = {
    AC1: 'Three metadata cases tested; not every generic type shape.',
    AC2: 'Resolver generation does not prove runtime round-trip behavior.',
    AC3: 'Emit and Debug build only. Windows and NativeAOT remain unverified.',
    AC4: 'Positional record gap confirmed. General diagnostic preservation is not established.'
  };
  for (const c of r.criteria) {
    const row = node('tr', undefined, 'evidence-row');
    const requirement = node('td'); requirement.dataset.label = 'Requirement';
    requirement.append(node('span', c.id, 'criterion-id'), node('strong', c.title), node('p', c.origin, 'muted'));
    const result = node('td', c.assessment); result.dataset.label = 'Observed result';
    if (c.id === 'AC1') {
      const cases = node('details'); cases.append(node('summary', 'Cases exercised'), node('p', c.detail)); result.append(cases);
    }
    const tests = node('td'); tests.dataset.label = 'Evidence';
    for (const id of c.tests) {
      const run = runs.get(id); if (!run) throw Error(`Unknown run ${id}`);
      const a = node('a', run.label, 'run-link'); a.href = '#run-' + run.id;
      a.append(node('span', run.result)); tests.append(a);
      const logs = node('div', undefined, 'links'); evidenceLinks(logs, run.artifacts); tests.append(logs);
    }
    const limit = node('td', limitations[c.id] || c.detail); limit.dataset.label = 'Limitation';
    row.append(requirement, result, tests, limit); $('evidence-map').append(row);
  }
  for (const run of r.runs) {
    const article = node('article', undefined, 'run'); article.id = 'run-' + run.id;
    const result = node('strong');
    const passed = ['head-targeted', 'full-suite'].includes(run.id) && run.result.match(/^([\d,]+ passed)(.*)$/);
    if (passed) result.append(node('span', passed[1], 'check-passed'), document.createTextNode(passed[2]));
    else result.textContent = run.result;
    article.append(node('h3', run.label), result, node('p', run.environment, 'muted'), node('p', run.meaning));
    if (['head-targeted', 'full-suite'].includes(run.id)) article.append(node('p', 'Recorded test result only; not approval of the change.', 'result-note'));
    const logs = node('div', undefined, 'links'); evidenceLinks(logs, run.artifacts); article.append(logs); $('runs').append(article);
  }
  // Open the recorded-run disclosure when navigating to a traceability target.
  function revealRun() {
    if (location.hash.startsWith('#run-')) {
      $('runs').parentElement.open = true;
      document.getElementById(location.hash.slice(1))?.scrollIntoView();
    }
  }
  addEventListener('hashchange', revealRun); revealRun();
  $('finding-title').textContent = r.finding.title; $('example').textContent = r.finding.example;
  for (const [id, key] of [['finding-base','base'],['finding-head','head'],['finding-control','control'],['finding-cause','cause']]) $(id).textContent = r.finding[key];
  evidenceLinks($('finding-links'), r.finding.artifacts);
  for (const ref of r.finding.references) $('source-links').append(link(ref.label, ref.url));
  for (const item of r.limits) {
    const card = node('li', undefined, 'card'); card.append(node('h3', item.title), node('p', item.detail)); $('limit-cards').append(card);
  }
  $('concept').append(node('p', r.concept.body));
  const boundaries = node('ul'); r.concept.boundaries.forEach(t => boundaries.append(node('li', t))); $('concept').append(boundaries);
  for (const item of r.lessons) {
    const lesson = node('div', undefined, 'lesson'); lesson.append(node('h3', item.title), node('p', item.detail)); $('lessons').append(lesson);
  }
  evidenceLinks($('footer-links'), ['report', 'setup', ...(artifacts.has('human-decision') ? ['human-decision'] : [])]);
  let review = {version:r.reviewVersion, base:r.change.base, head:r.change.head};
  let key = `earned-trust:decision:${review.version}:${review.base}:${review.head}`;
  const verdictLabels = {accept:'Accept', request_changes:'Request changes', defer:'Defer'};
  let saved = null;
  function validateDecision(d) {
    if (!d || d.schemaVersion !== 1 || d.issue !== r.issue || !d.review || Object.keys(review).some(k => d.review[k] !== review[k])) throw Error('Saved decision belongs to a different review.');
    if (!d.decision || !Object.hasOwn(verdictLabels, d.decision.verdict)) throw Error('Invalid saved decision.');
    for (const [field, max] of [['responsiblePerson',160],['rationale',5000],['acceptableResidualRisk',5000]]) {
      if (typeof d.decision[field] !== 'string' || !d.decision[field].trim() || d.decision[field].length > max) throw Error('Invalid saved decision fields.');
    }
    if (d.identityAssurance !== 'self-declared; not verified identity or GitHub approval' || typeof d.savedAt !== 'string' || !Number.isFinite(Date.parse(d.savedAt))) throw Error('Invalid saved decision metadata.');
  }
  function showSaved() {
    $('decision-status').textContent = verdictLabels[saved.decision.verdict] + ' · saved locally';
    $('save-context').textContent = `Self-declared: ${saved.decision.responsiblePerson}. Browser timestamp: ${saved.savedAt}`;
    $('export').disabled = false;
  }
  $('binding').textContent = `Review ${review.version}\nBase ${review.base}\nHead ${review.head}`;
  function updateRiskEmphasis() {
    const accepting = $('verdict').value === 'accept';
    $('risk-group').classList.toggle('accepting', accepting);
    $('acceptance-note').hidden = !accepting;
    $('risk-confirmation').hidden = !accepting;
    $('risk-ack').required = accepting;
    if (!accepting) $('risk-ack').checked = false;
  }
  $('verdict').addEventListener('change', updateRiskEmphasis);
  function restoreDecision() {
    saved = null;
    $('decision-form').reset();
    $('decision-status').textContent = 'Pending human review';
    $('save-context').textContent = 'No decision saved for this review.';
    $('decision-message').textContent = '';
    $('decision-message').dataset.state = '';
    $('export').disabled = true;
    $('dirty').hidden = true;
    $('binding').textContent = `Review ${review.version}\nBase ${review.base}\nHead ${review.head}`;
  try {
    const raw = localStorage.getItem(key);
    if (raw !== null) {
      const parsed = JSON.parse(raw); validateDecision(parsed); saved = parsed;
      $('owner').value = saved.decision.responsiblePerson; $('verdict').value = saved.decision.verdict;
      $('rationale').value = saved.decision.rationale; $('risk').value = saved.decision.acceptableResidualRisk;
      $('risk-ack').checked = saved.decision.residualRiskAcknowledged === true;
      showSaved(); $('decision-message').textContent = 'Restored the saved decision for this exact review.';
    }
  } catch (error) {
    $('decision-message').textContent = 'Local decision unavailable or invalid. Status remains pending. ' + error.message;
  }
    updateRiskEmphasis();
  }
  if (!new URL(location.href).searchParams.has('run') && !new URL(location.href).searchParams.has('aiReview')) restoreDecision();
  else { $('decision-form').hidden = true; $('decision-scope').textContent = 'Loading the requested execution report. No prior decision is applied.'; }
  updateRiskEmphasis();
  $('decision-form').addEventListener('input', () => { $('dirty').hidden = false; });
  $('decision-form').addEventListener('submit', event => {
    event.preventDefault();
    updateRiskEmphasis();
    if ($('verdict').value === 'accept' && !$('risk-ack').checked) {
      $('decision-message').dataset.state = 'error';
      $('decision-message').textContent = 'Decision was not saved. Confirm acceptance of the residual risk.';
      $('risk-ack').focus(); return;
    }
    const d = {schemaVersion:1, issue:r.issue, review:{...review}, decision:{responsiblePerson:$('owner').value.trim(), verdict:$('verdict').value, rationale:$('rationale').value.trim(), acceptableResidualRisk:$('risk').value.trim(), residualRiskAcknowledged:$('verdict').value === 'accept' && $('risk-ack').checked}, identityAssurance:'self-declared; not verified identity or GitHub approval', savedAt:new Date().toISOString(), timestampSource:'browser clock; not independently verified'};
    try {
      validateDecision(d); const encoded = JSON.stringify(d);
      localStorage.setItem(key, encoded);
      if (localStorage.getItem(key) !== encoded) throw Error('Storage read-back failed.');
      saved = d; showSaved(); $('dirty').hidden = true;
      $('decision-message').dataset.state = 'saved';
      $('decision-message').textContent = 'Decision saved locally for this base, head and review version. No remote approval was submitted.';
    } catch (error) {
      $('decision-message').dataset.state = 'error';
      $('decision-message').textContent = 'Decision was not saved. ' + error.message;
    }
  });
  $('export').addEventListener('click', () => {
    if (!saved) return;
    validateDecision(saved);
    const blob = new Blob([JSON.stringify(saved, null, 2) + '\n'], {type:'application/json'});
    const url = URL.createObjectURL(blob); const a = node('a'); a.href = url; a.download = `earned-trust-${r.issue}-${review.version}-decision.json`;
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('decision-message').textContent = 'Export requested for the last saved decision. Check your browser downloads.';
  });
  const originalReview = {version:r.reviewVersion, base:r.change.base, head:r.change.head};
  let selectedRun = null;
  let aiQuote = null;
  let requiresPreflight = false;
  let runRequest = 0;
  function setScope(binding, runId = null, aiId = null) {
    $('decision-form').hidden = false;
    review = {...binding};
    key = `earned-trust:decision:${review.version}:${review.base}:${review.head}`;
    $('decision-scope').textContent = aiId ? `Decision scope: new AI review ${aiId}; evidence run ${runId}. No previous assessment decision applies.` : runId ? `Decision scope: execution report ${runId}. This is not a new AI assessment.` : 'Decision scope: original recorded AI assessment.';
    $('original-scope').hidden = !runId;
    const url = new URL(location.href);
    if (runId && !aiId) url.searchParams.set('run', runId); else url.searchParams.delete('run');
    if (aiId) url.searchParams.set('aiReview', aiId); else url.searchParams.delete('aiReview');
    history.replaceState(null, '', url);
    restoreDecision();
  }
  $('original-scope').addEventListener('click', () => setScope(originalReview));
  $('use-run').addEventListener('click', () => {
    if (!selectedRun) return;
    setScope({version:selectedRun.reviewVersion, base:selectedRun.base, head:selectedRun.head}, selectedRun.runId);
    $('decision').scrollIntoView(); $('owner').focus();
  });
  async function displayRun(runId) {
    aiQuote = null;
    $('ai-cost').textContent = '';
    if (requiresPreflight) $('run-ai').disabled = true;
    const ticket = ++runRequest;
    $('run-select').disabled = true;
    $('run-loading').hidden = false;
    $('run-loading').textContent = 'Loading execution report…';
    $('use-run').hidden = true;
    selectedRun = null;
    const response = await fetch(`/runs/${encodeURIComponent(runId)}/report.json`);
    if (!response.ok) throw Error('Execution report could not be loaded.');
    const run = await response.json();
    if (ticket !== runRequest) return;
    if (run.kind !== 'issue-2283-evidence-run' || run.runId !== runId || run.base !== r.change.base || run.head !== r.change.head || run.reviewVersion !== run.parentReviewVersion + '+run.' + run.runId) throw Error('Execution report does not match this frozen comparison.');
    const body = $('collected-result'); body.replaceChildren();
    body.append(node('p', `Collection: ${run.status.replaceAll('_',' ')}. This is not a product approval.`, 'run-outcome'));
    body.append(node('p', `${run.runId} · ${run.finishedAt} · Checks ${run.checkVersion} · Report version ${run.reviewVersion}`, 'run-metadata'));
    body.append(node('p', 'Both versions use the conditional Roslyn 4.11.0 correction. No full solution or runtime/AOT validation was run.', 'section-note'));
    const sides = node('div', undefined, 'run-sides');
    for (const side of ['base','head']) {
      const column = node('div'); column.append(node('h3', side === 'base' ? 'Base execution' : 'Head execution'));
      for (const [id, check] of Object.entries(run.versions[side].checks)) {
        const item = node('div', undefined, 'run-check');
        item.append(node('strong', `${id}: ${check.status.replaceAll('_',' ')}`), node('p', check.reason));
        if (check.tests) item.append(node('p', `${check.passed} passed / ${check.failed} failed; ${check.tests.length} executed.`));
        if (check.matchesPreviousObservation !== undefined) item.append(node('p', check.matchesPreviousObservation ? 'Matches the previous recorded observation.' : 'Contradiction: differs from the previous observation.', check.matchesPreviousObservation ? 'muted' : 'run-contradiction'));
        if (check.comparisons) {
          const observations = node('details'); observations.append(node('summary', 'Probe case comparisons'));
          for (const comparison of check.comparisons) {
            observations.append(node('h3', comparison.id));
            observations.append(node('p', comparison.matches ? 'Matches previous observation.' : 'Contradiction: observation changed.', comparison.matches ? 'muted' : 'run-contradiction'));
            observations.append(node('p', 'Observed: ' + JSON.stringify(comparison.actual)));
            if (!comparison.matches) observations.append(node('p', 'Previously expected: ' + JSON.stringify(comparison.expected)));
          }
          item.append(observations);
        }
        column.append(item);
      }
      sides.append(column);
    }
    body.append(sides);
    for (const contradiction of run.contradictions) body.append(node('p', 'Contradiction: ' + contradiction, 'run-contradiction'));
    if (run.environmentError) body.append(node('p', 'Environment: ' + run.environmentError, 'run-contradiction'));
    const raw = node('div', undefined, 'links');
    raw.append(link('Structured run JSON', `/runs/${runId}/report.json`)); body.append(raw);
    const details = node('details'); details.append(node('summary', 'Executed commands, exit codes and logs'));
    const commands = node('ol', undefined, 'command-list');
    for (const command of run.commands) {
      const item = node('li'); item.append(node('strong', `${command.id} · ${command.status} · exit ${command.exitCode === null ? 'unavailable' : command.exitCode}`), node('code', command.argv.join(' ')), link('Command log', `/runs/${runId}/${command.log}`)); commands.append(item);
    }
    details.append(commands); body.append(details);
    const inputs = node('details'); inputs.append(node('summary', 'Shared harness and Roslyn patch provenance'));
    inputs.append(node('p', run.inputs.identicalAcrossVersions === true ? 'Verified identical test source, probe source/project and Roslyn patch hashes in both versions.' : 'Identical complete inputs could not be verified. Do not infer a passing comparison.'));
    for (const path of run.artifacts.filter(path => path.startsWith('inputs/') || path.endsWith('setup.patch'))) inputs.append(link(path, `/runs/${runId}/${path}`), document.createElement('br'));
    body.append(inputs);
    selectedRun = run;
    $('use-run').hidden = false;
    $('run-loading').hidden = true;
    $('run-select').disabled = false;
  }
  async function loadRuns() {
    try {
      const response = await fetch('/runs/index.json');
      if (!response.ok) throw Error('Saved run index could not be loaded.');
      const index = await response.json();
      if (index.errors.length) { $('run-load-error').hidden = false; $('run-load-error').textContent = 'Some saved runs are invalid: ' + index.errors.map(e => e.path + ': ' + e.error).join('; '); }
      if (!index.runs.length && new URL(location.href).searchParams.has('run')) throw Error('The requested run is missing.');
      if (!index.runs.length) { $('run-loading').textContent = 'No completed collection reports yet. Run python3 trust-demo/collect_evidence.py locally.'; return; }
      for (const run of index.runs) {
        const option = node('option', `${run.runId} · ${run.status}`); option.value = run.runId; $('run-select').append(option);
      }
      $('run-select').hidden = false;
      const requested = new URL(location.href).searchParams.get('run');
      if (requested && !index.runs.some(run => run.runId === requested)) throw Error('The requested run is missing. Its decision scope was not restored.');
      if (requested) $('run-select').value = requested;
      await displayRun($('run-select').value);
      if (requested) setScope({version:selectedRun.reviewVersion, base:selectedRun.base, head:selectedRun.head}, selectedRun.runId);
      $('run-select').addEventListener('change', () => displayRun($('run-select').value).catch(showRunError));
    } catch (error) { showRunError(error); }
  }
  function showRunError(error) {
    $('run-select').disabled = false;
    $('run-loading').hidden = true; $('use-run').hidden = true;
    selectedRun = null;
    $('run-load-error').hidden = false;
    $('run-load-error').textContent = 'Execution evidence unavailable: ' + error.message + ' The original saved assessment is still shown.';
    if (new URL(location.href).searchParams.has('run')) {
      saved = null; $('export').disabled = true;
      $('decision-status').textContent = 'Pending human review';
      $('decision-scope').textContent = 'Requested execution report unavailable. No decision can be recorded for it.';
      $('decision-form').hidden = true;
      $('original-scope').hidden = false;
    }
  }
  async function loadAIReviews(restoreRequested = false) {
    const response = await fetch('/ai/reviews');
    if (!response.ok) throw Error('Saved AI reviews could not be loaded. Earlier results remain stored.');
    const history = await response.json();
    if (!Array.isArray(history.reviews)) throw Error('Invalid saved-review index.');
    const container = $('ai-history'); container.replaceChildren();
    if (history.errors.length) container.append(node('p', 'Some stored reviews are invalid or unavailable.', 'run-contradiction'));
    if (!history.reviews.length) container.append(node('p', 'No new model reviews have been completed. The saved example above is separate.', 'section-note'));
    const requested = new URL(location.href).searchParams.get('aiReview');
    let restored = false;
    for (const review of history.reviews) {
      const article = node('article', undefined, 'ai-result');
      article.append(node('h3', `${review.reviewId} · ${review.status.replaceAll('_',' ')}`));
      article.append(node('p', `Evidence run: ${review.evidenceRunId}. Service: ${review.service || 'not selected'}. Model: ${review.model || 'not selected'}.`, 'run-metadata'));
      if (review.providerMetadata) {
        const m = review.providerMetadata;
        article.append(node('p', `Anthropic request: ${m.requestId || 'unavailable'} · message: ${m.messageId || 'unavailable'} · stop: ${m.stopReason || 'unavailable'}. Usage: ${JSON.stringify(m.usage)}. Usage-priced estimate: ${m.actualCostEstimateUSD === null ? 'unavailable' : '$' + m.actualCostEstimateUSD + ' USD (not an invoice)'}.`, 'run-metadata'));
      }
      if (review.providerTransport) article.append(node('p', 'Provider transport metadata: ' + JSON.stringify(review.providerTransport), 'run-metadata'));
      if (review.status !== 'completed') {
        article.append(node('p', `${review.error?.code || 'unavailable'}: ${review.error?.message || 'No valid model result.'}`, 'run-contradiction'));
      } else if (review.kind === 'issue-2283-ai-review' && review.base === r.change.base && review.head === r.change.head && review.reviewVersion === review.reviewId) {
        article.append(node('p', 'New model assessment, not the saved example and not a human approval. Reference existence does not verify a claim.', 'section-note'));
        const result = review.result;
        article.append(node('h3', 'Requirement assessment'));
        for (const item of result.requirements) article.append(node('p', `${item.id} · ${item.status} · ${item.title}: ${item.rationale}`));
        article.append(node('h3', 'Findings'));
        if (!result.findings.length) article.append(node('p', 'No findings returned; this does not establish correctness.'));
        for (const item of result.findings) {
          article.append(node('h3', `${item.id} · ${item.severity} · ${item.title}`), node('p', item.explanation));
        }
        const checks = node('details'); checks.append(node('summary', 'Reference checks · existence only'));
        for (const check of review.referenceChecks) checks.append(node('p', `${check.owner}: ${typeof check.reference === 'string' ? check.reference : JSON.stringify(check.reference)} · ${check.status}. ${check.explanation}`, check.status === 'unverified' ? 'run-contradiction' : 'muted'));
        article.append(checks);
        for (const [key,label] of [['uncertainties','Uncertainties'],['unchecked','Not checked'],['humanQuestions','Questions for a human']]) {
          article.append(node('h3', label)); const list = node('ul');
          if (!result[key].length) list.append(node('li', 'None stated by the model; this is not independent validation.'));
          result[key].forEach(text => list.append(node('li', text))); article.append(list);
        }
        const use = node('button', 'Use AI review as decision scope', 'secondary'); use.type = 'button'; use.classList.add('ai-use-scope'); use.dataset.reviewId = review.reviewId;
        const bind = () => setScope({version:review.reviewVersion,base:review.base,head:review.head,aiReviewId:review.reviewId,evidenceRunId:review.evidenceRunId},review.evidenceRunId,review.reviewId);
        use.addEventListener('click', () => { bind(); $('decision').scrollIntoView(); $('owner').focus(); });
        article.append(use);
        if (restoreRequested && requested === review.reviewId) { bind(); restored = true; }
        const provenance = node('details'); provenance.append(node('summary', 'AI review provenance'));
        provenance.append(node('p', `Input SHA-256: ${review.inputSha256}; instruction SHA-256: ${review.instructionsSha256}.`, 'run-metadata'));
        provenance.append(link('Input snapshot', `/ai/reviews/${review.reviewId}/input.json`), document.createElement('br'), link('Instruction snapshot', `/ai/reviews/${review.reviewId}/instructions.txt`)); article.append(provenance);
      }
      article.append(document.createElement('br'),link('Review record JSON', `/ai/reviews/${review.reviewId}/review.json`)); container.append(article);
    }
    if (restoreRequested && requested && !restored) {
      saved = null; $('decision-form').hidden = true; $('original-scope').hidden = false; $('export').disabled = true;
      $('decision-status').textContent = 'Pending human review';
      $('decision-scope').textContent = 'Requested AI review is unavailable or incomplete; no old decision is applied.';
    }
  }
  async function loadAIConfig() {
    try {
      const response = await fetch('/ai/config'); if (!response.ok) throw Error('Configuration status unavailable.');
      const config = await response.json();
      requiresPreflight = config.requiresPreflight === true;
      $('prepare-ai').hidden = !requiresPreflight;
      if (requiresPreflight) $('run-ai').disabled = true;
      $('ai-config').textContent = config.configured ? 'Model service configured on the server. A new review sends the selected material to that provider.' : 'Not configured: ' + config.missing.join('; ') + '. No genuine model run is available yet.';
    } catch (error) { $('ai-config').textContent = error.message; }
  }
  $('prepare-ai').addEventListener('click', async () => {
    if (!selectedRun) { $('ai-status').textContent = 'Select an evidence run first.'; return; }
    aiQuote = null; $('run-ai').disabled = true; $('prepare-ai').disabled = true;
    $('ai-cost').textContent = 'Checking model access and counting the full input on Anthropic. No generation request is sent.';
    const runId = selectedRun.runId;
    try {
      const response = await fetch('/ai/preflight', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({runId})});
      const quote = await response.json();
      if (!response.ok) throw Error(quote.error ? `${quote.error.code}: ${quote.error.message}${quote.error.details ? ' Details: ' + JSON.stringify(quote.error.details) : ''}` : 'Preflight failed. No generation sent.');
      if (selectedRun?.runId !== runId) throw Error('Evidence selection changed. Check tokens again.');
      aiQuote = quote;
      $('ai-cost').textContent = `${quote.resolvedModel}: ${quote.inputTokens.toLocaleString('en-US')} counted input tokens; output limit ${quote.maxOutputTokens.toLocaleString('en-US')} including thinking; context ${quote.contextCapacity.toLocaleString('en-US')}. Estimated cost using the full output limit: $${quote.estimatedUSDWithMaxOutput.toFixed(4)}; with input safety margin: $${quote.estimatedUSDWithMargin.toFixed(4)} USD. Token count and cost are estimates, not an invoice. Quote valid 10 minutes, one generation only. Click Run AI review to send the paid request.`;
      $('run-ai').disabled = false;
    } catch (error) { $('ai-cost').textContent = 'Preflight unavailable: ' + error.message; }
    finally { $('prepare-ai').disabled = false; }
  });
  $('run-ai').addEventListener('click', async () => {
    if (!selectedRun) { $('ai-status').textContent = 'Select an available evidence run first.'; return; }
    if (requiresPreflight && !aiQuote) { $('ai-status').textContent = 'Check tokens and cost before generation.'; return; }
    const quoteId = aiQuote?.quoteId; aiQuote = null;
    $('run-ai').disabled = true; $('ai-status').textContent = 'Requesting a server-side AI review…';
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 325000);
    try {
      const response = await fetch('/ai/reviews', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(quoteId ? {runId:selectedRun.runId,quoteId} : {runId:selectedRun.runId}),signal:controller.signal});
      const review = await response.json();
      if (!response.ok || review.status !== 'completed') $('ai-status').textContent = `${review.error?.code || 'review_failed'}: ${review.error?.message || 'No valid model review was returned.'} Previous results are preserved.`;
      else $('ai-status').textContent = `AI review ${review.reviewId} completed. It requires its own human decision.`;
      await loadAIReviews();
    } catch (error) { $('ai-status').textContent = error.name === 'AbortError' ? 'The request timed out. Previous results remain stored; refresh history to check the server record.' : 'The review request failed. Previous results remain stored.'; }
    finally { clearTimeout(timer); $('run-ai').disabled = requiresPreflight; }
  });
  loadAIConfig();
  loadAIReviews(true).catch(error => {
    $('ai-status').textContent = error.message;
    if (new URL(location.href).searchParams.has('aiReview')) { saved = null; $('decision-form').hidden = true; $('original-scope').hidden = false; $('export').disabled = true; }
  });
  loadRuns();
  $('loading').hidden = true;
  $('content').hidden = false;
}
main().catch(error => {
  $('loading').hidden = true;
  $('content').hidden = true; $('fatal').hidden = false;
  $('fatal').textContent = 'The recorded review could not be loaded or validated. No assessment or decision is shown. ' + error.message;
});
