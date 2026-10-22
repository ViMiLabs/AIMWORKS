
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
