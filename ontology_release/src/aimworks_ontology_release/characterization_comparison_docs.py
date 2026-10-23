from __future__ import annotations

"""Static documentation for the fair H2KG-CHAMEO benchmark."""

from html import escape
from pathlib import Path
from typing import Any


def _relative(page_path: Path, target: Path) -> str:
    import os

    return Path(os.path.relpath(target, page_path.parent)).as_posix()


def comparison_body(
    report: dict[str, Any] | None,
    page_path: Path,
    docs_root: Path,
) -> str:
    if not report:
        return """
<section class="cb-intro"><p class="eyebrow">Comparative benchmark</p><h2>Benchmark package unavailable</h2><p>Build the H2KG-CHAMEO comparison before generating documentation.</p></section>
"""
    summary = report["balanced_benchmark"]
    conclusion = report["balanced_conclusion"]
    package_href = _relative(
        page_path,
        docs_root / "characterization_kg_comparison" / "comparison_query_workbench.json",
    )
    artifact_root = _relative(page_path, docs_root / "characterization_kg_comparison")
    kg_href = _relative(page_path, docs_root / "pages" / "characterization-knowledge-graph.html")
    expected_rows = sum(
        int(row["expected_rows"])
        for row in report.get("balanced_requirement_matrix", [])
    )
    h2kg_exact = summary["h2kg"]["exact_requirements"]
    chameo_exact = summary["chameo"]["exact_requirements"]
    requirement_count = summary["requirement_count"]
    return f"""
<section class="cb-intro">
  <div class="cb-intro-copy">
    <p class="eyebrow">Controlled ontology application benchmark</p>
    <h2>One source corpus. Two native semantic models.</h2>
    <p>H₂KG and CHAMEO were mapped independently from the same sanitized eight-case characterization manifest. The frozen requirements, expected rows, and conclusion rules were fixed before ontology-specific SPARQL was executed. Neither ontology was modified, and no local semantic bridge was admitted to either scored graph.</p>
    <div class="cb-actions"><a class="cb-button primary" href="#comparison-workbench">Inspect the evidence</a><a class="cb-button" href="{escape(kg_href)}">Open the H₂KG application</a></div>
  </div>
  <div class="cb-scoreboard" aria-label="Benchmark headline results">
    <div><span>H₂KG exact</span><strong>{h2kg_exact}/{requirement_count}</strong><small>{100*h2kg_exact/requirement_count:.1f}%</small></div>
    <div><span>CHAMEO exact</span><strong>{chameo_exact}/{requirement_count}</strong><small>{100*chameo_exact/requirement_count:.1f}%</small></div>
    <div><span>Expected rows</span><strong>{expected_rows}</strong><small>across eight cases</small></div>
    <div><span>Import closure</span><strong>{report['source_lock']['resolved_import_count']}</strong><small>CHAMEO/EMMO modules</small></div>
  </div>
</section>

<section class="cb-protocol" aria-labelledby="cb-protocol-title">
  <div class="cb-section-head"><p class="eyebrow">Fairness controls</p><h2 id="cb-protocol-title">How the comparison was kept symmetric</h2></div>
  <div class="cb-protocol-grid">
    <article><span>01</span><h3>Common source</h3><p>Both ABoxes begin with the same 1,635 eligible workbook fields and eight cases.</p></article>
    <article><span>02</span><h3>Independent mapping</h3><p>Each graph uses its own ontology and declared imports; neither graph is translated from the other.</p></article>
    <article><span>03</span><h3>Frozen expectations</h3><p>Thirteen lifecycle requirements produce 501 manifest-derived expected rows before querying.</p></article>
    <article><span>04</span><h3>Auditable decision</h3><p>Five hashed rules must all pass before the complementarity conclusion is emitted.</p></article>
  </div>
</section>

<section class="cb-conclusion">
  <p class="eyebrow">Computed outcome</p>
  <blockquote>{escape(conclusion['statement'])}</blockquote>
  <p>{escape(conclusion['scope'])}</p>
</section>

<section class="cb-workbench" id="comparison-workbench" data-package="{escape(package_href)}" data-artifact-root="{escape(artifact_root)}">
  <header class="cb-workbench-head">
    <div><p class="eyebrow">SPARQL and RDF evidence</p><h2>Trace every benchmark outcome</h2><p>Select a plain-language requirement and ontology. The result table is the frozen RDFLib output; selecting a row renders only the RDF statements that support that answer.</p></div>
    <div id="cb-load-status" class="cb-load-status" aria-live="polite">Loading benchmark package...</div>
  </header>

  <div id="cb-requirement-matrix" class="cb-table-wrap cb-matrix"></div>

  <div class="cb-controls">
    <label><span>Plain-language requirement</span><select id="cb-requirement-select"></select></label>
    <label><span>Ontology model</span><select id="cb-ontology-select"><option value="h2kg">H₂KG</option><option value="chameo">CHAMEO</option></select></label>
    <label><span>Filter result rows</span><input id="cb-result-filter" type="search" placeholder="Type any displayed value" autocomplete="off"></label>
  </div>

  <article class="cb-question-card">
    <div><p class="eyebrow">Scientific question</p><h3 id="cb-question"></h3><p id="cb-source-basis"></p></div>
    <div id="cb-outcome" class="cb-outcome"></div>
  </article>

  <div class="cb-query-grid">
    <article class="cb-panel cb-query-panel">
      <div class="cb-panel-head"><div><p class="eyebrow">Ontology-specific SPARQL</p><h3 id="cb-query-title">Validated query</h3></div><button id="cb-copy-query" type="button">Copy query</button></div>
      <textarea id="cb-query" spellcheck="false" aria-label="Ontology-specific SPARQL"></textarea>
      <p id="cb-rationale" class="cb-note"></p>
    </article>
    <aside class="cb-panel cb-downloads">
      <p class="eyebrow">Reproducibility</p><h3>Download benchmark evidence</h3>
      <a href="{artifact_root}/benchmark_contract.json" download>Frozen contract · JSON</a>
      <a href="{artifact_root}/balanced_requirement_matrix.csv" download>Requirement matrix · CSV</a>
      <a href="{artifact_root}/balanced_conclusion_rules.json" download>Conclusion rules · JSON</a>
      <a href="{artifact_root}/ontology_evidence_audit.json" download>Ontology evidence audit</a>
      <a href="{artifact_root}/strict_h2kg_semantic_graph.ttl" download>H₂KG scored graph · Turtle</a>
      <a href="{artifact_root}/strict_chameo_semantic_graph.ttl" download>CHAMEO scored graph · Turtle</a>
      <a href="{artifact_root}/native_benchmark_report.json" download>Complete report · JSON</a>
    </aside>
  </div>

  <div class="cb-results-grid">
    <article class="cb-panel"><div class="cb-panel-head"><div><p class="eyebrow">Observed</p><h3>SPARQL result rows</h3></div><button id="cb-results-csv" type="button">Download CSV</button></div><div id="cb-observed" class="cb-table-wrap"></div></article>
    <article class="cb-panel"><div class="cb-panel-head"><div><p class="eyebrow">Expected</p><h3>Manifest-derived ground truth</h3></div></div><div id="cb-expected" class="cb-table-wrap"></div></article>
  </div>

  <section class="cb-evidence">
    <header class="cb-evidence-head">
      <div><p class="eyebrow">Query evidence subgraph</p><h2>Why this row is returned</h2><p>Choose a row to see its compact RDF support. Solid arrows are asserted predicates; absent required paths are reported as gaps rather than invented.</p></div>
      <label><span>Result row</span><select id="cb-row-select"></select></label>
    </header>
    <div class="cb-graph-shell">
      <svg id="cb-evidence-graph" role="img" aria-label="RDF evidence graph"></svg>
      <aside id="cb-node-inspector" class="cb-node-inspector"><strong>Select a node</strong><span>Its type and IRI will appear here.</span></aside>
    </div>
    <p id="cb-graph-note" class="cb-note"></p>
    <div class="cb-legend"><span class="workflow">Workflow</span><span class="process">Process</span><span class="measurement">Measurement</span><span class="matter">Matter</span><span class="parameter">Parameter</span><span class="data">Data/result</span><span class="property">Property</span><span class="instrument">Instrument/software</span><span class="literal">Value/unit</span></div>
  </section>

  <section class="cb-differences"><div><p class="eyebrow">Exact row-multiset comparison</p><h2>Missing and additional answers</h2></div><div id="cb-difference-summary"></div></section>
</section>
"""


