from __future__ import annotations

"""Static documentation assets for the characterization knowledge graph."""

from html import escape
from pathlib import Path
from typing import Any


def characterization_body(
    report: dict[str, Any] | None,
    page_path: Path,
    docs_root: Path,
) -> str:
    report = report or {}
    data_href = _relative(page_path, docs_root / "characterization_kg" / "characterization_web_graph.json")
    artifact_root = _relative(page_path, docs_root / "characterization_kg")
    cases = report.get("case_count", 8)
    fields = report.get("represented_field_count", 0)
    findings = report.get("validation_finding_count", 0)
    triples = report.get("rdf_triple_count", 0)
    if not report:
        return """
<section class="kg-intro"><p class="eyebrow">Application graph</p><h2>Characterization knowledge graph unavailable</h2><p>Run the characterization build before generating documentation.</p></section>
"""
    return f"""
<section class="kg-intro">
  <div>
    <p class="eyebrow">Workbook-backed application graph</p>
    <h2>Search the characterization workflow evidence</h2>
    <p>Eight source-fidelity case graphs are connected to H₂KG 2.3.0 occurrence semantics without changing the ontology taxonomy. TEM opens by default. Missing, unconfirmed, unresolved-unit, and conflicting values remain visible instead of being normalized away.</p>
  </div>
  <div class="kg-metrics" aria-label="Knowledge graph metrics">
    <span><strong>{cases}</strong> cases</span><span><strong>{fields:,}</strong> source fields</span><span><strong>{triples:,}</strong> RDF triples</span><span><strong>{findings:,}</strong> explicit findings</span>
  </div>
</section>

<section class="kg-app" id="characterization-kg-root" data-graph="{escape(data_href)}" data-artifact-root="{escape(artifact_root)}">
  <header class="kg-toolbar">
    <div><label for="kg-case">Method case</label><select id="kg-case"></select></div>
    <div class="kg-search-wrap"><label for="kg-search">Search nodes and source values</label><input id="kg-search" type="search" placeholder="e.g. working distance, ImageJ, 5 nm" autocomplete="off"></div>
    <fieldset><legend>Visible layers</legend><label><input id="kg-layer-semantic" type="checkbox" checked> Semantic</label><label><input id="kg-layer-source" type="checkbox"> Source fields</label><label><input id="kg-layer-validation" type="checkbox"> Findings</label></fieldset>
    <button id="kg-reset" type="button">Reset view</button>
  </header>
  <p id="kg-status" class="kg-status" aria-live="polite">Loading the local graph package...</p>
  <div class="kg-stage">
    <div class="kg-graph-panel">
      <svg id="kg-graph" role="img" aria-label="Interactive characterization knowledge graph"></svg>
      <div class="kg-legend"><span class="matter">Matter</span><span class="process">Process</span><span class="measurement">Measurement</span><span class="instrument">Instrument</span><span class="parameter">Parameter</span><span class="data">Data</span><span class="property">Property</span><span class="source">Source field</span><span class="validation">Finding</span></div>
    </div>
    <aside id="kg-inspector" class="kg-inspector"><p class="eyebrow">Node inspector</p><h3>Select a node</h3><p>Click a node to inspect its H₂KG types, source status, provenance, and connected relations.</p></aside>
  </div>
</section>

<section class="kg-lower-grid">
  <article class="kg-query card">
    <p class="eyebrow">SPARQL competency workspace</p>
    <h2>Run the release-tested queries</h2>
    <p>The static page shows deterministic RDFLib results for the five published query files. Edit or download a query, then use the bundled script or notebook for unrestricted local SPARQL execution.</p>
    <label for="kg-query-select">Query preset</label><select id="kg-query-select"></select>
    <textarea id="kg-query-editor" spellcheck="false" aria-label="SPARQL query editor"></textarea>
    <div class="kg-query-actions"><button id="kg-run-query" type="button">Run tested query</button><button id="kg-download-query" type="button">Download .rq</button><button id="kg-result-csv" type="button">Export CSV</button><button id="kg-result-json" type="button">Export JSON</button></div>
    <p id="kg-query-note" class="kg-status"></p>
    <div id="kg-query-results" class="kg-table-wrap"></div>
  </article>
  <aside class="kg-downloads card">
    <p class="eyebrow">Reproducibility package</p><h2>Download artifacts</h2>
    <a href="{artifact_root}/characterization_knowledge_graph.trig" download>Named graph dataset (.trig)</a>
    <a href="{artifact_root}/characterization_knowledge_graph.nq" download>Named graph dataset (.nq)</a>
    <a href="{artifact_root}/characterization_knowledge_graph.ttl" download>Flattened graph (.ttl)</a>
    <a href="{artifact_root}/characterization_knowledge_graph.jsonld" download>Flattened graph (.jsonld)</a>
    <a href="{artifact_root}/characterization_shapes.ttl" download>SHACL shapes</a>
    <a href="{artifact_root}/characterization_source_manifest.json" download>Sanitized source manifest</a>
    <a href="{artifact_root}/source_semantic_mapping_registry.csv" download>Source-to-semantic registry</a>
    <a href="{artifact_root}/source_coverage_report.csv" download>Source coverage report</a>
    <a href="{artifact_root}/unit_registry.csv" download>QUDT unit registry</a>
    <a href="{artifact_root}/validation_report.json" download>Validation report</a>
    <a href="{artifact_root}/run_demo.py" download>RDFLib demonstration script</a>
    <a href="{artifact_root}/characterization_kg_demo.ipynb" download>Reproducible notebook</a>
    <div class="kg-integrity"><strong>Source integrity</strong><span>Workbook SHA-256</span><code>{escape(str(report.get('source_sha256', '')))}</code><span>Coverage</span><code>{report.get('source_coverage_percent', 0):.2f}%</code><span>SHACL</span><code>{'conforms' if report.get('shacl_conforms') else 'does not conform'}</code><span>RDF parity</span><code>{'isomorphic' if report.get('turtle_jsonld_isomorphic') else 'not verified'}</code></div>
  </aside>
</section>
"""


