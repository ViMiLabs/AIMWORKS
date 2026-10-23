from __future__ import annotations

"""Static documentation assets for the characterization SPARQL workbench."""

from html import escape
from pathlib import Path
from typing import Any


def characterization_body(
    report: dict[str, Any] | None,
    page_path: Path,
    docs_root: Path,
) -> str:
    report = report or {}
    data_href = _relative(page_path, docs_root / "characterization_kg" / "characterization_query_workbench.json")
    artifact_root = _relative(page_path, docs_root / "characterization_kg")
    cases = report.get("case_count", 8)
    fields = report.get("represented_field_count", 0)
    findings = report.get("validation_finding_count", 0)
    triples = report.get("rdf_triple_count", 0)
    query_validation = report.get("query_validation", {})
    passed = query_validation.get("passed_query_count", 0)
    query_count = query_validation.get("query_count", 0)
    matched = query_validation.get("matched_row_count", 0)
    if not report:
        return """
<section class="kg-intro"><p class="eyebrow">SPARQL application</p><h2>Characterization query package unavailable</h2><p>Run the characterization build before generating documentation.</p></section>
"""
    return f"""
<section class="kg-intro">
  <div>
    <p class="eyebrow">Workbook-backed RDF application</p>
    <h2>Validated SPARQL competency workbench</h2>
    <p>Explore release-tested queries over eight H₂KG-aligned characterization cases. Every observed row is checked against an expectation independently derived from the sanitized workbook manifest. This evaluates source-conformant retrieval, not scientific correctness or general search performance.</p>
  </div>
  <div class="kg-metrics" aria-label="Knowledge graph metrics">
    <span><strong>{passed}/{query_count}</strong> queries passed</span><span><strong>{matched:,}</strong> rows matched</span><span><strong>{fields:,}</strong> source fields</span><span><strong>{triples:,}</strong> RDF triples</span>
  </div>
</section>

<section class="kg-workbench" id="characterization-kg-root" data-package="{escape(data_href)}" data-artifact-root="{escape(artifact_root)}">
  <header class="kg-validation-head">
    <div><p class="eyebrow">Ground-truth validation</p><h2>Expected and observed results</h2><p>The build uses exact row-multiset comparison. Missing rows, unexpected rows, and duplicate-count differences cause publication to fail.</p></div>
    <div id="kg-validation-summary" class="kg-validation-summary" aria-live="polite">Loading validation package...</div>
  </header>
  <div id="kg-validation-matrix" class="kg-table-wrap kg-validation-matrix"></div>

  <div class="kg-main-grid">
    <article class="kg-query card">
      <p class="eyebrow">SPARQL query and result</p>
      <h2>Inspect a tested competency query</h2>
      <div class="kg-controls">
        <div><label for="kg-query-select">Query example</label><select id="kg-query-select"></select></div>
        <div><label for="kg-result-filter">Filter displayed rows</label><input id="kg-result-filter" type="search" placeholder="Filter any result value" autocomplete="off"></div>
      </div>
      <p id="kg-query-purpose" class="kg-purpose"></p>
      <textarea id="kg-query-editor" spellcheck="false" aria-label="SPARQL query editor"></textarea>
      <div class="kg-query-actions">
        <button id="kg-show-result" type="button">Show validated result</button>
        <button id="kg-download-query" type="button">Download SPARQL</button>
        <button id="kg-observed-csv" type="button">Observed CSV</button>
        <button id="kg-observed-json" type="button">Observed JSON</button>
        <button id="kg-expected-csv" type="button">Ground truth CSV</button>
        <button id="kg-expected-json" type="button">Ground truth JSON</button>
      </div>
      <p id="kg-query-note" class="kg-status" aria-live="polite"></p>
    </article>

    <aside class="kg-downloads card">
      <p class="eyebrow">Reproducibility</p><h2>Download artifacts</h2>
      <a href="{artifact_root}/characterization_knowledge_graph.trig" download>Named graphs · TriG</a>
      <a href="{artifact_root}/characterization_knowledge_graph.ttl" download>Flattened graph · Turtle</a>
      <a href="{artifact_root}/characterization_knowledge_graph.jsonld" download>Flattened graph · JSON-LD</a>
      <a href="{artifact_root}/characterization_shapes.ttl" download>SHACL shapes</a>
      <a href="{artifact_root}/query_ground_truth/query_ground_truth_validation.csv" download>Query validation · CSV</a>
      <a href="{artifact_root}/query_ground_truth/query_ground_truth_validation.json" download>Query validation · JSON</a>
      <a href="{artifact_root}/source_semantic_mapping_registry.csv" download>Source mapping registry</a>
      <a href="{artifact_root}/characterization_source_manifest.json" download>Sanitized source manifest</a>
      <a href="{artifact_root}/run_demo.py" download>RDFLib runner</a>
      <a href="{artifact_root}/characterization_kg_demo.ipynb" download>Jupyter notebook</a>
      <div class="kg-integrity"><strong>Release checks</strong><span>Cases</span><code>{cases}</code><span>Source coverage</span><code>{report.get('source_coverage_percent', 0):.2f}%</code><span>Explicit findings</span><code>{findings:,}</code><span>SHACL</span><code>{'conforms' if report.get('shacl_conforms') else 'does not conform'}</code><span>RDF parity</span><code>{'isomorphic' if report.get('turtle_jsonld_isomorphic') else 'not verified'}</code></div>
    </aside>
  </div>

  <section id="kg-selected-validation" class="kg-selected-validation" aria-live="polite"></section>
  <div class="kg-results-grid">
    <article class="kg-result-panel"><div class="kg-panel-title"><p class="eyebrow">SPARQL output</p><h3>Observed RDFLib result</h3></div><div id="kg-query-results" class="kg-table-wrap"></div></article>
    <article class="kg-result-panel"><div class="kg-panel-title"><p class="eyebrow">Independent expectation</p><h3>Workbook-derived ground truth</h3></div><div id="kg-expected-results" class="kg-table-wrap"></div></article>
  </div>
  <section class="kg-differences"><div class="kg-panel-title"><p class="eyebrow">Exact comparison</p><h3>Missing and unexpected rows</h3></div><div id="kg-differences"></div></section>
</section>
"""


