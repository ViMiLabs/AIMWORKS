
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
