
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
    const rows=data.requirements.map((item)=>({id:item.id,question:item.question,assessment:item.assessment_type,expected:item.expected_rows.length,h2kg:item.ontologies.h2kg.status,chameo:item.ontologies.chameo.status}));
    $('cb-requirement-matrix').innerHTML=`<table><thead><tr><th>ID</th><th>Assessment</th><th>Plain-language requirement</th><th>Expected rows</th><th>H₂KG</th><th>CHAMEO</th></tr></thead><tbody>${rows.map((row)=>`<tr><td>${esc(row.id.slice(0,3).toUpperCase())}</td><td>${esc(row.assessment.replaceAll('_',' '))}</td><td>${esc(row.question)}</td><td>${row.expected}</td><td>${statusPill(row.h2kg)}</td><td>${statusPill(row.chameo)}</td></tr>`).join('')}</tbody></table>`;
  }
  async function syncRequirement(){
    current=data.requirements.find((item)=>item.id===reqSelect.value);
    currentModel=current?.ontologies[ontologySelect.value];
    if(!current||!currentModel)return;
    filter.value='';
    $('cb-question').textContent=current.question;
    $('cb-source-basis').textContent=`Assessment: ${current.assessment_type.replaceAll('_',' ')}. Evidence basis: ${current.source_basis}`;
    $('cb-query-title').textContent=`${ontologySelect.value==='h2kg'?'H₂KG':'CHAMEO'} query or assessment note`;
    $('cb-query').value=currentModel.query;
    $('cb-rationale').textContent=currentModel.rationale;
    const c=currentModel.comparison;
    const evidenceCards=currentModel.query_executed
      ? `<div>Matched<strong>${c.matched_row_count}/${c.expected_row_count}</strong></div><div>Additional<strong>${c.unexpected_row_count}</strong></div>`
      : `<div>Assessment<strong>${esc(currentModel.assessment_mode.replaceAll('_',' '))}</strong></div><div>SPARQL executed<strong>No</strong></div>`;
    $('cb-outcome').innerHTML=`<div>Status<strong>${statusPill(currentModel.status)}</strong></div><div>Representation<strong>${esc(currentModel.representation_tier.replaceAll('_',' '))}</strong></div>${evidenceCards}`;
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
    keys.forEach((key)=>{const row=observed.get(key)||expected.get(key);const option=document.createElement('option');option.value=key;const state=currentModel.query_executed?(observed.has(key)?(expected.has(key)?'Matched':'Additional'):'Missing'):'Assessment target';option.textContent=`${state} · ${rowSummary(row)}`;rowSelect.append(option);});
    if(keys.length)rowSelect.value=keys[0];
  }
  function renderTables(){
    if(!current||!currentModel)return;
    const term=filter.value.trim().toLowerCase();
    const keep=(row)=>!term||JSON.stringify(row).toLowerCase().includes(term);
    renderTable($('cb-observed'),current.variables,currentModel.rows.filter(keep),currentModel.query_executed?'No observed rows.':'No SPARQL query was executed; consult the native assessment rationale.',true);
    renderTable($('cb-expected'),current.variables,current.expected_rows.filter(keep),'No expected rows.',true);
  }
  function renderTable(container,variables,rows,empty,clickable){
    if(!rows.length){container.innerHTML=`<p class="cb-empty">${esc(empty)}</p>`;return;}
    container.innerHTML=`<table><thead><tr>${clickable?'<th>Evidence</th>':''}${variables.map((key)=>`<th>${esc(key)}</th>`).join('')}</tr></thead><tbody>${rows.map((row)=>{const key=signature(row);return `<tr data-row-key="${esc(key)}">${clickable?'<td><button type="button" class="cb-view-row">View graph</button></td>':''}${variables.map((name)=>`<td>${esc(row[name]??'')}</td>`).join('')}</tr>`;}).join('')}</tbody></table>`;
    container.querySelectorAll('tr[data-row-key]').forEach((tr)=>tr.addEventListener('click',()=>{if([...rowSelect.options].some((option)=>option.value===tr.dataset.rowKey)){rowSelect.value=tr.dataset.rowKey;renderEvidence();document.querySelector('.cb-evidence').scrollIntoView({behavior:'smooth',block:'start'});}}));
  }
  function renderDifferences(){
    const c=currentModel.comparison;
    $('cb-difference-summary').innerHTML=currentModel.query_executed
      ? `<div class="cb-difference-cards"><div>Expected<strong>${c.expected_row_count}</strong></div><div>Observed<strong>${c.observed_row_count}</strong></div><div>Missing<strong>${c.missing_expected_row_count}</strong></div><div>Additional<strong>${c.unexpected_row_count}</strong></div></div>`
      : `<div class="cb-difference-cards"><div>Target population<strong>${c.expected_row_count}</strong></div><div>Assessment<strong>${esc(currentModel.assessment_mode.replaceAll('_',' '))}</strong></div><div>SPARQL executed<strong>No</strong></div><div>Status<strong>${esc(currentModel.status.replaceAll('_',' '))}</strong></div></div>`;
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