def characterization_css() -> str:
    return r"""
:root { --kg-ink:#16313a; --kg-muted:#587078; --kg-line:#cadadd; --kg-teal:#167d70; --kg-blue:#356f9f; --kg-amber:#b26b12; --kg-red:#a44231; --kg-soft:#f5faf9; }
.kg-intro { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:2rem; align-items:end; margin:1.2rem 0; padding:1.45rem; border:1px solid var(--kg-line); border-radius:18px; background:radial-gradient(circle at 4% 5%,rgba(22,125,112,.13),transparent 28%),linear-gradient(130deg,#f4fbf9,#fff8eb); box-shadow:0 18px 45px rgba(23,55,65,.08); }
.kg-intro h2,.kg-workbench h2,.kg-workbench h3 { margin:.2rem 0 .5rem; color:var(--kg-ink); }.kg-intro p { max-width:870px; }
.kg-metrics { display:grid; grid-template-columns:repeat(2,minmax(135px,1fr)); gap:.55rem; }.kg-metrics span { padding:.68rem .82rem; border:1px solid #d8e3e4; border-radius:12px; background:rgba(255,255,255,.92); color:var(--kg-muted); white-space:nowrap; }.kg-metrics strong { display:block; color:var(--kg-teal); font-size:1.3rem; }
.kg-workbench { overflow:hidden; border:1px solid var(--kg-line); border-radius:18px; background:#fff; box-shadow:0 18px 48px rgba(19,48,57,.09); }
.kg-validation-head { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:1.5rem; align-items:center; padding:1.15rem 1.25rem; background:linear-gradient(120deg,#eff9f6,#faf6ec); border-bottom:1px solid #dbe5e7; }.kg-validation-head p { margin:.25rem 0; max-width:820px; }
.kg-validation-summary { min-width:235px; padding:.8rem 1rem; border:1px solid #afd2c8; border-radius:12px; background:#fff; color:#31565d; font-size:.82rem; }.kg-validation-summary strong { display:block; color:#0b6d61; font-size:1.45rem; }.kg-validation-summary.fail { border-color:#d7a59a; color:var(--kg-red); }
.kg-validation-matrix { max-height:360px; margin:0; border:0; border-bottom:1px solid #dbe5e7; border-radius:0; }
.kg-main-grid { display:grid; grid-template-columns:minmax(0,1.8fr) minmax(285px,.65fr); gap:1rem; padding:1rem; background:#f7faf9; }.kg-query.card,.kg-downloads.card { margin:0; }
.kg-controls { display:grid; grid-template-columns:minmax(260px,1fr) minmax(220px,.55fr); gap:.75rem; margin:.8rem 0; }.kg-query label { display:block; margin-bottom:.3rem; color:#36535c; font-size:.8rem; font-weight:750; }.kg-query select,.kg-query input { width:100%; padding:.65rem .72rem; border:1px solid #aebfc4; border-radius:8px; background:#fff; color:var(--kg-ink); }.kg-purpose { min-height:2.4rem; margin:.4rem 0; color:var(--kg-muted); }
.kg-query textarea { width:100%; min-height:330px; padding:.85rem; resize:vertical; border:1px solid #829aa0; border-radius:10px; background:#10252d; color:#e8f6f4; font:12px/1.55 Consolas,monospace; tab-size:2; }.kg-query-actions { display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.7rem; }.kg-query-actions button { min-height:40px; padding:.5rem .72rem; border:1px solid var(--kg-teal); border-radius:8px; background:#fff; color:#0b625b; font-weight:750; cursor:pointer; }.kg-query-actions button:hover { color:#fff; background:var(--kg-teal); }.kg-query .kg-status { margin:.65rem 0 0; padding:.65rem .75rem; border:1px solid #d7e4e4; border-radius:8px; background:#f8fbfb; color:var(--kg-muted); font-size:.82rem; }
.kg-downloads { display:flex; flex-direction:column; gap:.45rem; align-self:start; }.kg-downloads a { padding:.57rem .68rem; border:1px solid #bdd1d4; border-radius:8px; color:#0a6967; text-decoration:none; font-weight:700; background:#fbfdfd; }.kg-downloads a:hover { background:#e8f6f3; }.kg-integrity { display:grid; grid-template-columns:auto 1fr; gap:.3rem .65rem; margin-top:.6rem; padding:.78rem; border-radius:10px; background:#edf4f3; }.kg-integrity strong { grid-column:1/-1; margin-bottom:.2rem; }.kg-integrity span { color:#5d7077; font-size:.75rem; }.kg-integrity code { overflow-wrap:anywhere; white-space:normal; font-size:.72rem; }
.kg-selected-validation { display:grid; grid-template-columns:repeat(6,minmax(110px,1fr)); gap:.65rem; padding:1rem; border-top:1px solid #dbe5e7; border-bottom:1px solid #dbe5e7; background:#fff; }.kg-check { padding:.7rem; border:1px solid #cddddd; border-radius:10px; background:#f9fcfb; color:#587078; font-size:.74rem; }.kg-check strong { display:block; margin-top:.2rem; color:var(--kg-ink); font-size:1rem; }.kg-check.pass { border-color:#9acbbd; background:#eef9f5; }.kg-check.fail { border-color:#d8a69c; background:#fff4f1; }
.kg-results-grid { display:grid; grid-template-columns:1fr 1fr; gap:1rem; padding:1rem; }.kg-result-panel,.kg-differences { min-width:0; border:1px solid #d5e1e3; border-radius:12px; background:#fff; overflow:hidden; }.kg-panel-title { padding:.78rem .9rem; background:#f3f8f7; border-bottom:1px solid #d5e1e3; }.kg-panel-title p { margin:0; }.kg-panel-title h3 { margin:.15rem 0 0; font-size:1rem; }
.kg-table-wrap { max-height:470px; overflow:auto; }.kg-table-wrap table { width:100%; border-collapse:collapse; font-size:.75rem; }.kg-table-wrap th { position:sticky; top:0; z-index:1; padding:.55rem; text-align:left; background:#e6f1ef; color:#24464f; white-space:nowrap; }.kg-table-wrap td { padding:.48rem .55rem; border-top:1px solid #e0e8e9; max-width:300px; overflow-wrap:anywhere; vertical-align:top; }.kg-table-wrap tr:nth-child(even) td { background:#fbfdfd; }.kg-empty { margin:0; padding:1rem; color:var(--kg-muted); }
.kg-pill { display:inline-block; min-width:52px; padding:.18rem .45rem; border-radius:999px; text-align:center; font-weight:800; font-size:.7rem; text-transform:uppercase; letter-spacing:.04em; }.kg-pill.pass { color:#086157; background:#dff3ed; }.kg-pill.fail { color:#8c3224; background:#fde7e2; }
.kg-differences { margin:0 1rem 1rem; }.kg-difference-grid { display:grid; grid-template-columns:1fr 1fr; gap:1rem; padding:1rem; }.kg-difference-grid h4 { margin:.1rem 0 .45rem; }.kg-difference-grid .kg-table-wrap { max-height:300px; border:1px solid #e0e8e9; border-radius:8px; }
@media(max-width:1050px){.kg-intro,.kg-validation-head,.kg-main-grid,.kg-results-grid{grid-template-columns:1fr}.kg-validation-summary{min-width:0}.kg-selected-validation{grid-template-columns:repeat(3,1fr)}}
@media(max-width:680px){.kg-metrics,.kg-controls,.kg-difference-grid{grid-template-columns:1fr}.kg-selected-validation{grid-template-columns:1fr 1fr}.kg-query-actions button{flex:1 1 45%}.kg-query textarea{min-height:280px}}
"""