def comparison_css() -> str:
    return r"""
:root{--cb-ink:#142e36;--cb-muted:#5b7078;--cb-line:#c9d8d9;--cb-teal:#0d786f;--cb-blue:#316e9e;--cb-amber:#b46b18;--cb-violet:#75539a;--cb-cyan:#347f90;--cb-red:#a74634;--cb-paper:#fffdf8;}
.cb-intro{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(330px,.65fr);gap:1.2rem;margin:1.2rem 0 1.5rem;padding:1.55rem;border:1px solid var(--cb-line);border-radius:24px;background:radial-gradient(circle at 3% 4%,rgba(13,120,111,.18),transparent 28%),linear-gradient(135deg,#f4fbf9,#fff7e9);box-shadow:0 20px 54px rgba(20,46,54,.1)}
.cb-intro h2,.cb-protocol h2,.cb-workbench h2,.cb-evidence h2,.cb-differences h2{margin:.15rem 0 .55rem;color:var(--cb-ink)}.cb-intro p{max-width:820px;line-height:1.65}.cb-actions{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:1rem}.cb-button{display:inline-flex;padding:.62rem .9rem;border:1px solid var(--cb-teal);border-radius:999px;color:var(--cb-teal);text-decoration:none;font-weight:750;background:#fff}.cb-button.primary{color:#fff;background:var(--cb-teal)}
.cb-scoreboard{display:grid;grid-template-columns:1fr 1fr;gap:.65rem}.cb-scoreboard div{padding:.9rem;border:1px solid #d7e3e2;border-radius:15px;background:rgba(255,255,255,.9)}.cb-scoreboard span,.cb-scoreboard small{display:block;color:var(--cb-muted);font-size:.75rem}.cb-scoreboard strong{display:block;margin:.12rem 0;color:var(--cb-teal);font:700 1.65rem/1.1 "Iowan Old Style",Georgia,serif}
.cb-protocol{margin:1.5rem 0}.cb-section-head{display:flex;align-items:end;justify-content:space-between;gap:1rem}.cb-protocol-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}.cb-protocol-grid article{position:relative;padding:1rem;border:1px solid var(--cb-line);border-radius:16px;background:rgba(255,255,255,.82);box-shadow:0 12px 30px rgba(20,46,54,.06)}.cb-protocol-grid article>span{color:var(--cb-amber);font-weight:800;letter-spacing:.12em}.cb-protocol-grid h3{margin:.4rem 0}.cb-protocol-grid p{margin:0;color:var(--cb-muted);font-size:.9rem;line-height:1.5}
.cb-conclusion{margin:1.5rem 0;padding:1.35rem 1.5rem;border-left:5px solid var(--cb-teal);border-radius:0 18px 18px 0;background:linear-gradient(120deg,#eaf7f3,#fff)}.cb-conclusion blockquote{margin:.25rem 0 .7rem;font:700 clamp(1.18rem,2.2vw,1.65rem)/1.35 "Iowan Old Style",Georgia,serif;color:var(--cb-ink)}.cb-conclusion p:last-child{margin-bottom:0;color:var(--cb-muted)}
.cb-workbench{overflow:hidden;border:1px solid var(--cb-line);border-radius:22px;background:#fff;box-shadow:0 22px 58px rgba(20,46,54,.1)}.cb-workbench-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:1.2rem;align-items:center;padding:1.25rem;background:linear-gradient(120deg,#eff9f6,#fff8ed);border-bottom:1px solid var(--cb-line)}.cb-workbench-head p{max-width:850px;margin:.25rem 0}.cb-load-status{min-width:230px;padding:.8rem 1rem;border:1px solid #acd0c6;border-radius:12px;background:#fff;color:var(--cb-muted)}.cb-load-status strong{display:block;color:var(--cb-teal);font-size:1.15rem}
.cb-table-wrap{overflow:auto;max-height:450px}.cb-table-wrap table{width:100%;border-collapse:collapse;font-size:.78rem}.cb-table-wrap th{position:sticky;top:0;z-index:2;padding:.58rem;text-align:left;background:#e6f1ef;color:#26464e;white-space:nowrap}.cb-table-wrap td{padding:.52rem .58rem;border-top:1px solid #e0e8e8;vertical-align:top;max-width:310px;overflow-wrap:anywhere}.cb-table-wrap tr:nth-child(even) td{background:#fbfdfc}.cb-table-wrap tr[data-row-key]{cursor:pointer}.cb-table-wrap tr[data-row-key]:hover td,.cb-table-wrap tr.selected td{background:#e8f6f2}.cb-matrix{max-height:390px;border-bottom:1px solid var(--cb-line)}
.cb-status{display:inline-flex;padding:.2rem .48rem;border-radius:999px;font-size:.68rem;font-weight:850;text-transform:uppercase;letter-spacing:.04em}.cb-status.exact{color:#075e54;background:#dff3ed}.cb-status.partial{color:#80510b;background:#fff0ce}.cb-status.not_expressible_without_extension{color:#893725;background:#fde7df}
.cb-controls{display:grid;grid-template-columns:minmax(300px,1.4fr) minmax(170px,.45fr) minmax(220px,.65fr);gap:.8rem;padding:1rem;background:#f7faf9;border-bottom:1px solid var(--cb-line)}.cb-controls label,.cb-evidence-head label{display:grid;gap:.32rem;color:#3c5961;font-size:.78rem;font-weight:750}.cb-controls select,.cb-controls input,.cb-evidence-head select{width:100%;padding:.68rem .75rem;border:1px solid #aebfc2;border-radius:9px;background:#fff;color:var(--cb-ink)}
.cb-question-card{display:grid;grid-template-columns:minmax(0,1fr) minmax(270px,.42fr);gap:1rem;align-items:center;padding:1.1rem 1.2rem;border-bottom:1px solid var(--cb-line)}.cb-question-card h3{margin:.15rem 0;font-size:1.22rem}.cb-question-card p{margin:.35rem 0;color:var(--cb-muted)}.cb-outcome{display:grid;grid-template-columns:1fr 1fr;gap:.45rem}.cb-outcome div{padding:.58rem;border:1px solid #d5e1e2;border-radius:10px;background:#f9fcfb;font-size:.72rem;color:var(--cb-muted)}.cb-outcome strong{display:block;margin-top:.15rem;color:var(--cb-ink);font-size:.92rem}
.cb-query-grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(280px,.55fr);gap:1rem;padding:1rem;background:#f7faf9}.cb-panel{min-width:0;overflow:hidden;border:1px solid #d3e0e1;border-radius:14px;background:#fff}.cb-panel-head{display:flex;align-items:center;justify-content:space-between;gap:.8rem;padding:.75rem .9rem;border-bottom:1px solid #d8e3e4;background:#f2f7f6}.cb-panel-head h3{margin:.12rem 0}.cb-panel-head p{margin:0}.cb-panel-head button,.cb-results-grid button{padding:.48rem .68rem;border:1px solid var(--cb-teal);border-radius:8px;background:#fff;color:var(--cb-teal);font-weight:750;cursor:pointer}.cb-query-panel textarea{width:100%;min-height:315px;padding:.85rem;border:0;resize:vertical;background:#10272e;color:#eaf7f4;font:12px/1.55 Consolas,monospace}.cb-note{margin:0;padding:.72rem .85rem;color:var(--cb-muted);font-size:.82rem;line-height:1.5}.cb-downloads{display:flex;flex-direction:column;gap:.45rem;padding:.9rem;align-self:start}.cb-downloads h3{margin:.15rem 0 .45rem}.cb-downloads a{padding:.57rem .68rem;border:1px solid #bdd1d3;border-radius:8px;color:#096b68;text-decoration:none;font-weight:700;background:#fbfdfd}.cb-downloads a:hover{background:#e8f6f3}
.cb-results-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;padding:1rem}.cb-empty{margin:0;padding:1rem;color:var(--cb-muted)}
.cb-evidence{margin:0 1rem 1rem;border:1px solid #d3e0e1;border-radius:16px;background:#fff;overflow:hidden}.cb-evidence-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(310px,.45fr);gap:1rem;align-items:center;padding:1rem;background:linear-gradient(120deg,#edf7f5,#fff8ed);border-bottom:1px solid var(--cb-line)}.cb-evidence-head p{margin:.2rem 0;max-width:780px}.cb-graph-shell{position:relative;min-height:390px;background:radial-gradient(circle at 15% 10%,rgba(13,120,111,.08),transparent 27%),#fbfdfc}.cb-graph-shell svg{display:block;width:100%;min-height:390px}.cb-node-inspector{position:absolute;right:.8rem;bottom:.8rem;display:grid;gap:.2rem;max-width:380px;padding:.65rem .75rem;border:1px solid #c7d7d8;border-radius:10px;background:rgba(255,255,255,.94);box-shadow:0 8px 24px rgba(20,46,54,.1);font-size:.73rem}.cb-node-inspector span{color:var(--cb-muted);overflow-wrap:anywhere}.cb-graph-edge{stroke:#617b82;stroke-width:1.7;fill:none}.cb-graph-edge-label{font:11px Aptos,"Segoe UI",sans-serif;fill:#425e66;paint-order:stroke;stroke:#fbfdfc;stroke-width:5px;stroke-linejoin:round}.cb-graph-node{cursor:pointer}.cb-graph-node rect{stroke-width:1.6;filter:drop-shadow(0 5px 8px rgba(20,46,54,.08))}.cb-graph-node text{pointer-events:none;fill:#17333b;font:700 12px Aptos,"Segoe UI",sans-serif}.cb-graph-node text.type{font-size:9px;font-weight:600;fill:#60757c}.cb-graph-node.workflow rect{fill:#edf2f3;stroke:#667b82}.cb-graph-node.process rect{fill:#e7f0fa;stroke:#356f9f}.cb-graph-node.measurement rect{fill:#e3eff9;stroke:#2f6898}.cb-graph-node.matter rect{fill:#e4f3ef;stroke:#268779}.cb-graph-node.parameter rect{fill:#fff0d8;stroke:#b46b18}.cb-graph-node.data rect{fill:#f0e9f8;stroke:#7654a0}.cb-graph-node.property rect{fill:#e3f2f4;stroke:#347f90}.cb-graph-node.instrument rect,.cb-graph-node.software rect{fill:#edf0f2;stroke:#728087}.cb-graph-node.technique rect,.cb-graph-node.class rect{fill:#f7ebdc;stroke:#b66728}.cb-graph-node.quantity rect,.cb-graph-node.literal rect,.cb-graph-node.unit rect{fill:#fff5df;stroke:#c17a20}.cb-legend{display:flex;flex-wrap:wrap;gap:.45rem;padding:.75rem 1rem;border-top:1px solid #dce5e6}.cb-legend span{padding:.25rem .5rem;border-radius:999px;font-size:.68rem;font-weight:750;background:#eef3f3;color:#3d5960}
.cb-differences{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.65fr);gap:1rem;align-items:center;padding:1rem 1.2rem;border-top:1px solid var(--cb-line);background:#f7faf9}.cb-difference-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:.45rem}.cb-difference-cards div{padding:.6rem;border:1px solid #d4e0e1;border-radius:10px;background:#fff;color:var(--cb-muted);font-size:.7rem}.cb-difference-cards strong{display:block;color:var(--cb-ink);font-size:1rem}
@media(max-width:1050px){.cb-intro,.cb-workbench-head,.cb-query-grid,.cb-results-grid,.cb-question-card,.cb-evidence-head,.cb-differences{grid-template-columns:1fr}.cb-protocol-grid{grid-template-columns:1fr 1fr}.cb-load-status{min-width:0}.cb-node-inspector{position:static;margin:.7rem}}
@media(max-width:700px){.cb-scoreboard,.cb-protocol-grid,.cb-controls,.cb-outcome,.cb-difference-cards{grid-template-columns:1fr}.cb-query-panel textarea{min-height:250px}.cb-graph-shell{overflow:auto}.cb-graph-shell svg{min-width:800px}.cb-intro{padding:1rem}}
"""


