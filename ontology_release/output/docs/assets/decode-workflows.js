
(() => {
  const root = document.getElementById('decode-root');
  if (!root || !window.cytoscape) return;
  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value || '').replace(/[&<>'"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const lower = (value) => String(value || '').toLowerCase();
  const graph = $('#decode-graph'), details = $('#decode-details'), hover = $('#decode-hovercard');
  const sourceToggle = $('#decode-show-source'), anchorToggle = $('#decode-show-anchors'), semanticToggle = $('#decode-show-semantic'), semanticFilter = $('#decode-semantic-filter'), more = $('#decode-more');
  let data, cy, selectedWorkflow, selectedAnchor, shownWorkflows = new Set(), viewMode = 'source';

  fetch(root.dataset.decodeData).then((response) => response.json()).then((loaded) => { data = loaded; initialize(); }).catch((error) => { details.innerHTML = `<h2>Workflow data unavailable</h2><p>${esc(error.message)}</p>`; });

  function index(items) { return Object.fromEntries((items || []).map((item) => [item.id, item])); }
  function initialize() {
    data.nodeById = index(data.nodes); data.projectionNodeById = index(data.projection_nodes || []); data.anchorById = index(data.anchors); data.workflowById = index(data.workflows); data.edgeRegistryBySource = Object.fromEntries((data.edge_registry || []).map((row) => [row.source_dependency_id, row]));
    data.semantic_overview ||= { nodes: [], source_edges: [], semantic_edges: [] };
    data.overviewNodeById = index(data.semantic_overview.nodes);
    data.nodesByWorkflow = {}; data.nodes.forEach((node) => (data.nodesByWorkflow[node.workflow_id] ||= []).push(node.id));
    const family = $('#decode-family');
    [...new Set(data.workflows.map((workflow) => workflow.method_family))].sort().forEach((name) => family.insertAdjacentHTML('beforeend', `<option value="${esc(name)}">${esc(name.replaceAll('_', ' '))}</option>`));
    $('#decode-search').addEventListener('input', renderCatalogue); family.addEventListener('change', renderCatalogue);
    [sourceToggle, anchorToggle, semanticToggle, semanticFilter].forEach((input) => input.addEventListener('change', renderGraph));
    document.querySelectorAll('input[name="decode-view"]').forEach((input) => input.addEventListener('change', () => { viewMode = input.value; syncViewControls(); renderGraph(); showWorkflowDetails(data.workflowById[selectedWorkflow]); }));
    $('#decode-reset').addEventListener('click', () => selectWorkflow(selectedWorkflow));
    more.addEventListener('click', () => addNextConnectedWorkflow(selectedAnchor));
    syncViewControls(); renderCatalogue(); selectWorkflow(data.workflows[0]?.id);
  }

  function syncViewControls() {
    document.querySelectorAll('input[name="decode-view"]').forEach((input) => { input.checked = input.value === viewMode; });
    $('#decode-anchor-control').hidden = viewMode !== 'source';
    $('#decode-source-label').textContent = viewMode === 'semantic' ? 'Aggregated source dependencies' : 'Source dependencies';
    updateLegend();
  }
  function updateLegend() {
    const legend = $('#decode-legend');
    if (viewMode === 'source') {
      legend.innerHTML = '<strong>Semantic role (node fill):</strong> <span class="legend-matter">matter</span><span class="legend-manufacturing">manufacturing</span><span class="legend-process">process</span><span class="legend-measurement">measurement</span><span class="legend-instrument">instrument</span><span class="legend-parameter">parameter</span><span class="legend-data">data</span><span class="legend-property">property</span><span class="legend-metadata">metadata</span><span class="legend-mixed">mixed / missing role</span><br><strong>Mapping status (border):</strong> <span class="legend-approved">H2KG</span><span class="legend-reviewed">reviewed DECODE</span><span class="legend-unresolved">unresolved</span><br><span class="legend-source">solid arrow</span> preserved source dependency <span class="legend-anchor">dashed link</span> occurrence-to-anchor mapping <span class="legend-semantic">colored arrow</span> approved H2KG semantic projection';
      return;
    }
    legend.innerHTML = '<strong>Semantic role:</strong> <span class="legend-matter">matter</span><span class="legend-manufacturing">manufacturing</span><span class="legend-process">process</span><span class="legend-measurement">measurement</span><span class="legend-instrument">instrument</span><span class="legend-parameter">parameter</span><span class="legend-data">data</span><span class="legend-property">property</span><span class="legend-metadata">metadata</span><span class="legend-mixed">mixed / missing role</span><br><strong>Mapping status:</strong> <span class="legend-approved">H2KG</span><span class="legend-reviewed">reviewed DECODE</span><span class="legend-unresolved">unresolved</span><br><span class="legend-source">solid arrow</span> provenance-preserving aggregate <span class="legend-semantic">colored arrow</span> approved H2KG semantic projection';
  }
  function renderCatalogue() {
    const needle = lower($('#decode-search').value), family = $('#decode-family').value;
    const matches = data.workflows.filter((workflow) => (!needle || [workflow.title, workflow.source_filename, workflow.method_family, workflow.mapping_status, workflow.iri].join(' ').toLowerCase().includes(needle)) && (!family || workflow.method_family === family));
    $('#decode-catalogue-status').textContent = `${matches.length} of ${data.workflows.length} workflows`;
    $('#decode-workflow-list').innerHTML = matches.map((workflow) => `<button class="decode-workflow-card ${workflow.id === selectedWorkflow ? 'active' : ''}" data-workflow="${esc(workflow.id)}"><strong>${esc(workflow.title)}</strong><small>${esc(workflow.method_family.replaceAll('_',' '))} | ${workflow.source_node_count} nodes, ${workflow.source_edge_count} edges</small><small>${workflow.mapped_anchor_count} reviewed mappings | ${workflow.cross_workflow_connection_count} cross-workflow links</small></button>`).join('');
    document.querySelectorAll('[data-workflow]').forEach((button) => button.addEventListener('click', () => selectWorkflow(button.dataset.workflow)));
  }
  function selectWorkflow(workflowId) {
    if (!data.workflowById[workflowId]) return;
    selectedWorkflow = workflowId; selectedAnchor = null; shownWorkflows = new Set([workflowId]); more.hidden = true;
    renderCatalogue(); renderGraph(); showWorkflowDetails(data.workflowById[workflowId]);
  }
  function visibleNodeIds() { return new Set([...shownWorkflows].flatMap((workflowId) => data.nodesByWorkflow[workflowId] || [])); }
  function overviewId(occurrenceId) { const node = data.nodeById[occurrenceId]; return node?.anchor_id || `unresolved::${occurrenceId}`; }
  function visibleAnchorIds(nodes) { return new Set([...nodes].map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); }
  function semanticRoleKey(node) {
    if (node.role_conflict) return 'mixed';
    return ({ Matter:'matter', Manufacturing:'manufacturing', Process:'process', Measurement:'measurement', Instrument:'instrument', Parameter:'parameter', Data:'data', Property:'property', Metadata:'metadata' })[node.semantic_role] || 'unknown';
  }
  function semanticRoleText(node) {
    return node.role_conflict ? `Mixed role: ${(node.semantic_roles || []).join(', ') || 'unresolved'}` : (node.semantic_role || 'Missing role');
  }
  function mappingLabel(state) { return ({ approved_h2kg:'H2KG', reviewed_decode:'reviewed DECODE', unresolved:'Unresolved' })[state] || state || 'Unresolved'; }
  function projectionVisible(edge) { return semanticFilter.value === 'all' || edge.projection_outcome === semanticFilter.value; }

  function sourceElements() {
    const nodes = visibleNodeIds(), anchors = visibleAnchorIds(nodes), output = [];
    [...nodes].forEach((id) => { const node = data.nodeById[id]; output.push({ group:'nodes', data:{ id, label:node.label, kind:'occurrence', state:node.mapping_state, visual:node.visual_category || 'other', role:semanticRoleKey(node), workflow:node.workflow_id } }); });
    const semantic = semanticToggle.checked ? data.semantic_edges.filter((edge) => shownWorkflows.has(edge.workflow_id) && projectionVisible(edge)) : [];
    const semanticAnchorIds = new Set(semantic.flatMap((edge) => [edge.source, edge.target]).filter((id) => data.anchorById[id]));
    const proxyIds = new Set(semantic.flatMap((edge) => [edge.source, edge.target]).filter((id) => data.projectionNodeById[id]));
    [...proxyIds].forEach((id) => { const node = data.projectionNodeById[id]; output.push({ group:'nodes', data:{ id, label:node.label, kind:'value-proxy', state:'derived', role:'data', workflow:node.workflow_id } }); });
    const anchorNodeIds = new Set([...anchors, ...semanticAnchorIds]);
    if (anchorToggle.checked || semanticAnchorIds.size) {
      [...anchorNodeIds].forEach((id) => { const anchor = data.anchorById[id]; if (anchor) output.push({ group:'nodes', data:{ id, label:anchor.label, kind:'source-anchor', state:anchor.state, role:semanticRoleKey(anchor), anchorId:id } }); });
      if (anchorToggle.checked) data.anchor_edges.filter((edge) => nodes.has(edge.source) && anchorNodeIds.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'anchor', label:'maps to' } }));
    }
    if (sourceToggle.checked) data.source_edges.filter((edge) => nodes.has(edge.source) && nodes.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'source', label:edge.label || 'source dependency', sourceDependencyId:edge.id, sourceEdgeIds:[edge.id] } }));
    const visible = new Set(output.filter((item) => item.group === 'nodes').map((item) => item.data.id));
    semantic.filter((edge) => visible.has(edge.source) && visible.has(edge.target)).forEach((edge) => output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'semantic', label:edge.label, sourceDependencyId:edge.source_dependency_id, sourceEdgeIds:[edge.source_dependency_id], projectionOutcome:edge.projection_outcome, projectionPattern:edge.projection_pattern } }));
    return output;
  }
  function semanticElements() {
    const visible = visibleNodeIds(), semanticIds = new Set([...visible].map(overviewId)), output = [];
    [...semanticIds].forEach((id) => { const node = data.overviewNodeById[id]; if (node) output.push({ group:'nodes', data:{ id, label:node.label, kind:node.kind, state:node.state, role:semanticRoleKey(node), occurrenceCount:node.occurrence_count, anchorId:data.anchorById[id] ? id : '' } }); });
    if (sourceToggle.checked) data.semantic_overview.source_edges.forEach((edge) => {
      const pairs = (edge.occurrence_pairs || []).filter((pair) => visible.has(pair.source_occurrence_id) && visible.has(pair.target_occurrence_id));
      if (pairs.length && semanticIds.has(edge.source) && semanticIds.has(edge.target)) output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'source', label:`source dependency (${pairs.length})`, sourceEdgeIds:pairs.map((pair) => pair.source_dependency_id), occurrenceCount:pairs.length } });
    });
    if (semanticToggle.checked) data.semantic_overview.semantic_edges.filter(projectionVisible).forEach((edge) => {
      const visibleCount = (edge.workflow_ids || []).filter((workflowId) => shownWorkflows.has(workflowId)).length;
      if (visibleCount && semanticIds.has(edge.source) && semanticIds.has(edge.target)) output.push({ group:'edges', data:{ id:edge.id, source:edge.source, target:edge.target, kind:'semantic', label:edge.label, sourceEdgeIds:edge.source_dependency_ids, occurrenceCount:visibleCount } });
    });
    return output;
  }
  function elements() { return viewMode === 'semantic' ? semanticElements() : sourceElements(); }

  function renderGraph() {
    if (cy) cy.destroy();
    cy = cytoscape({ container:graph, elements:elements(), style:[
      { selector:'node', style:{ 'label':'data(label)', 'font-size':10, 'text-wrap':'wrap', 'text-max-width':118, 'color':'#183139', 'text-valign':'center', 'text-halign':'center', 'border-width':2, 'background-color':'#a9bcc0', 'border-color':'#50676d', 'width':60, 'height':60 } },
      { selector:'node[kind = "occurrence"][role = "matter"]', style:{ 'background-color':'#0f6d7a', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "manufacturing"]', style:{ 'background-color':'#b45309', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "process"]', style:{ 'background-color':'#d49118', 'color':'#183139' } },
      { selector:'node[kind = "occurrence"][role = "measurement"]', style:{ 'background-color':'#376caa', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "instrument"]', style:{ 'background-color':'#5d6b76', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "parameter"]', style:{ 'background-color':'#5d66a6', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "data"]', style:{ 'background-color':'#64b4d5', 'color':'#183139' } },
      { selector:'node[kind = "occurrence"][role = "property"]', style:{ 'background-color':'#9d5549', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][role = "metadata"]', style:{ 'background-color':'#98a3aa', 'color':'#183139' } },
      { selector:'node[kind = "occurrence"][role = "mixed"], node[kind = "occurrence"][role = "unknown"]', style:{ 'background-color':'#adb8bd', 'color':'#183139' } },
      { selector:'node[kind = "value-proxy"]', style:{ 'shape':'diamond', 'background-color':'#64b4d5', 'border-color':'#087f71', 'border-width':3, 'color':'#183139', 'width':52, 'height':52, 'font-size':9 } },
      { selector:'node[kind = "source-anchor"], node[kind = "semantic-anchor"]', style:{ 'shape':'round-rectangle', 'width':124, 'height':50, 'font-weight':700 } },
      { selector:'node[kind = "source-anchor"][state = "approved_h2kg"]', style:{ 'background-color':'#0d7f83', 'border-color':'#07575a', 'color':'#fff' } },
      { selector:'node[kind = "source-anchor"][state = "reviewed_decode"]', style:{ 'background-color':'#bd8529', 'border-color':'#855c12', 'color':'#fff' } },
      { selector:'node[kind = "occurrence"][state = "approved_h2kg"]', style:{ 'border-color':'#006f73', 'border-width':4 } },
      { selector:'node[kind = "occurrence"][state = "reviewed_decode"]', style:{ 'border-color':'#9a650b', 'border-width':4 } },
      { selector:'node[kind = "occurrence"][state = "unresolved"]', style:{ 'border-color':'#a63030', 'border-style':'dashed', 'border-width':3 } },
      { selector:'node[kind = "semantic-anchor"][role = "matter"]', style:{ 'background-color':'#0f6d7a', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "manufacturing"]', style:{ 'background-color':'#b45309', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "process"]', style:{ 'background-color':'#d49118', 'color':'#183139' } },
      { selector:'node[kind = "semantic-anchor"][role = "measurement"]', style:{ 'background-color':'#376caa', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "instrument"]', style:{ 'background-color':'#5d6b76', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "parameter"]', style:{ 'background-color':'#5d66a6', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "data"]', style:{ 'background-color':'#64b4d5', 'color':'#183139' } },
      { selector:'node[kind = "semantic-anchor"][role = "property"]', style:{ 'background-color':'#9d5549', 'color':'#fff' } },
      { selector:'node[kind = "semantic-anchor"][role = "metadata"]', style:{ 'background-color':'#98a3aa', 'color':'#183139' } },
      { selector:'node[kind = "semantic-anchor"][role = "mixed"], node[kind = "semantic-anchor"][role = "unknown"], node[kind = "semantic-unresolved"]', style:{ 'background-color':'#adb8bd', 'color':'#183139' } },
      { selector:'node[kind = "semantic-anchor"][state = "approved_h2kg"]', style:{ 'border-color':'#006f73', 'border-width':4 } },
      { selector:'node[kind = "semantic-anchor"][state = "reviewed_decode"]', style:{ 'border-color':'#9a650b', 'border-width':4 } },
      { selector:'node[kind = "semantic-anchor"][role = "mixed"], node[kind = "semantic-anchor"][state = "unresolved"], node[kind = "semantic-unresolved"]', style:{ 'border-color':'#a63030', 'border-style':'dashed', 'border-width':3 } },
      { selector:'node.hovered, node.focused', style:{ 'border-color':'#f59e0b', 'border-width':5, 'z-index':999 } },
      { selector:'edge[kind = "source"]', style:{ 'width':2, 'line-color':'#596c72', 'target-arrow-color':'#596c72', 'target-arrow-shape':'triangle', 'curve-style':'bezier', 'label':'data(label)', 'font-size':9, 'text-background-color':'#fff', 'text-background-opacity':.9, 'text-background-padding':2 } },
      { selector:'edge[kind = "anchor"]', style:{ 'width':1.5, 'line-style':'dashed', 'line-color':'#bd8529', 'curve-style':'bezier' } },
      { selector:'edge[kind = "semantic"]', style:{ 'width':2.5, 'line-color':'#087f71', 'target-arrow-color':'#087f71', 'target-arrow-shape':'triangle', 'label':'data(label)', 'font-size':9, 'text-background-color':'#fff', 'text-background-opacity':.9, 'text-background-padding':2 } }
    ], layout:{ name:'cose', animate:false, padding:34, idealEdgeLength:105, nodeRepulsion:520000 } });
    cy.on('dbltap', 'node', (event) => { const item = event.target.data(); const anchorId = item.anchorId || (item.kind === 'source-anchor' ? item.id : data.nodeById[item.id]?.anchor_id); if (anchorId) expandAnchor(anchorId); else if (item.kind === 'semantic-unresolved') showSemanticNodeDetails(item.id); else if (item.kind === 'value-proxy') showProjectionNodeDetails(item.id); else showOccurrenceDetails(item.id); });
    cy.on('tap', 'node', (event) => { const item = event.target.data(); if (item.kind === 'semantic-anchor' || item.kind === 'semantic-unresolved') showSemanticNodeDetails(item.id); else if (item.kind === 'source-anchor') showAnchorDetails(item.id); else if (item.kind === 'value-proxy') showProjectionNodeDetails(item.id); else showOccurrenceDetails(item.id); });
    cy.on('tap', 'edge', (event) => showEdgeDetails(event.target.data()));
    cy.on('mouseover', 'node, edge', (event) => { event.target.addClass('hovered'); showHover(event.target, event.originalEvent); });
    cy.on('mousemove', 'node, edge', (event) => moveHover(event.originalEvent));
    cy.on('mouseout', 'node, edge', (event) => { event.target.removeClass('hovered'); hideHover(); });
  }

  function rankedConnectedWorkflows(anchorId) {
    const visibleAnchors = visibleAnchorIds(visibleNodeIds());
    const candidates = new Set((data.anchor_index[anchorId] || []).map((id) => data.nodeById[id]?.workflow_id).filter((id) => id && !shownWorkflows.has(id)));
    return [...candidates].sort((left, right) => { const leftAnchors = new Set((data.nodesByWorkflow[left] || []).map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); const rightAnchors = new Set((data.nodesByWorkflow[right] || []).map((id) => data.nodeById[id]?.anchor_id).filter(Boolean)); const leftScore = [...leftAnchors].filter((id) => visibleAnchors.has(id)).length, rightScore = [...rightAnchors].filter((id) => visibleAnchors.has(id)).length; return rightScore - leftScore || data.workflowById[left].title.localeCompare(data.workflowById[right].title); });
  }
  function expandAnchor(anchorId) { selectedAnchor = anchorId; const next = rankedConnectedWorkflows(anchorId)[0]; if (next) shownWorkflows.add(next); renderGraph(); showAnchorDetails(anchorId); updateMoreButton(); }
  function addNextConnectedWorkflow(anchorId) { if (anchorId) expandAnchor(anchorId); }
  function updateMoreButton() { const remaining = selectedAnchor ? rankedConnectedWorkflows(selectedAnchor).length : 0; more.hidden = !remaining; more.textContent = `Add next connected workflow (${remaining} remaining)`; }

  function downloads(workflow) { const standard = `<a href="../decode/workflows/${encodeURIComponent(workflow.id)}.json" download>Download normalized workflow JSON</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.jsonld" download>Download JSON-LD projection</a><a href="../decode/workflows/${encodeURIComponent(workflow.id)}.ttl" download>Download Turtle projection</a><a href="../decode/decode_mapping_matrix.csv" download>Download mapping matrix</a><a href="../decode/decode_edge_registry.csv" download>Download edge-alignment registry</a><a href="../decode/decode_duplicate_occurrence_audit.csv" download>Download duplicate-occurrence audit</a><a href="../decode/decode_validation_report.json" download>Download validation report</a>`; const extras = (workflow.downloads || []).map((item) => `<a href="${esc(item.href)}" download>${esc(item.label)}</a>`).join(''); return `<div class="decode-downloads">${standard}${extras}</div>`; }
  function showWorkflowDetails(workflow) { const semanticCount = new Set((data.nodesByWorkflow[workflow.id] || []).map(overviewId)).size; const sourceStatus = workflow.is_derived ? 'PDF-derived interface schema; the original GraphML workflows are unchanged.' : (viewMode === 'semantic' ? 'Select a canonical node to inspect its original GraphML occurrences and branch contexts.' : 'The complete preserved source workflow is visible. Double-click an occurrence or anchor to traverse reviewed cross-workflow connections.'); details.innerHTML = `<h2>${esc(workflow.title)}</h2><p><span class="decode-status ${esc(workflow.mapping_status)}">${esc(workflow.mapping_status)}</span> <span class="decode-status">${workflow.is_derived ? 'derived schema' : (viewMode === 'semantic' ? 'semantic overview' : 'source preserved')}</span></p><p><strong>Source:</strong> ${esc(workflow.source_filename)}<br><strong>Method family:</strong> ${esc(workflow.method_family)}<br><strong>Topology:</strong> ${workflow.source_node_count} occurrences and ${workflow.source_edge_count} directed dependencies.<br><strong>Semantic overview:</strong> ${semanticCount} canonical nodes.</p><p>${sourceStatus}</p>${downloads(workflow)}`; }
  function showOccurrenceDetails(id) { const node = data.nodeById[id]; if (!node) return; const workflow = data.workflowById[node.workflow_id], anchor = data.anchorById[node.anchor_id]; const anchorText = anchor ? `<p><strong>Shared anchor:</strong> ${anchor.state === 'approved_h2kg' ? `<a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.id)}">${esc(anchor.label)}</a>` : esc(anchor.label)}</p>` : '<p><strong>Shared anchor:</strong> unresolved; no cross-workflow join is available.</p>'; const role = node.canonical_role_iri ? `<p><strong>H2KG role:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.canonical_role_iri)}">${esc(node.semantic_role || node.canonical_role_iri)}</a></p>` : ''; details.innerHTML = `<h2>${esc(node.label)}</h2><p><span class="decode-status ${esc(node.mapping_state)}">${esc(node.mapping_state)}</span></p><p><strong>Decision:</strong> ${esc(node.decision || 'unresolved')}<br><strong>Original GraphML ID:</strong> <code>${esc(node.source_id)}</code><br><strong>Workflow:</strong> ${esc(workflow.title)}<br><strong>Native category:</strong> ${esc(node.native_category || 'not supplied')}</p><p><strong>Source metadata:</strong> ${esc(node.description || 'not supplied')}</p>${anchorText}${role}<p><strong>Mapping evidence:</strong> ${esc(node.mapping_evidence || 'not supplied')}</p>${downloads(workflow)}`; if (cy) { const selected = cy.$id(id); selected.addClass('focused'); cy.center(selected); } }
  function showProjectionNodeDetails(id) { const node = data.projectionNodeById[id]; if (!node) return; const workflow = data.workflowById[node.workflow_id], source = data.nodeById[node.source_occurrence_id]; details.innerHTML = `<h2>${esc(node.label)}</h2><p><span class="decode-status">derived semantic projection</span></p><p><strong>H2KG type:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.canonical_role_iri)}">DataPoint</a><br><strong>Source occurrence:</strong> <code>${esc(source.source_id)}</code> ${esc(source.label)}<br><strong>Workflow:</strong> ${esc(workflow.title)}</p><p>${esc(node.description)}</p>`; }
  function showSemanticNodeDetails(id) { const node = data.overviewNodeById[id]; if (!node) return; const visible = visibleNodeIds(), occurrences = node.occurrence_ids.filter((occurrenceId) => visible.has(occurrenceId)); const anchor = data.anchorById[id]; const h2kg = anchor?.state === 'approved_h2kg' ? `<p><a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(id)}">Inspect this stable H2KG term in H2KG Explore</a></p>` : ''; const role = node.canonical_role_iri && !node.role_conflict ? `<p><strong>Semantic role:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(node.canonical_role_iri)}">${esc(semanticRoleText(node))}</a></p>` : `<p><strong>Semantic role:</strong> ${esc(semanticRoleText(node))}</p>`; const list = occurrences.map((occurrenceId) => { const occurrence = data.nodeById[occurrenceId], workflow = data.workflowById[occurrence.workflow_id]; return `<li><button class="decode-add-workflow" data-inspect-occurrence="${esc(occurrenceId)}"><code>${esc(occurrence.source_id)}</code> in ${esc(workflow.title)}</button></li>`; }).join(''); details.innerHTML = `<h2>${esc(node.label)}</h2><p><span class="decode-status ${esc(node.state)}">${esc(mappingLabel(node.state))}</span> ${esc(node.decision || '')}</p>${role}<p><strong>Semantic overview:</strong> ${occurrences.length} visible source occurrence${occurrences.length === 1 ? '' : 's'} represented by one canonical node.</p><p>${esc(node.evidence || '')}</p>${h2kg}<h3>Inspect preserved source occurrences</h3><ul>${list || '<li>No occurrence is visible.</li>'}</ul>${anchor ? `<p>Double-click this node to add one complete connected workflow through the shared anchor.</p>` : ''}`; document.querySelectorAll('[data-inspect-occurrence]').forEach((button) => button.addEventListener('click', () => { viewMode = 'source'; syncViewControls(); renderGraph(); showOccurrenceDetails(button.dataset.inspectOccurrence); })); }
  function showAnchorDetails(anchorId) { const anchor = data.anchorById[anchorId]; if (!anchor) return; const workflows = [...new Set((data.anchor_index[anchorId] || []).map((id) => data.nodeById[id]?.workflow_id).filter(Boolean))].map((id) => data.workflowById[id]); const candidates = rankedConnectedWorkflows(anchorId); const h2kg = anchor.state === 'approved_h2kg' ? `<p><a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.id)}">Inspect this stable H2KG term in H2KG Explore</a></p>` : ''; const role = anchor.canonical_role_iri && anchor.state !== 'approved_h2kg' ? `<p><strong>H2KG role:</strong> <a href="${root.dataset.h2kgExplore}?iri=${encodeURIComponent(anchor.canonical_role_iri)}">${esc(anchor.semantic_role || anchor.canonical_role_iri)}</a></p>` : ''; const cards = candidates.slice(0,8).map((workflow) => `<button class="decode-add-workflow" data-add-workflow="${esc(workflow.id)}">Add full workflow: ${esc(workflow.title)}</button>`).join(''); details.innerHTML = `<h2>${esc(anchor.label)}</h2><p><span class="decode-status ${esc(anchor.state)}">${esc(mappingLabel(anchor.state))}</span> ${esc(anchor.decision || '')}</p><p><code>${esc(anchor.id)}</code></p><p>${esc(anchor.evidence)}</p>${h2kg}${role}<h3>Linked workflows (${workflows.length})</h3><ul>${workflows.map((workflow) => `<li>${esc(workflow.title)}</li>`).join('')}</ul>${cards ? `<h3>Expand a connected workflow</h3>${cards}` : '<p>All linked workflows are visible.</p>'}`; document.querySelectorAll('[data-add-workflow]').forEach((button) => button.addEventListener('click', () => { shownWorkflows.add(button.dataset.addWorkflow); renderGraph(); showAnchorDetails(anchorId); updateMoreButton(); })); }
  function visibleRelations(id) { return [...cy.$id(id).connectedEdges()].map((edge) => `${edge.data('kind')}: ${edge.data('label') || 'relation'}`).join('; ') || 'none'; }
  function edgeDecision(item) { return data.edgeRegistryBySource[item.sourceDependencyId || item.id]; }
  function edgeDecisionHtml(item) { const decision = edgeDecision(item); if (!decision) return ''; return `<p><strong>Classification:</strong> ${esc(decision.projection_outcome)}<br><strong>Pattern:</strong> ${esc(decision.projection_pattern)}<br><strong>Semantic direction:</strong> ${esc(decision.semantic_direction)}<br><strong>Predicate(s):</strong> ${esc(decision.semantic_predicates || 'none')}<br><strong>Confidence:</strong> ${esc(decision.confidence)}<br><strong>Rationale:</strong> ${esc(decision.rationale)}</p>`; }
  function showEdgeDetails(item) { details.innerHTML = `<h2>${esc(item.label || 'Source dependency')}</h2><p><strong>Relation layer:</strong> ${esc(item.kind)}<br><strong>Preserved direction:</strong> <code>${esc(item.source)}</code> -> <code>${esc(item.target)}</code><br><strong>Source dependency ID:</strong> <code>${esc(item.sourceDependencyId || item.id)}</code></p>${edgeDecisionHtml(item)}`; }
  function showHover(element, event) { const item = element.data(); if (element.isEdge()) { const count = item.occurrenceCount ? `<p><strong>Preserved source dependencies:</strong> ${item.occurrenceCount}</p>` : ''; hover.innerHTML = `<h3>${esc(item.label || item.kind)}</h3><p><strong>Relation layer:</strong> ${esc(item.kind)}</p><p><code>${esc(item.source)}</code> -> <code>${esc(item.target)}</code></p>${edgeDecisionHtml(item)}${count}`; } else if (item.kind === 'semantic-anchor' || item.kind === 'semantic-unresolved') { const node = data.overviewNodeById[item.id]; hover.innerHTML = `<h3>${esc(node.label)}</h3><p><span class="decode-status ${esc(node.state)}">${esc(mappingLabel(node.state))}</span></p><p><strong>Semantic role:</strong> ${esc(semanticRoleText(node))}</p><p>${node.occurrence_count} preserved occurrence${node.occurrence_count === 1 ? '' : 's'} represented here. Double-click to expand connected workflows when an anchor is available.</p>`; } else if (item.kind === 'source-anchor') { const anchor = data.anchorById[item.id], workflows = [...new Set((data.anchor_index[item.id] || []).map((id) => data.nodeById[id]?.workflow_id).filter(Boolean))]; hover.innerHTML = `<h3>${esc(anchor.label)}</h3><p><span class="decode-status ${esc(anchor.state)}">${esc(mappingLabel(anchor.state))}</span></p><p><strong>Semantic role:</strong> ${esc(anchor.semantic_role || 'Missing role')}</p><p>${workflows.length} linked workflows. Double-click to add the next complete workflow.</p>`; } else if (item.kind === 'value-proxy') { const node = data.projectionNodeById[item.id]; hover.innerHTML = `<h3>${esc(node.label)}</h3><p><strong>Derived semantic node:</strong> H2KG DataPoint proxy</p><p>${esc(node.description)}</p>`; } else { const node = data.nodeById[item.id]; hover.innerHTML = `<h3>${esc(node.label)}</h3><p><span class="decode-status ${esc(node.mapping_state)}">${esc(mappingLabel(node.mapping_state))}</span> ${esc(node.visual_category || 'other')}</p><p><strong>Semantic role:</strong> ${esc(node.semantic_role || 'Missing role')}</p><p><strong>GraphML ID:</strong> <code>${esc(node.source_id)}</code><br><strong>Workflow:</strong> ${esc(data.workflowById[node.workflow_id].title)}<br><strong>Native category:</strong> ${esc(node.native_category || 'not supplied')}</p><p><strong>Visible relations:</strong> ${esc(visibleRelations(node.id))}</p>`; } hover.classList.remove('is-hidden'); moveHover(event); }
  function moveHover(event) { if (!event || hover.classList.contains('is-hidden')) return; hover.style.left = `${Math.min((event.clientX || 0) + 14, window.innerWidth - hover.offsetWidth - 10)}px`; hover.style.top = `${Math.min((event.clientY || 0) + 14, window.innerHeight - hover.offsetHeight - 10)}px`; }
  function hideHover() { hover.classList.add('is-hidden'); }
})();