def characterization_css() -> str:
    return r"""
:root { --kg-ink:#16313a; --kg-muted:#587078; --kg-line:#cadadd; --kg-teal:#167d70; --kg-blue:#356f9f; --kg-amber:#b26b12; --kg-violet:#7e55a6; --kg-cyan:#3b8791; --kg-gray:#74828a; }
.kg-intro { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:2rem; align-items:end; margin:1.2rem 0; padding:1.35rem; border:1px solid var(--kg-line); border-radius:18px; background:radial-gradient(circle at 4% 5%,rgba(22,125,112,.12),transparent 27%),linear-gradient(130deg,#f5fbfa,#fff9ed); box-shadow:0 18px 45px rgba(23,55,65,.08); }
.kg-intro h2 { margin:.2rem 0 .5rem; color:var(--kg-ink); }.kg-intro p { max-width:850px; }
.kg-metrics { display:grid; grid-template-columns:repeat(2,minmax(125px,1fr)); gap:.55rem; }.kg-metrics span { padding:.65rem .8rem; border:1px solid #d8e3e4; border-radius:12px; background:rgba(255,255,255,.9); color:var(--kg-muted); white-space:nowrap; }.kg-metrics strong { display:block; color:var(--kg-teal); font-size:1.3rem; }
.kg-app { overflow:hidden; border:1px solid var(--kg-line); border-radius:18px; background:#fff; box-shadow:0 18px 48px rgba(19,48,57,.09); }
.kg-toolbar { display:grid; grid-template-columns:220px minmax(300px,1fr) auto auto; gap:1rem; align-items:end; padding:1rem 1.1rem; border-bottom:1px solid #dbe5e7; background:linear-gradient(120deg,#f2faf8,#f9f6ef); }
.kg-toolbar label,.kg-query label { display:block; margin-bottom:.3rem; color:#36535c; font-size:.8rem; font-weight:750; }.kg-toolbar select,.kg-toolbar input,.kg-query select { width:100%; padding:.62rem .7rem; border:1px solid #aebfc4; border-radius:8px; background:#fff; color:var(--kg-ink); }
.kg-toolbar fieldset { display:flex; gap:.65rem; align-items:center; min-height:43px; margin:0; padding:.38rem .65rem; border:1px solid #bccdd1; border-radius:9px; }.kg-toolbar fieldset label { display:flex; gap:.25rem; align-items:center; margin:0; white-space:nowrap; }.kg-toolbar legend { padding:0 .2rem; font-size:.72rem; font-weight:750; color:#506970; }
.kg-toolbar button,.kg-query-actions button { min-height:40px; padding:.48rem .72rem; border:1px solid var(--kg-teal); border-radius:8px; background:#fff; color:#0b625b; font-weight:750; cursor:pointer; }.kg-toolbar button:hover,.kg-query-actions button:hover { color:#fff; background:var(--kg-teal); }
.kg-status { min-height:1.3rem; margin:0; padding:.55rem 1.1rem; color:var(--kg-muted); font-size:.82rem; border-bottom:1px solid #e1e9ea; }
.kg-stage { display:grid; grid-template-columns:minmax(0,1fr) 340px; min-height:720px; }.kg-graph-panel { position:relative; min-width:0; height:720px; overflow:auto; background:radial-gradient(circle at 25% 12%,rgba(22,125,112,.08),transparent 24%),linear-gradient(#fff,#fbfdfd); }
#kg-graph { display:block; width:1800px; height:900px; min-width:100%; }.kg-edge { stroke:#9aadb2; stroke-width:1.25; opacity:.54; }.kg-edge.semantic { stroke:#53727b; opacity:.65; }.kg-edge.validation { stroke:#b36c1d; stroke-dasharray:6 5; }.kg-node { cursor:pointer; }.kg-node rect { stroke-width:2; rx:8; }.kg-node text { pointer-events:none; font:12px Aptos,Segoe UI,sans-serif; fill:#16313a; }.kg-node.is-match rect { stroke:#b34f16; stroke-width:4; filter:drop-shadow(0 4px 4px rgba(179,79,22,.24)); }.kg-node.is-selected rect { stroke:#102f39; stroke-width:4; }
.kg-node.matter rect { fill:#dff1ed; stroke:#258675; }.kg-node.manufacturing rect,.kg-node.process rect { fill:#e5eef7; stroke:#427cad; }.kg-node.measurement rect { fill:#dceaf8; stroke:#286da3; }.kg-node.instrument rect { fill:#eef1f3; stroke:#74828a; }.kg-node.parameter rect { fill:#fff1d7; stroke:#b26b12; }.kg-node.data rect,.kg-node.datapoint rect { fill:#efe6f7; stroke:#7e55a6; }.kg-node.property rect { fill:#e0f1f3; stroke:#3b8791; }.kg-node.source rect { fill:#f5f6f7; stroke:#8b979c; stroke-dasharray:5 4; }.kg-node.validation rect { fill:#fff0db; stroke:#b36619; stroke-dasharray:6 4; }.kg-node.semantic rect { fill:#eef6f6; stroke:#5b8588; }
.kg-legend { position:sticky; left:1rem; bottom:1rem; display:flex; flex-wrap:wrap; gap:.4rem; width:max-content; max-width:calc(100% - 2rem); padding:.45rem .6rem; border:1px solid #d2dfe1; border-radius:10px; background:rgba(255,255,255,.94); box-shadow:0 8px 22px rgba(22,49,58,.1); font-size:.73rem; }.kg-legend span::before { content:""; display:inline-block; width:.65rem; height:.65rem; margin-right:.25rem; border-radius:3px; vertical-align:-.05rem; }.kg-legend .matter::before{background:#dff1ed}.kg-legend .process::before{background:#e5eef7}.kg-legend .measurement::before{background:#dceaf8}.kg-legend .instrument::before{background:#eef1f3}.kg-legend .parameter::before{background:#fff1d7}.kg-legend .data::before{background:#efe6f7}.kg-legend .property::before{background:#e0f1f3}.kg-legend .source::before{background:#f5f6f7}.kg-legend .validation::before{background:#fff0db}
.kg-inspector { max-height:720px; overflow:auto; padding:1rem 1.1rem; border-left:1px solid #dbe5e7; background:#f8fbfb; }.kg-inspector h3 { margin:.2rem 0 .6rem; }.kg-inspector dl { display:grid; grid-template-columns:92px minmax(0,1fr); gap:.35rem .55rem; font-size:.8rem; }.kg-inspector dt { font-weight:750; color:#425e66; }.kg-inspector dd { margin:0; overflow-wrap:anywhere; }.kg-inspector code { font-size:.72rem; }.kg-relations { display:grid; gap:.35rem; margin-top:.8rem; }.kg-relation { padding:.45rem; border:1px solid #d7e2e4; border-radius:7px; background:#fff; font-size:.77rem; overflow-wrap:anywhere; }
.kg-lower-grid { display:grid; grid-template-columns:minmax(0,1.7fr) minmax(280px,.7fr); gap:1rem; margin-top:1rem; }.kg-query.card,.kg-downloads.card { margin:0; }.kg-query h2,.kg-downloads h2 { margin:.15rem 0 .45rem; }.kg-query textarea { width:100%; min-height:245px; margin-top:.65rem; padding:.8rem; resize:vertical; border:1px solid #9eb2b8; border-radius:9px; background:#10252d; color:#e8f6f4; font:12px/1.55 Consolas,monospace; tab-size:2; }.kg-query-actions { display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.6rem; }.kg-query .kg-status { padding:.45rem 0; border:0; }.kg-table-wrap { max-height:430px; overflow:auto; border:1px solid #d5e1e3; border-radius:9px; }.kg-table-wrap table { width:100%; border-collapse:collapse; font-size:.75rem; }.kg-table-wrap th { position:sticky; top:0; z-index:1; padding:.5rem; text-align:left; background:#e8f2f2; color:#24464f; }.kg-table-wrap td { padding:.45rem .5rem; border-top:1px solid #e0e8e9; max-width:260px; overflow-wrap:anywhere; vertical-align:top; }
.kg-downloads { display:flex; flex-direction:column; gap:.45rem; align-self:start; }.kg-downloads a { padding:.55rem .65rem; border:1px solid #bdd1d4; border-radius:8px; color:#0a6967; text-decoration:none; font-weight:700; background:#f9fcfc; }.kg-downloads a:hover { background:#e8f6f3; }.kg-integrity { display:grid; gap:.3rem; margin-top:.6rem; padding:.75rem; border-radius:10px; background:#f1f5f5; }.kg-integrity strong { margin-bottom:.2rem; }.kg-integrity span { color:#5d7077; font-size:.75rem; }.kg-integrity code { overflow-wrap:anywhere; white-space:normal; font-size:.7rem; }
@media(max-width:1050px){.kg-toolbar{grid-template-columns:1fr 1fr}.kg-stage{grid-template-columns:1fr}.kg-inspector{max-height:none;border-left:0;border-top:1px solid #dbe5e7}.kg-lower-grid{grid-template-columns:1fr}.kg-intro{grid-template-columns:1fr}.kg-graph-panel{height:650px}}
@media(max-width:680px){.kg-toolbar{grid-template-columns:1fr}.kg-toolbar fieldset{flex-wrap:wrap}.kg-metrics{grid-template-columns:1fr 1fr}.kg-query-actions button{flex:1 1 45%}}
"""