def comparison_js() -> str:
    return r"""
(() => {
  const root=document.getElementById('comparison-workbench');
  if(!root)return;
  const $=(id)=>document.getElementById(id);
  const esc=(value)=>String(value??'').replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const reqSelect=$('cb-requirement-select'),ontologySelect=$('cb-ontology-select'),filter=$('cb-result-filter'),rowSelect=$('cb-row-select');
  let data=null,current=null,currentModel=null,evidence=null;
  const evidenceCache=new Map();

  fetch(root.dataset.package).then((response)=>{if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json();}).then((payload)=>{
    data=payload;
    renderMatrix();
    payload.requirements.forEach((item)=>{const option=document.createElement('option');option.value=item.id;option.textContent=`${item.id.slice(0,3).toUpperCase()} · ${item.question}`;reqSelect.append(option);});
    reqSelect.value=payload.default_requirement||payload.requirements[0].id;
    ontologySelect.value=payload.default_ontology||'h2kg';
    $('cb-load-status').innerHTML=`<strong>${payload.summary.requirement_count} requirements loaded</strong>${payload.summary.h2kg.exact_requirements} H₂KG exact · ${payload.summary.chameo.exact_requirements} CHAMEO exact`;
    syncRequirement();
  }).catch((error)=>{$('cb-load-status').textContent=`Benchmark package unavailable: ${error.message}`;$('cb-load-status').classList.add('fail');});

  reqSelect.addEventListener('change',syncRequirement);
  ontologySelect.addEventListener('change',syncRequirement);
  filter.addEventListener('input',renderTables);
  rowSelect.addEventListener('change',renderEvidence);
  $('cb-copy-query').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('cb-query').value);$('cb-copy-query').textContent='Copied';setTimeout(()=>{$('cb-copy-query').textContent='Copy query';},1200);}catch{download('query.rq',$('cb-query').value,'application/sparql-query');}});
  $('cb-results-csv').addEventListener('click',()=>{if(!current||!currentModel)return;downloadRows(current.id,current.variables,currentModel.rows);});

  function renderMatrix(){
    const rows=data.requirements.map((item)=>({id:item.id,question:item.question,expected:item.expected_rows.length,h2kg:item.ontologies.h2kg.status,chameo:item.ontologies.chameo.status}));
    $('cb-requirement-matrix').innerHTML=`<table><thead><tr><th>ID</th><th>Plain-language requirement</th><th>Expected rows</th><th>H₂KG</th><th>CHAMEO</th></tr></thead><tbody>${rows.map((row)=>`<tr><td>${esc(row.id.slice(0,3).toUpperCase())}</td><td>${esc(row.question)}</td><td>${row.expected}</td><td>${statusPill(row.h2kg)}</td><td>${statusPill(row.chameo)}</td></tr>`).join('')}</tbody></table>`;
  }
  async function syncRequirement(){
    current=data.requirements.find((item)=>item.id===reqSelect.value);
    currentModel=current?.ontologies[ontologySelect.value];
    if(!current||!currentModel)return;
    filter.value='';
    $('cb-question').textContent=current.question;
    $('cb-source-basis').textContent=`Ground-truth basis: ${current.source_basis}`;
    $('cb-query-title').textContent=`${ontologySelect.value==='h2kg'?'H₂KG':'CHAMEO'} query`;
    $('cb-query').value=currentModel.query;
    $('cb-rationale').textContent=currentModel.rationale;
    const c=currentModel.comparison;
    $('cb-outcome').innerHTML=`<div>Status<strong>${statusPill(currentModel.status)}</strong></div><div>Representation<strong>${esc(currentModel.representation_tier.replaceAll('_',' '))}</strong></div><div>Matched<strong>${c.matched_row_count}/${c.expected_row_count}</strong></div><div>Additional<strong>${c.unexpected_row_count}</strong></div>`;
    renderTables();
    const href=`${root.dataset.artifactRoot}/${currentModel.evidence_path}`;
    try{
      evidence=evidenceCache.get(href);
      if(!evidence){const response=await fetch(href);if(!response.ok)throw new Error(`HTTP ${response.status}`);evidence=await response.json();evidenceCache.set(href,evidence);}
      populateRowSelect();renderEvidence();
    }catch(error){$('cb-graph-note').textContent=`Evidence graph unavailable: ${error.message}`;drawGraph({nodes:[],edges:[],message:'Evidence unavailable.'});}
    renderDifferences();
  }
  function statusPill(value){return `<span class="cb-status ${esc(value)}">${esc(value.replaceAll('_',' '))}</span>`;}
  function signature(row){return JSON.stringify(current.variables.map((key)=>String(row[key]??'')));}
  function rowSummary(row){return current.variables.filter((key)=>key!=='caseKey').slice(0,3).map((key)=>row[key]).filter(Boolean).join(' · ')||row.caseKey||'row';}
  function populateRowSelect(){
    rowSelect.innerHTML='';
    const observed=new Map(currentModel.rows.map((row)=>[signature(row),row]));
    const expected=new Map(current.expected_rows.map((row)=>[signature(row),row]));
    const keys=[...observed.keys(),...expected.keys()].filter((key,index,array)=>array.indexOf(key)===index);
    keys.forEach((key)=>{const row=observed.get(key)||expected.get(key);const option=document.createElement('option');option.value=key;const state=observed.has(key)?(expected.has(key)?'Matched':'Additional'):'Missing';option.textContent=`${state} · ${rowSummary(row)}`;rowSelect.append(option);});
    if(keys.length)rowSelect.value=keys[0];
  }
  function renderTables(){
    if(!current||!currentModel)return;
    const term=filter.value.trim().toLowerCase();
    const keep=(row)=>!term||JSON.stringify(row).toLowerCase().includes(term);
    renderTable($('cb-observed'),current.variables,currentModel.rows.filter(keep),'No observed rows.',true);
    renderTable($('cb-expected'),current.variables,current.expected_rows.filter(keep),'No expected rows.',true);
  }
  function renderTable(container,variables,rows,empty,clickable){
    if(!rows.length){container.innerHTML=`<p class="cb-empty">${esc(empty)}</p>`;return;}
    container.innerHTML=`<table><thead><tr>${clickable?'<th>Evidence</th>':''}${variables.map((key)=>`<th>${esc(key)}</th>`).join('')}</tr></thead><tbody>${rows.map((row)=>{const key=signature(row);return `<tr data-row-key="${esc(key)}">${clickable?'<td><button type="button" class="cb-view-row">View graph</button></td>':''}${variables.map((name)=>`<td>${esc(row[name]??'')}</td>`).join('')}</tr>`;}).join('')}</tbody></table>`;
    container.querySelectorAll('tr[data-row-key]').forEach((tr)=>tr.addEventListener('click',()=>{if([...rowSelect.options].some((option)=>option.value===tr.dataset.rowKey)){rowSelect.value=tr.dataset.rowKey;renderEvidence();document.querySelector('.cb-evidence').scrollIntoView({behavior:'smooth',block:'start'});}}));
  }
  function renderDifferences(){
    const c=currentModel.comparison;
    $('cb-difference-summary').innerHTML=`<div class="cb-difference-cards"><div>Expected<strong>${c.expected_row_count}</strong></div><div>Observed<strong>${c.observed_row_count}</strong></div><div>Missing<strong>${c.missing_expected_row_count}</strong></div><div>Additional<strong>${c.unexpected_row_count}</strong></div></div>`;
  }
  function renderEvidence(){
    if(!evidence||!current)return;
    const entry=evidence.entries.find((item)=>item.signature===rowSelect.value)||evidence.entries[0];
    if(!entry){drawGraph({nodes:[],edges:[],message:'No result row is available.'});return;}
    drawGraph(entry.graph);
    $('cb-graph-note').textContent=`${entry.graph.message}${entry.graph.truncated?' The displayed neighborhood was capped at 24 predicates.':''}`;
    document.querySelectorAll('tr[data-row-key]').forEach((tr)=>tr.classList.toggle('selected',tr.dataset.rowKey===entry.signature));
  }
  function drawGraph(graph){
    const svg=$('cb-evidence-graph');
    const nodes=graph.nodes||[],edges=graph.edges||[];
    if(!nodes.length){svg.setAttribute('viewBox','0 0 960 320');svg.innerHTML='<text x="480" y="160" text-anchor="middle" fill="#63777d">No asserted RDF path is available for this expected answer.</text>';$('cb-node-inspector').innerHTML='<strong>No evidence node</strong><span>The required native relation is absent.</span>';return;}
    const byId=new Map(nodes.map((node)=>[node.id,node]));
    const incoming=new Map(nodes.map((node)=>[node.id,0]));
    edges.forEach((edge)=>incoming.set(edge.target,(incoming.get(edge.target)||0)+1));
    let roots=nodes.filter((node)=>(incoming.get(node.id)||0)===0).map((node)=>node.id);
    if(!roots.length)roots=[nodes[0].id];
    const depth=new Map(roots.map((id)=>[id,0]));
    const queue=[...roots];
    while(queue.length){const id=queue.shift(),base=depth.get(id)||0;edges.filter((edge)=>edge.source===id).forEach((edge)=>{const next=Math.min(base+1,4);if(!depth.has(edge.target)||depth.get(edge.target)>next){depth.set(edge.target,next);queue.push(edge.target);}});}
    nodes.forEach((node)=>{if(!depth.has(node.id))depth.set(node.id,Math.min(3,Math.max(0,...depth.values())+1));});
    const groups=new Map();nodes.forEach((node)=>{const level=depth.get(node.id)||0;if(!groups.has(level))groups.set(level,[]);groups.get(level).push(node);});
    const levels=[...groups.keys()].sort((a,b)=>a-b),maxRows=Math.max(...[...groups.values()].map((items)=>items.length));
    const width=1000,height=Math.max(360,maxRows*92+70),left=35,right=35,nodeW=188,nodeH=58;
    const positions=new Map();levels.forEach((level,column)=>{const items=groups.get(level);const x=left+(levels.length===1?(width-nodeW-left-right)/2:column*(width-nodeW-left-right)/Math.max(1,levels.length-1));const gap=(height-50-items.length*nodeH)/Math.max(1,items.length+1);items.forEach((node,index)=>positions.set(node.id,{x,y:25+gap*(index+1)+nodeH*index}));});
    const marker='<defs><marker id="cb-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#617b82"/></marker></defs>';
    const edgeSvg=edges.map((edge)=>{const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)return'';const x1=a.x+nodeW,y1=a.y+nodeH/2,x2=b.x,y2=b.y+nodeH/2,mx=(x1+x2)/2;return `<path class="cb-graph-edge" marker-end="url(#cb-arrow)" d="M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}"><title>${esc(edge.predicate)}</title></path><text class="cb-graph-edge-label" x="${mx}" y="${(y1+y2)/2-5}" text-anchor="middle">${esc(short(edge.label,28))}</text>`;}).join('');
    const nodeSvg=nodes.map((node)=>{const p=positions.get(node.id),label=short(node.label,27),type=short(node.type,30);return `<g class="cb-graph-node ${esc(node.role||'other')}" data-node-id="${esc(node.id)}" transform="translate(${p.x},${p.y})"><rect width="${nodeW}" height="${nodeH}" rx="11"/><text x="${nodeW/2}" y="25" text-anchor="middle">${esc(label)}</text><text class="type" x="${nodeW/2}" y="43" text-anchor="middle">${esc(type)}</text><title>${esc(node.label)}\n${esc(node.iri||node.type)}</title></g>`;}).join('');
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.innerHTML=marker+edgeSvg+nodeSvg;
    svg.querySelectorAll('.cb-graph-node').forEach((element)=>element.addEventListener('click',()=>{const node=byId.get(element.dataset.nodeId);$('cb-node-inspector').innerHTML=`<strong>${esc(node.label)}</strong><span>${esc(node.type)} · ${esc(node.role)}</span><span>${esc(node.iri||'Literal value')}</span>`;}));
  }
  function short(value,max){const text=String(value??'');return text.length>max?`${text.slice(0,max-1)}…`:text;}
  function downloadRows(id,variables,rows){const quote=(value)=>`"${String(value??'').replaceAll('"','""')}"`;download(`${id}_${ontologySelect.value}_results.csv`,[variables.map(quote).join(','),...rows.map((row)=>variables.map((key)=>quote(row[key])).join(','))].join('\n'),'text/csv');}
  function download(name,content,type){const blob=new Blob([content],{type}),url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
})();
"""