def characterization_js() -> str:
    return r"""
(() => {
  const root = document.getElementById('characterization-kg-root');
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const querySelect=$('kg-query-select'), queryEditor=$('kg-query-editor'), queryPurpose=$('kg-query-purpose'), queryNote=$('kg-query-note');
  const observedContainer=$('kg-query-results'), expectedContainer=$('kg-expected-results'), differences=$('kg-differences'), filter=$('kg-result-filter');
  let data=null, current=null;

  fetch(root.dataset.package).then((response) => {
    if(!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }).then((payload) => {
    data=payload;
    renderSummary(payload.validation_summary);
    renderMatrix(payload.queries);
    payload.queries.forEach((item) => { const option=document.createElement('option'); option.value=item.id; option.textContent=`${item.id.replace(/^q(\d+)_.*$/,'Q$1')} · ${item.title}`; querySelect.append(option); });
    querySelect.value=payload.default_query || payload.queries[0]?.id || '';
    syncQuery();
  }).catch((error) => {
    $('kg-validation-summary').textContent=`Query package unavailable: ${error.message}`;
    $('kg-validation-summary').classList.add('fail');
  });

  querySelect.addEventListener('change',syncQuery);
  filter.addEventListener('input',renderSelected);
  $('kg-show-result').addEventListener('click',showValidatedResult);
  $('kg-download-query').addEventListener('click',()=>current&&download(`${current.id}.rq`,queryEditor.value,'application/sparql-query'));
  $('kg-observed-csv').addEventListener('click',()=>downloadRows('observed','csv'));
  $('kg-observed-json').addEventListener('click',()=>downloadRows('observed','json'));
  $('kg-expected-csv').addEventListener('click',()=>downloadRows('expected','csv'));
  $('kg-expected-json').addEventListener('click',()=>downloadRows('expected','json'));

  function renderSummary(summary){
    const ok=summary.failed_query_count===0;
    const target=$('kg-validation-summary');
    target.classList.toggle('fail',!ok);
    target.innerHTML=`<strong>${summary.passed_query_count}/${summary.query_count} queries passed</strong>${summary.matched_row_count} of ${summary.expected_row_count} expected rows matched exactly.<br><small>${esc(summary.method)}</small>`;
  }
  function renderMatrix(queries){
    const variables=['Query','Competency example','Expected','Observed','Matched','Missing','Unexpected','Status'];
    const rows=queries.map((query)=>{const v=query.validation;return {Query:query.id.replace(/^q(\d+)_.*$/,'Q$1'),'Competency example':query.title,Expected:v.expected_row_count,Observed:v.observed_row_count,Matched:v.matched_row_count,Missing:v.missing_expected_row_count,Unexpected:v.unexpected_row_count,Status:`<span class="kg-pill ${v.status}">${v.status}</span>`};});
    renderTable($('kg-validation-matrix'),variables,rows,'No validation results.',true);
  }
  function syncQuery(){
    current=data?.queries.find((item)=>item.id===querySelect.value);
    if(!current)return;
    queryEditor.value=current.query;
    queryPurpose.textContent=`${current.purpose} Ground truth: ${current.ground_truth_basis}`;
    filter.value='';
    queryNote.textContent=`Release-tested with RDFLib: ${current.validation.observed_row_count} observed row(s), ${current.validation.expected_row_count} expected row(s).`;
    renderSelected();
  }
  function showValidatedResult(){
    if(!current)return;
    if(normalize(queryEditor.value)!==normalize(current.query)){
      queryNote.textContent='The query has been edited. This static page displays only the release-tested snapshot. Download the query and use run_demo.py or the notebook to execute arbitrary SPARQL with RDFLib.';
      return;
    }
    queryNote.textContent=`Validated snapshot loaded: ${current.validation.matched_row_count} matched, ${current.validation.missing_expected_row_count} missing, ${current.validation.unexpected_row_count} unexpected.`;
    renderSelected();
  }
  function renderSelected(){
    if(!current)return;
    const term=filter.value.trim().toLowerCase();
    const keep=(row)=>!term||JSON.stringify(row).toLowerCase().includes(term);
    const observed=(current.rows||[]).filter(keep), expected=(current.expected_rows||[]).filter(keep), v=current.validation;
    renderChecks(v);
    renderTable(observedContainer,current.variables||[],observed,'No observed rows match the current filter.');
    renderTable(expectedContainer,current.variables||[],expected,'No expected rows match the current filter.');
    renderDifferences(v);
  }
  function renderChecks(v){
    const checks=[['Overall',v.status],['Expected',v.expected_row_count],['Observed',v.observed_row_count],['Matched',v.matched_row_count],['Row precision',`${v.row_precision_percent}%`],['Row recall',`${v.row_recall_percent}%`]];
    $('kg-selected-validation').innerHTML=checks.map(([label,value],index)=>`<div class="kg-check ${index===0?v.status:''}">${esc(label)}<strong>${esc(value)}</strong></div>`).join('');
  }
  function renderDifferences(v){
    differences.innerHTML=`<div class="kg-difference-grid"><div><h4>Missing expected rows (${v.missing_expected_row_count})</h4><div id="kg-missing-table" class="kg-table-wrap"></div></div><div><h4>Unexpected observed rows (${v.unexpected_row_count})</h4><div id="kg-unexpected-table" class="kg-table-wrap"></div></div></div>`;
    renderTable($('kg-missing-table'),[...(current.variables||[]),'occurrences'],v.missing_expected_rows||[],'None.');
    renderTable($('kg-unexpected-table'),[...(current.variables||[]),'occurrences'],v.unexpected_rows||[],'None.');
  }
  function renderTable(container,variables,rows,emptyMessage,allowHtml=false){
    if(!rows.length){container.innerHTML=`<p class="kg-empty">${esc(emptyMessage)}</p>`;return;}
    container.innerHTML=`<table><thead><tr>${variables.map((item)=>`<th>${esc(item)}</th>`).join('')}</tr></thead><tbody>${rows.map((row)=>`<tr>${variables.map((item)=>`<td>${allowHtml&&item==='Status'?row[item]:esc(row[item]??'')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }
  function downloadRows(kind,format){
    if(!current)return;
    const rows=kind==='expected'?(current.expected_rows||[]):(current.rows||[]), variables=current.variables||[];
    if(format==='json'){download(`${current.id}_${kind}.json`,JSON.stringify({variables,rows},null,2),'application/json');return;}
    const quote=(value)=>`"${String(value??'').replace(/"/g,'""')}"`;
    download(`${current.id}_${kind}.csv`,[variables.map(quote).join(','),...rows.map((row)=>variables.map((key)=>quote(row[key])).join(','))].join('\n'),'text/csv');
  }
  function normalize(value){return String(value||'').replace(/\s+/g,' ').trim();}
  function download(name,content,type){const blob=new Blob([content],{type}),url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
})();
"""


def _relative(page_path: Path, target: Path) -> str:
    import os

    return Path(os.path.relpath(target, page_path.parent)).as_posix()