def characterization_js() -> str:
    return r"""
(() => {
  const root = document.getElementById('characterization-kg-root');
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const short = (iri) => String(iri || '').split(/[#/]/).filter(Boolean).pop() || String(iri || '');
  const caseSelect=$('kg-case'), search=$('kg-search'), svg=$('kg-graph'), inspector=$('kg-inspector'), status=$('kg-status');
  const layerSemantic=$('kg-layer-semantic'), layerSource=$('kg-layer-source'), layerValidation=$('kg-layer-validation');
  const querySelect=$('kg-query-select'), queryEditor=$('kg-query-editor'), queryResults=$('kg-query-results'), queryNote=$('kg-query-note');
  let data=null, selected=null, currentRows=[];

  fetch(root.dataset.graph).then((response) => { if(!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); }).then((payload) => {
    data=payload;
    payload.cases.forEach((item) => { const option=document.createElement('option'); option.value=item.key; option.textContent=item.title; caseSelect.append(option); });
    caseSelect.value=payload.default_case || 'tem';
    payload.queries.forEach((item) => { const option=document.createElement('option'); option.value=item.id; option.textContent=item.title; querySelect.append(option); });
    querySelect.value=payload.queries[0]?.id || '';
    syncQuery(); render();
  }).catch((error) => { status.textContent=`Knowledge graph unavailable: ${error.message}`; status.classList.add('bad'); });

  [caseSelect,layerSemantic,layerSource,layerValidation].forEach((element)=>element.addEventListener('change',render));
  search.addEventListener('input',render);
  $('kg-reset').addEventListener('click',()=>{search.value='';layerSemantic.checked=true;layerSource.checked=false;layerValidation.checked=false;selected=null;render();});
  querySelect.addEventListener('change',syncQuery);
  $('kg-run-query').addEventListener('click',runQuery);
  $('kg-download-query').addEventListener('click',()=>download(`${querySelect.value}.rq`,queryEditor.value,'application/sparql-query'));
  $('kg-result-csv').addEventListener('click',()=>downloadRows('csv'));
  $('kg-result-json').addEventListener('click',()=>downloadRows('json'));

  function layers(){return new Set([layerSemantic.checked&&'semantic',layerSource.checked&&'source',layerValidation.checked&&'validation'].filter(Boolean));}
  function visibleNodes(){
    const wanted=layers(), term=search.value.trim().toLowerCase();
    return data.nodes.filter((node)=>node.case===caseSelect.value&&wanted.has(node.layer)).map((node)=>({...node,match:!term||JSON.stringify(node).toLowerCase().includes(term)}));
  }
  function render(){
    if(!data)return;
    const nodes=visibleNodes(), nodeMap=new Map(nodes.map((node)=>[node.id,node])), ids=new Set(nodeMap.keys());
    const links=data.links.filter((link)=>link.case===caseSelect.value&&ids.has(link.source)&&ids.has(link.target));
    const positions=layout(nodes); svg.innerHTML=''; svg.setAttribute('viewBox','0 0 1800 900');
    const defs=document.createElementNS('http://www.w3.org/2000/svg','defs'); defs.innerHTML='<marker id="kg-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#718990"/></marker>'; svg.append(defs);
    links.forEach((link)=>{const a=positions.get(link.source),b=positions.get(link.target);if(!a||!b)return;const line=el('line',{x1:a.x+62,y1:a.y+17,x2:b.x-62,y2:b.y+17,class:`kg-edge ${link.layer}`,'marker-end':'url(#kg-arrow)'});const title=el('title');title.textContent=link.label;line.append(title);svg.append(line);});
    nodes.forEach((node)=>{const pos=positions.get(node.id),group=el('g',{class:`kg-node ${node.role}${node.match?' is-match':''}${selected===node.id?' is-selected':''}`,transform:`translate(${pos.x-62},${pos.y})`,tabindex:'0',role:'button'});group.append(el('rect',{width:124,height:35}));const text=el('text',{x:62,y:22,'text-anchor':'middle'});text.textContent=truncate(node.label,19);group.append(text);const title=el('title');title.textContent=node.label;group.append(title);group.addEventListener('click',()=>inspect(node));group.addEventListener('keydown',(event)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();inspect(node);}});svg.append(group);});
    const matches=nodes.filter((node)=>node.match).length;
    status.textContent=`${nodes.length} nodes and ${links.length} relations shown for ${caseSelect.selectedOptions[0]?.textContent || caseSelect.value}${search.value?`; ${matches} search matches`:''}.`;
  }
  function layout(nodes){
    const roleOrder=['source','matter','manufacturing','measurement','instrument','parameter','process','data','datapoint','property','validation','semantic'];
    const grouped=new Map(roleOrder.map((role)=>[role,[]]));nodes.forEach((node)=>(grouped.get(node.role)||grouped.get('semantic')).push(node));
    const positions=new Map();let column=0;
    roleOrder.forEach((role)=>{const items=grouped.get(role);if(!items?.length)return;const lanes=Math.max(1,Math.ceil(items.length/14));items.sort((a,b)=>a.label.localeCompare(b.label)).forEach((node,index)=>{const lane=Math.floor(index/14),row=index%14;positions.set(node.id,{x:100+(column+lane)*155,y:45+row*57});});column+=lanes;});
    return positions;
  }
  function inspect(node){
    selected=node.id;render();const incoming=data.links.filter((link)=>link.case===node.case&&link.target===node.id),outgoing=data.links.filter((link)=>link.case===node.case&&link.source===node.id);const relations=[...incoming.map((link)=>({direction:'←',label:link.label,other:link.source})),...outgoing.map((link)=>({direction:'→',label:link.label,other:link.target}))].slice(0,40);
    inspector.innerHTML=`<p class="eyebrow">${esc(node.layer)} layer · ${esc(node.role)}</p><h3>${esc(node.label)}</h3><dl><dt>IRI</dt><dd><code>${esc(node.id)}</code></dd><dt>Types</dt><dd>${node.types.map((item)=>`<code>${esc(short(item))}</code>`).join(', ')||'not asserted'}</dd>${Object.entries(node.details||{}).map(([key,value])=>`<dt>${esc(key)}</dt><dd>${esc(value)}</dd>`).join('')}</dl><h4>Visible relations</h4><div class="kg-relations">${relations.map((item)=>`<div class="kg-relation">${item.direction} <strong>${esc(item.label)}</strong><br><code>${esc(short(item.other))}</code></div>`).join('')||'<p>No visible relations in the selected layers.</p>'}</div>`;
  }
  function syncQuery(){const query=data?.queries.find((item)=>item.id===querySelect.value);if(!query)return;queryEditor.value=query.query;queryNote.textContent=query.purpose;currentRows=query.rows||[];renderTable(query.variables||[],currentRows);}
  function normalize(value){return String(value||'').replace(/\s+/g,' ').trim();}
  function runQuery(){const query=data?.queries.find((item)=>item.id===querySelect.value);if(!query)return;if(normalize(queryEditor.value)!==normalize(query.query)){queryNote.textContent='This query was edited. The static page executes only the release-tested snapshot; download the .rq file and use run_demo.py or the notebook to execute arbitrary SPARQL with RDFLib.';currentRows=[];renderTable([],[]);return;}currentRows=query.rows||[];queryNote.textContent=`Release-tested RDFLib result: ${currentRows.length} row${currentRows.length===1?'':'s'}.`;renderTable(query.variables||[],currentRows);}
  function renderTable(variables,rows){if(!rows.length){queryResults.innerHTML='<p class="kg-status">No browser result rows to display.</p>';return;}queryResults.innerHTML=`<table><thead><tr>${variables.map((item)=>`<th>${esc(item)}</th>`).join('')}</tr></thead><tbody>${rows.map((row)=>`<tr>${variables.map((item)=>`<td>${esc(row[item]??'')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;}
  function downloadRows(format){const query=data?.queries.find((item)=>item.id===querySelect.value);if(!query||!currentRows.length)return;if(format==='json'){download(`${query.id}.json`,JSON.stringify(currentRows,null,2),'application/json');return;}const variables=query.variables||Object.keys(currentRows[0]||{}),quote=(value)=>`"${String(value??'').replace(/"/g,'""')}"`;download(`${query.id}.csv`,[variables.map(quote).join(','),...currentRows.map((row)=>variables.map((key)=>quote(row[key])).join(','))].join('\n'),'text/csv');}
  function download(name,content,type){const blob=new Blob([content],{type}),url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function truncate(value,max){const text=String(value||'');return text.length>max?`${text.slice(0,max-1)}…`:text;}
  function el(name,attributes={}){const node=document.createElementNS('http://www.w3.org/2000/svg',name);Object.entries(attributes).forEach(([key,value])=>node.setAttribute(key,value));return node;}
})();
"""


def _relative(page_path: Path, target: Path) -> str:
    import os

    return Path(os.path.relpath(target, page_path.parent)).as_posix()

