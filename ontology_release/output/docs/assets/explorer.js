
document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-explorer-root]");
  if (!root) return;

  const dataPath = root.dataset.explorerData;
  const alignmentEvidencePath = root.dataset.alignmentEvidence;
  const referencePage = root.dataset.referencePage || "../hydrogen-ontology.html";
  const searchInputEl = root.querySelector("[data-explorer-search]");
  const searchStatusEl = root.querySelector("[data-explorer-search-status]");
  const resultsEl = root.querySelector("[data-explorer-results]");
  const trailEl = root.querySelector("[data-explorer-trail]");
  const graphNoteEl = root.querySelector("[data-explorer-graph-note]");
  const inspectorEl = root.querySelector("[data-explorer-inspector]");
  const relationsEl = root.querySelector("[data-explorer-relations]");
  const breadcrumbEl = root.querySelector("[data-explorer-breadcrumb]");
  const branchEl = root.querySelector("[data-explorer-branch]");
  const chartEl = root.querySelector("[data-explorer-chart]");
  const downloadRelationsEl = root.querySelector("[data-explorer-download-relations]");
  const countNodesEl = root.querySelector('[data-explorer-count="nodes"]');
  const countEdgesEl = root.querySelector('[data-explorer-count="edges"]');
  const countExpandedEl = root.querySelector('[data-explorer-count="expanded"]');
  const undoButtonEl = root.querySelector('[data-explorer-action="undo"]');
  const layerMenuEl = root.querySelector(".explorer-layer-menu");
  const layerCountEl = root.querySelector("[data-explorer-layer-count]");

  const STARTER_LABELS = [
    "measurement",
    "property",
    "parameter",
    "matter",
    "instrument",
    "manufacturing",
    "process",
    "data",
    "metadata"
  ];
  const MAX_SUGGESTIONS = 14;

  let payload = null;
  let alignmentEvidencePayload = null;
  let alignmentEvidencePromise = null;
  let cy = null;
  let currentSuggestions = [];

  const state = {
    selectedId: null,
      seedId: null,
      expandedIds: new Set(),
      trail: [],
      history: [],
      highlightedIndex: 0,
      currentGraph: null,
      currentRelations: [],
      hoverCardEl: null,
      viewMode: "taxonomy"
    };

  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
  const normalize = (value) => String(value || "").trim().toLowerCase();
  const stripKey = (value) => normalize(value).replace(/[^a-z0-9]+/g, "");
  const activeModules = () => Array.from(root.querySelectorAll("[data-explorer-module]:checked")).map((input) => input.value);
  const activeView = () => root.querySelector("[data-explorer-view]:checked")?.value || "taxonomy";
  const activeBranch = () => branchEl?.value || "";
  const toggleEnabled = (name) => Boolean(root.querySelector(`[data-explorer-toggle="${name}"]`)?.checked);
    const branchColor = (branch) => ({
      Matter: "#4aa99b",
      Process: "#d88738",
      InformationEntity: "#8a72bd",
      Characteristic: "#4f9fb4",
      Agent: "#7f8b92",
      Compatibility: "#a6aaad"
    }[branch] || "#9aa4a9");
    const branchShape = (branch) => ({
      Matter: "ellipse",
      Process: "round-rectangle",
      InformationEntity: "diamond",
      Characteristic: "hexagon",
      Agent: "rectangle"
    }[branch] || "ellipse");
    const nodeQname = (node) => String(node.qname || node.localName || node.iri || "");
    const nodeAnchorHref = (node) => `${referencePage}#${encodeURIComponent(node.anchor || node.localName || "")}`;
    const slugify = (value) => stripKey(value).slice(0, 64) || "selection";

    function levenshtein(left, right) {
    if (left === right) return 0;
    if (!left.length) return right.length;
    if (!right.length) return left.length;
    const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
    for (let i = 1; i <= left.length; i += 1) {
      let diagonal = previous[0];
      previous[0] = i;
      for (let j = 1; j <= right.length; j += 1) {
        const stored = previous[j];
        const cost = left[i - 1] === right[j - 1] ? 0 : 1;
        previous[j] = Math.min(previous[j] + 1, previous[j - 1] + 1, diagonal + cost);
        diagonal = stored;
      }
    }
    return previous[right.length];
  }

  function fuzzyBonus(query, candidate) {
    const q = stripKey(query);
    const c = stripKey(candidate);
    if (!q || !c || Math.abs(q.length - c.length) > 3) return 0;
    const distance = levenshtein(q, c);
    if (distance === 0) return 28;
    if (distance === 1) return 16;
    if (distance === 2) return 8;
    return 0;
  }

  function isSearchableNode(node) {
    const localName = String(node.localName || "");
    if (node.category === "Ontology" || localName.startsWith("_") || /_QV$/i.test(localName)) return false;
    return true;
  }

  function searchCandidates() {
    const allowExternal = toggleEnabled("includeExternalSearch");
    const viewMode = activeView();
    const branch = activeBranch();
    return (payload?.nodes || []).filter((node) => {
      if (!isSearchableNode(node)) return false;
      if (!allowExternal && !node.local) return false;
      if (viewMode === "taxonomy" && !(node.modules || []).includes("taxonomy")) return false;
      if (branch && node.taxonomy_top_branch !== branch) return false;
      return true;
    });
  }

  function starterSuggestions(view) {
    const candidates = view.nodes.filter((node) => isSearchableNode(node) && node.local);
    const starters = [];
    const seen = new Set();
    STARTER_LABELS.forEach((target) => {
      const match = candidates.find((node) => {
        const label = normalize(node.label);
        const localName = normalize(node.localName);
        return label === target || localName === target;
      });
      if (match && !seen.has(match.id)) {
        starters.push(match);
        seen.add(match.id);
      }
    });
    return starters.length
      ? starters
      : candidates.sort((left, right) => (Number(right.degree || 0) - Number(left.degree || 0)) || left.label.localeCompare(right.label)).slice(0, MAX_SUGGESTIONS);
  }

  function scoreNode(node, query) {
    const q = normalize(query);
    if (!q) return 0;
    const label = normalize(node.label);
    const localName = normalize(node.localName || "");
    const qname = normalize(nodeQname(node));
    const iri = normalize(node.iri || "");
    const details = normalize(node.search_text || node.description || "");
    const altLabels = normalize((node.alt_labels || []).join(" "));
    const notations = normalize((node.notations || []).join(" "));
    const examples = normalize((node.examples || []).join(" "));
    const notes = normalize((node.notes || []).join(" "));
    const displayClass = normalize(node.display_class || "");
    const mappingText = normalize((node.mapping_labels || []).join(" "));
    let score = 0;

    if (label === q || localName === q || qname === q) score += 180;
    if (label.startsWith(q) || localName.startsWith(q) || qname.startsWith(q)) score += 95;
    if (label.includes(q) || localName.includes(q) || qname.includes(q)) score += 70;
    if (details.includes(q)) score += 28;
    if (altLabels.includes(q)) score += 20;
    if (notations === q) score += 120;
    if (notations.includes(q)) score += 55;
    if (displayClass.includes(q)) score += 18;
    if (examples.includes(q) || notes.includes(q)) score += 12;
    if (iri.includes(q)) score += 12;
    if (mappingText.includes(q)) score += 9;
    if (node.local) score += 18;
    if ((node.modules || []).includes("vocabulary")) score += 12;
    if ((node.modules || []).includes("schema")) score += 8;
    score += Math.max(
      fuzzyBonus(q, label),
      fuzzyBonus(q, localName),
      fuzzyBonus(q, qname),
      fuzzyBonus(q, displayClass),
      0
    );
    score += Math.min(Number(node.degree || 0), 60) / 25;
    return score;
  }

  function searchResults(query) {
    const q = normalize(query);
    if (!q) return [];
    return searchCandidates()
      .map((node) => ({ node, score: scoreNode(node, q) }))
      .filter((row) => row.score > 0)
      .sort((left, right) => {
        if (right.score !== left.score) return right.score - left.score;
        if (left.node.local !== right.node.local) return left.node.local ? -1 : 1;
        return left.node.label.localeCompare(right.node.label);
      })
      .slice(0, MAX_SUGGESTIONS)
      .map((row) => row.node);
  }

  function updateTrail(nodeId) {
    if (!nodeId) return;
    state.trail = state.trail.filter((value) => value !== nodeId);
    state.trail.push(nodeId);
    if (state.trail.length > 10) {
      state.trail = state.trail.slice(state.trail.length - 10);
    }
  }

  function captureSnapshot() {
    return {
      selectedId: state.selectedId,
      seedId: state.seedId,
      expandedIds: Array.from(state.expandedIds),
      trail: state.trail.slice(),
      highlightedIndex: state.highlightedIndex,
      searchValue: searchInputEl.value,
      activeModules: activeModules(),
      viewMode: activeView(),
      branch: activeBranch(),
      toggles: Object.fromEntries(Array.from(root.querySelectorAll("[data-explorer-toggle]")).map((input) => [input.dataset.explorerToggle, input.checked]))
    };
  }

  function pushHistorySnapshot() {
    state.history.push(captureSnapshot());
    if (state.history.length > 30) {
      state.history = state.history.slice(state.history.length - 30);
    }
  }

  function applySnapshot(snapshot) {
    if (!snapshot) return;
    searchInputEl.value = snapshot.searchValue || "";
    const selectedModules = new Set(snapshot.activeModules || []);
    root.querySelectorAll("[data-explorer-module]").forEach((input) => {
      input.checked = selectedModules.has(input.value);
    });
    root.querySelectorAll("[data-explorer-toggle]").forEach((input) => {
      input.checked = Boolean(snapshot.toggles?.[input.dataset.explorerToggle]);
    });
    const viewInput = root.querySelector(`[data-explorer-view][value="${snapshot.viewMode || "taxonomy"}"]`);
    if (viewInput) viewInput.checked = true;
    if (branchEl) branchEl.value = snapshot.branch || "";
    state.selectedId = snapshot.selectedId || null;
    state.seedId = snapshot.seedId || null;
    state.expandedIds = new Set(snapshot.expandedIds || []);
    state.trail = Array.isArray(snapshot.trail) ? snapshot.trail.slice(-10) : [];
    state.highlightedIndex = Number.isInteger(snapshot.highlightedIndex) ? snapshot.highlightedIndex : 0;
  }

  function runUndoable(action) {
    pushHistorySnapshot();
    action();
    renderAll();
  }

  function undoLastStep() {
    if (!state.history.length) return;
    applySnapshot(state.history.pop());
    renderAll();
  }

  function selectNode(nodeId, options = {}) {
    if (!nodeId) return;
    const reset = options.reset !== false;
    state.selectedId = nodeId;
    state.seedId = state.seedId || nodeId;
    if (reset) {
      state.expandedIds = new Set([nodeId]);
    } else {
      state.expandedIds.add(nodeId);
    }
    updateTrail(nodeId);
  }

  function buildBaseView() {
    const selectedModules = new Set(activeModules());
    const viewMode = activeView();
    const branch = activeBranch();
    state.viewMode = viewMode;
    const nodes = (payload.nodes || []).filter((node) => {
      if (!(node.modules || []).some((moduleId) => selectedModules.has(moduleId))) return false;
      if (viewMode === "taxonomy" && !(node.modules || []).includes("taxonomy")) return false;
      if (branch && node.taxonomy_top_branch !== branch) return false;
      return true;
    });
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links = (payload.links || []).filter((link) => {
      if (!selectedModules.has(link.module) || !nodeMap.has(link.source) || !nodeMap.has(link.target)) return false;
      const isTaxonomy = link.module === "taxonomy" || link.edgeFamily === "taxonomy" || link.predicate === "subclassOf";
      if (viewMode === "taxonomy") return isTaxonomy;
      if (viewMode === "relations") return link.module === "profiles" || link.edgeFamily === "workflow_usage";
      return true;
    });
    const adjacency = new Map();
    links.forEach((link) => {
      if (!adjacency.has(link.source)) adjacency.set(link.source, []);
      if (!adjacency.has(link.target)) adjacency.set(link.target, []);
      adjacency.get(link.source).push(link);
      adjacency.get(link.target).push(link);
    });
    return { nodes, nodeMap, links, adjacency, viewMode, branch };
  }

  function buildExpandedGraph(view) {
    const center = view.nodeMap.get(state.selectedId);
    if (!center) {
      return { center: null, nodes: [], links: [], nodeMap: new Map(), meta: { expandedCount: 0 } };
    }
    const expanded = new Set(Array.from(state.expandedIds).filter((id) => view.nodeMap.has(id)));
    expanded.add(center.id);
    const visibleIds = new Set([center.id]);
    const visibleLinks = new Map();
    Array.from(expanded).forEach((sourceId) => {
      (view.adjacency.get(sourceId) || []).forEach((link) => {
        const neighborId = link.source === sourceId ? link.target : link.source;
        const neighbor = view.nodeMap.get(neighborId);
        if (!neighbor) return;
        if (!toggleEnabled("showExternalNeighbors") && !neighbor.local && neighbor.id !== center.id) return;
        visibleIds.add(link.source);
        visibleIds.add(link.target);
        visibleLinks.set(`${link.source}|${link.target}|${link.predicate}|${link.module}`, link);
      });
    });
    const nodes = Array.from(visibleIds)
      .map((id) => view.nodeMap.get(id))
      .filter(Boolean)
      .sort((left, right) => {
        if (left.id === center.id) return -1;
        if (right.id === center.id) return 1;
        if (left.local !== right.local) return left.local ? -1 : 1;
        return left.label.localeCompare(right.label);
      });
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links = Array.from(visibleLinks.values()).filter((link) => nodeMap.has(link.source) && nodeMap.has(link.target));
    return { center, nodes, links, nodeMap, meta: { expandedCount: expanded.size } };
  }

  function ensureCy() {
    if (cy) return cy;
    cy = cytoscape({
      container: chartEl,
      elements: [],
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele) => branchColor(ele.data("topBranch")),
            "shape": (ele) => branchShape(ele.data("topBranch")),
            "label": "data(label)",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": 120,
            "color": "#132129",
            "text-valign": "bottom",
            "text-margin-y": 8,
            "width": (ele) => ele.data("isCenter") ? 38 : 28,
            "height": (ele) => ele.data("isCenter") ? 38 : 28,
            "border-width": (ele) => ele.data("isCenter") ? 4 : ele.data("isDeprecated") ? 2.5 : 1.4,
            "border-style": (ele) => ele.data("isDeprecated") ? "dashed" : "solid",
            "border-color": (ele) => ele.data("isCenter") ? "#c86a2b" : "rgba(19,33,41,0.28)"
          }
        },
        {
          selector: "edge",
          style: {
            "line-color": (ele) => ele.data("isTaxonomy") ? "rgba(15,109,122,0.56)" : "rgba(19,33,41,0.24)",
            "target-arrow-color": (ele) => ele.data("isTaxonomy") ? "rgba(15,109,122,0.56)" : "rgba(19,33,41,0.24)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "arrow-scale": 0.9,
            "width": 1.6,
            "label": "data(label)",
            "font-size": 9,
            "color": "rgba(19,33,41,0.74)",
            "text-background-color": "rgba(255,255,255,0.92)",
            "text-background-opacity": 1,
            "text-background-padding": 2,
            "text-rotation": "autorotate"
          }
        },
        {
          selector: ":selected",
          style: {
            "overlay-color": "#0f6d7a",
            "overlay-opacity": 0.08
          }
        }
      ]
    });
    cy.on("tap", "node", (event) => {
      runUndoable(() => {
        state.seedId = state.seedId || event.target.id();
        selectNode(event.target.id(), { reset: false });
      });
    });
    cy.on("mouseover", "node", (event) => {
      showHoverCardForNode(event.target.id(), event);
    });
    cy.on("mouseover", "edge", (event) => {
      showHoverCardForEdge(event.target.id(), event);
    });
    cy.on("mousemove", "node, edge", (event) => {
      positionHoverCard(event);
    });
    cy.on("mouseout", "node, edge", () => {
      hideHoverCard();
    });
    cy.on("tap", (event) => {
      if (event.target === cy) hideHoverCard();
    });
    return cy;
  }

  function runLayout(graph) {
    const instance = ensureCy();
    if (!graph.nodes.length) return;
    const dense = graph.nodes.length > 28 || graph.links.length > 34;
    instance.layout(
      state.viewMode === "taxonomy"
        ? { name: "breadthfirst", directed: true, animate: false, fit: true, padding: 50, spacingFactor: 1.35 }
        : dense
        ? { name: "circle", animate: false, fit: true, padding: 55 }
        : {
            name: "cose",
            animate: false,
            fit: true,
            padding: 34,
            nodeRepulsion: 320000,
            idealEdgeLength: 120,
            edgeElasticity: 110,
            gravity: 0.24,
            numIter: 850,
            coolingFactor: 0.95
          }
    ).run();
    const centerNode = instance.getElementById(graph.center.id);
    if (centerNode && centerNode.nonempty()) {
      instance.center(centerNode);
    }
  }

  function buildCyElements(graph) {
    const nodes = graph.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        isLocal: node.local,
        isCenter: node.id === graph.center?.id,
        isDeprecated: node.deprecated === "Deprecated",
        topBranch: node.taxonomy_top_branch || "",
        semanticRole: node.taxonomy_role || node.display_class || "",
        viewMode: state.viewMode,
        iri: node.iri
      }
    }));
    const edges = graph.links.map((link) => ({
      data: {
        id: `${link.source}|${link.target}|${link.predicate}|${link.module}`,
        source: link.source,
        target: link.target,
        label: String(link.value || link.predicate || ""),
        isTaxonomy: link.module === "taxonomy" || link.edgeFamily === "taxonomy" || link.predicate === "subclassOf"
      }
    }));
    return [...nodes, ...edges];
  }

  function ensureHoverCard() {
    if (state.hoverCardEl) return state.hoverCardEl;
    const container = chartEl.parentElement;
    if (!container) return null;
    const card = document.createElement("div");
    card.className = "explorer-hovercard is-hidden";
    card.setAttribute("aria-hidden", "true");
    container.appendChild(card);
    state.hoverCardEl = card;
    return card;
  }

  function positionHoverCard(event) {
    const card = ensureHoverCard();
    if (!card || card.classList.contains("is-hidden")) return;
    const container = chartEl.parentElement;
    if (!container) return;
    const point = event.renderedPosition || event.position;
    if (!point) return;
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    const cardWidth = Math.min(card.offsetWidth || 360, containerWidth - 16);
    const cardHeight = Math.min(card.offsetHeight || 220, containerHeight - 16);
    const desiredLeft = Math.min(Math.max(point.x + 16, 12), Math.max(12, containerWidth - cardWidth - 12));
    const desiredTop = Math.min(Math.max(point.y + 16, 12), Math.max(12, containerHeight - cardHeight - 12));
    card.style.left = `${desiredLeft}px`;
    card.style.top = `${desiredTop}px`;
  }

  function tripleRowsForNode(nodeId) {
    const graph = state.currentGraph;
    if (!graph) return [];
    return graph.links
      .filter((link) => link.source === nodeId || link.target === nodeId)
      .map((link) => ({
        source: graph.nodeMap.get(link.source)?.label || link.source,
        predicate: String(link.value || link.predicate || ""),
        target: graph.nodeMap.get(link.target)?.label || link.target,
        module: link.module,
        kind: link.edgeFamily,
        path: link.profilePath || "",
        rationale: link.rationale || ""
      }))
      .sort((left, right) => left.predicate.localeCompare(right.predicate) || left.target.localeCompare(right.target));
  }

  function renderHoverCard(title, subtitle, rows) {
    const card = ensureHoverCard();
    if (!card) return;
    const preview = rows.slice(0, 12);
    card.innerHTML = `
      <div class="explorer-hovercard__head">
        <strong>${escapeHtml(title)}</strong>
        <span class="explorer-hovercard__label">${escapeHtml(subtitle)}</span>
      </div>
      <div class="explorer-hovercard__body">
        ${preview.length ? preview.map((row) => `
          <div class="explorer-hovercard__triple">
            <div class="explorer-hovercard__spo"><strong>${escapeHtml(row.source)}</strong> <code>${escapeHtml(row.predicate)}</code> <strong>${escapeHtml(row.target)}</strong></div>
            <div class="explorer-hovercard__meta">${escapeHtml(row.module)}${row.kind ? ` | ${escapeHtml(row.kind)}` : ""}${row.path ? ` | path: ${escapeHtml(row.path)}` : ""}</div>
            ${row.rationale ? `<div class="explorer-hovercard__meta">${escapeHtml(row.rationale)}</div>` : ""}
          </div>
        `).join("") : '<div class="explorer-empty">No visible SPO relations for this selection.</div>'}
        ${rows.length > preview.length ? `<div class="explorer-hovercard__meta">Showing ${preview.length} of ${rows.length} visible relations.</div>` : ""}
      </div>
    `;
    card.classList.remove("is-hidden");
    card.setAttribute("aria-hidden", "false");
  }

  function hideHoverCard() {
    const card = ensureHoverCard();
    if (!card) return;
    card.classList.add("is-hidden");
    card.setAttribute("aria-hidden", "true");
  }

  function showHoverCardForNode(nodeId, event) {
    const graph = state.currentGraph;
    if (!graph) return;
    const node = graph.nodeMap.get(nodeId);
    if (!node) return;
    renderHoverCard(node.label, "Node relations", tripleRowsForNode(nodeId));
    positionHoverCard(event);
  }

  function showHoverCardForEdge(edgeId, event) {
    const graph = state.currentGraph;
    if (!graph) return;
    const link = graph.links.find((item) => `${item.source}|${item.target}|${item.predicate}|${item.module}` === edgeId);
    if (!link) return;
    const row = {
      source: graph.nodeMap.get(link.source)?.label || link.source,
      predicate: String(link.value || link.predicate || ""),
      target: graph.nodeMap.get(link.target)?.label || link.target,
      module: link.module,
      kind: link.edgeFamily,
      path: link.profilePath || "",
      rationale: link.rationale || ""
    };
    renderHoverCard(row.predicate, "Edge relation", [row]);
    positionHoverCard(event);
  }

  function downloadRelationsAsExcel(rows, selectedNode) {
    if (!rows.length) return;
    const tableRows = rows.map((row) => `
      <tr>
        <td>${escapeHtml(row.source)}</td>
        <td>${escapeHtml(row.predicate)}</td>
        <td>${escapeHtml(row.target)}</td>
        <td>${escapeHtml(row.module)}</td>
      </tr>
    `).join("");
    const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <style>
      table { border-collapse: collapse; font-family: Arial, sans-serif; }
      th, td { border: 1px solid #b8c0c8; padding: 6px 8px; text-align: left; vertical-align: top; }
      th { background: #eef3f5; font-weight: 700; }
      h1 { font-family: Arial, sans-serif; font-size: 18px; }
      p { font-family: Arial, sans-serif; color: #3d4b55; }
    </style>
  </head>
  <body>
    <h1>H2KG Visible Relations</h1>
    <p>Selection: ${escapeHtml(selectedNode?.label || "Current graph selection")}</p>
    <table>
      <thead><tr><th>Source</th><th>Predicate</th><th>Target</th><th>Module</th></tr></thead>
      <tbody>${tableRows}</tbody>
    </table>
  </body>
</html>`;
    const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `h2kg-visible-relations-${slugify(selectedNode?.localName || selectedNode?.label || "selection")}.xls`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function renderSearchStatus(mode, rows, query) {
    if (mode === "starter") {
      searchStatusEl.textContent = "Suggested starting points from the published whole-ontology release. Choose one to seed the graph.";
      return;
    }
    const scopeText = toggleEnabled("includeExternalSearch") ? "local and aligned external" : "local";
    searchStatusEl.textContent = `${rows.length} ${scopeText} suggestion${rows.length === 1 ? "" : "s"} for "${query.trim()}".`;
  }

  function renderResults(rows, mode) {
    currentSuggestions = rows;
    if (!rows.length) {
      resultsEl.innerHTML = `<div class="explorer-empty">${mode === "starter" ? "No starter terms are available with the current filters." : "No ontology terms match the current query."}</div>`;
      return;
    }
    resultsEl.innerHTML = rows.map((node, index) => `
      <button class="explorer-result ${node.id === state.seedId ? "is-active" : ""} ${index === state.highlightedIndex ? "is-highlighted" : ""}" type="button" data-explorer-result="${escapeHtml(node.id)}">
        <strong>${escapeHtml(node.label)}</strong>
        <small>${escapeHtml(node.display_class || node.category)}</small>
        <div class="explorer-result__meta">
          <span>${escapeHtml(node.localName || nodeQname(node) || node.iri)}</span>
          <span>${escapeHtml((node.modules || []).join(", "))}</span>
          <span>${node.local ? "Local" : "External"}</span>
        </div>
        <small>${escapeHtml(String(node.description || "").slice(0, 170))}</small>
      </button>
    `).join("");
    resultsEl.querySelectorAll("[data-explorer-result]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          state.seedId = button.dataset.explorerResult;
          selectNode(button.dataset.explorerResult, { reset: true });
        });
      });
    });
  }

  function renderTrail(view) {
    const rows = state.trail.map((id) => view.nodeMap.get(id)).filter(Boolean);
    if (!rows.length) {
      trailEl.innerHTML = '<div class="explorer-empty">The traversal trail appears after you select a term.</div>';
      return;
    }
    trailEl.innerHTML = rows.map((node) => `
      <button type="button" class="${node.id === state.selectedId ? "is-active" : ""}" data-explorer-trail="${escapeHtml(node.id)}">${escapeHtml(node.label)}</button>
    `).join("");
    trailEl.querySelectorAll("[data-explorer-trail]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          selectNode(button.dataset.explorerTrail, { reset: false });
        });
      });
    });
  }

  function renderBreadcrumb(node) {
    if (!breadcrumbEl) return;
    if (!node || !(node.modules || []).includes("taxonomy")) {
      breadcrumbEl.innerHTML = "<span>No taxonomy path is assigned to this resource.</span>";
      return;
    }
    const allNodes = new Map((payload?.nodes || []).map((item) => [item.id, item]));
    const path = [...(node.taxonomy_path || []), node.id]
      .map((id) => allNodes.get(id))
      .filter(Boolean);
    breadcrumbEl.innerHTML = path.map((item, index) => `
      ${index ? '<span class="separator" aria-hidden="true">/</span>' : ""}
      <button type="button" data-explorer-breadcrumb-node="${escapeHtml(item.id)}">${escapeHtml(item.label)}</button>
    `).join("");
    breadcrumbEl.querySelectorAll("[data-explorer-breadcrumb-node]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          state.seedId = state.seedId || button.dataset.explorerBreadcrumbNode;
          selectNode(button.dataset.explorerBreadcrumbNode, { reset: true });
        });
      });
    });
  }

  const alignmentRelationLabel = (relation) => ({
    "skos:exactMatch": "exact equivalent",
    "skos:broadMatch": "H2KG narrower than",
    "skos:narrowMatch": "H2KG broader than",
    "skos:relatedMatch": "related to",
    "owl:equivalentClass": "configured equivalent class",
    "owl:equivalentProperty": "configured equivalent property",
    "rdfs:subClassOf": "configured subclass of",
    "rdfs:subPropertyOf": "configured subproperty of"
  })[relation] || relation || "mapping";

  function assertedAlignmentHtml(node) {
    const rows = node.external_alignments || [];
    if (!rows.length) return "";
    return `<div class="explorer-inspector__section"><strong>External alignments</strong>${rows.map((row) => `
      <p><strong>${escapeHtml(alignmentRelationLabel(row.relation))}</strong><br>
      <a href="${escapeHtml(row.target_iri)}">${escapeHtml(row.target_label || row.target_iri)}</a>
      ${row.ontology_id ? `<br>${escapeHtml(row.ontology_id)}${row.ontology_version ? ` · ${escapeHtml(row.ontology_version)}` : ""}` : ""}
      ${row.collections?.length ? `<br>${escapeHtml(row.collections.join(", "))}` : ""}
      ${row.alignment_category ? `<br>Category: ${escapeHtml(row.alignment_category.replaceAll("_", " "))}` : ""}
      ${row.confidence ? `<br>Confidence: ${escapeHtml(row.confidence)}` : ""}
      ${row.evidence ? `<br>${escapeHtml(row.evidence)}` : ""}
      ${row.tib_catalogue_url ? `<br><a href="${escapeHtml(row.tib_catalogue_url)}">TIB catalogue record</a>` : ""}</p>
    `).join("")}</div>`;
  }

  async function renderNonAssertedAlignmentEvidence(node) {
    const target = inspectorEl.querySelector("[data-external-evidence-for]");
    if (!target || !node.local || !alignmentEvidencePath) return;
    if (!alignmentEvidencePromise) {
      alignmentEvidencePromise = fetch(alignmentEvidencePath)
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then((data) => { alignmentEvidencePayload = data; return data; });
    }
    try {
      const data = alignmentEvidencePayload || await alignmentEvidencePromise;
      if (target.dataset.externalEvidenceFor !== node.id) return;
      const rows = data.by_h2kg_iri?.[node.id] || [];
      if (!rows.length) {
        target.innerHTML = '<p>No non-asserted related or directional candidate is recorded for this term in the compact collection-level index.</p>';
        return;
      }
      target.innerHTML = rows.map((row) => `<p><strong>${escapeHtml(row.relation_label)}</strong><br><a href="${escapeHtml(row.target_iri)}">${escapeHtml(row.target_label || row.target_iri)}</a><br>${escapeHtml(row.ontology_id)}${row.ontology_version ? ` · ${escapeHtml(row.ontology_version)}` : ""} · ${escapeHtml(row.collection)}<br>${escapeHtml(row.evidence)}${row.tib_catalogue_url ? `<br><a href="${escapeHtml(row.tib_catalogue_url)}">TIB catalogue record</a>` : ""}</p>`).join("") + '<p><a href="tib-benchmark.html">Open the full ontology-level benchmark</a></p>';
    } catch (_error) {
      target.innerHTML = '<p>Benchmark evidence could not be loaded. The asserted bridge remains available above.</p>';
    }
  }

  function workflowUsageHtml(node) {
    const rows = node.workflow_usages || [];
    if (!rows.length) return '<p>No contextual workflow use is asserted for this class.</p>';
    const unique = new Map();
    rows.forEach((row) => {
      const key = `${row.source_iri}|${row.relation}|${row.target_iri}|${row.path}`;
      unique.set(key, row);
    });
    return Array.from(unique.values()).slice(0, 24).map((row) => `
      <p><strong>${escapeHtml(row.source_label || row.source_iri)}</strong>
      ${escapeHtml(row.relation)}
      <strong>${escapeHtml(row.target_label || row.target_iri)}</strong>
      ${row.path ? `<br>Path: <code>${escapeHtml(row.path)}</code>` : ""}
      ${row.rationale ? `<br>${escapeHtml(row.rationale)}` : ""}</p>
    `).join("");
  }

  function renderInspector(node, graph) {
    if (!node) {
      inspectorEl.innerHTML = '<div class="explorer-empty">Pick a term to inspect its stable IRI, definition, and graph role.</div>';
      return;
    }
    const referenceHref = node.local ? nodeAnchorHref(node) : node.iri;
    inspectorEl.innerHTML = `
      <div class="explorer-inspector">
        <div class="explorer-inspector__section">
          <strong>${escapeHtml(node.label)}</strong>
          <div class="explorer-chip-row">
            <span class="explorer-chip">${node.local ? "Local H2KG" : "External aligned"}</span>
            <span class="explorer-chip">${escapeHtml(node.display_class || node.category)}</span>
            <span class="explorer-chip">${escapeHtml(node.deprecated || "Active")}</span>
            ${node.taxonomy_top_branch ? `<span class="explorer-chip">${escapeHtml(node.taxonomy_top_branch)}</span>` : ""}
            ${(node.workflow_badges || []).map((badge) => `<span class="explorer-chip">${escapeHtml(badge)}</span>`).join("")}
          </div>
        </div>
        <div class="explorer-inspector__section">
          <strong>Stable IRI</strong>
          <p><code>${escapeHtml(node.iri)}</code></p>
          <div class="button-row">
            <a class="inline-button inline-button--small" href="${escapeHtml(referenceHref)}">Open reference</a>
            <button type="button" class="inline-button inline-button--small inline-button--ghost" data-copy-iri="${escapeHtml(node.iri)}">Copy IRI</button>
          </div>
        </div>
        <div class="explorer-inspector__section">
          <strong>Definition</strong>
          <p>${escapeHtml(node.description || "No definition recorded.")}</p>
        </div>
        ${node.deprecated === "Deprecated" ? `<div class="explorer-inspector__section"><strong>Compatibility status</strong><p>This identifier is retained for compatibility and excluded from normal taxonomy expansion.${node.replacement_iri ? `<br>Canonical replacement: <code>${escapeHtml(node.replacement_iri)}</code>` : ""}${(node.migration_target_iris || []).length ? `<br>Context-specific migration targets: ${(node.migration_target_iris || []).map((iri) => `<code>${escapeHtml(iri)}</code>`).join(", ")}` : ""}${node.profile_fallback_iri ? `<br>Profile fallback: <code>${escapeHtml(node.profile_fallback_iri)}</code>` : ""}</p></div>` : ""}
        ${assertedAlignmentHtml(node)}
        ${node.local ? `<div class="explorer-inspector__section"><strong>Benchmark evidence, not asserted</strong><div data-external-evidence-for="${escapeHtml(node.id)}"><p>Loading compact benchmark evidence...</p></div></div>` : ""}
        ${node.taxonomy_parent_label || node.taxonomy_top_branch ? `<div class="explorer-inspector__section"><strong>Intrinsic classification</strong><p>Parent: ${escapeHtml(node.taxonomy_parent_label || "Top-level branch")}<br>Top branch: ${escapeHtml(node.taxonomy_top_branch || "Not assigned")}<br>Semantic role: ${escapeHtml(node.taxonomy_role || "Class")}<br>Module: ${escapeHtml(node.taxonomy_module || "core")}</p></div>` : ""}
        ${node.local ? `<div class="explorer-inspector__section"><strong>Workflow usage</strong>${workflowUsageHtml(node)}</div>` : ""}
        ${node.definition_status ? `<div class="explorer-inspector__section"><strong>Governance</strong><p>Status: ${escapeHtml(node.governance_status || "approved")}<br>Definition status: ${escapeHtml(node.definition_status)}<br>Correction action: ${escapeHtml(node.correction_action || node.migration_action || "retain")}</p></div>` : ""}
        ${(node.notations || []).length ? `<div class="explorer-inspector__section"><strong>Notation</strong><p>${escapeHtml(node.notations.join("; "))}</p></div>` : ""}
        ${(node.quantity_guidance || []).length ? `<div class="explorer-inspector__section"><strong>Quantity guidance</strong>${node.quantity_guidance.map((row) => `<p>${escapeHtml([row.quantity_kind, row.unit].filter(Boolean).join(" | "))}<br>${escapeHtml(row.description || "")}</p>`).join("")}</div>` : ""}
        ${(node.sources || []).length ? `<div class="explorer-inspector__section"><strong>Source</strong>${node.sources.map((source) => `<p>${source.startsWith("http") ? `<a href="${escapeHtml(source)}">${escapeHtml(source)}</a>` : escapeHtml(source)}</p>`).join("")}</div>` : ""}
        <div class="explorer-inspector__section">
          <strong>Visualization context</strong>
          <p>${escapeHtml(node.id === graph.center?.id ? "Current focus term." : "Visible through the current expanded neighborhood.")} Direct links in the explorer dataset: ${escapeHtml(String(node.degree || 0))}. Modules: ${escapeHtml((node.modules || []).join(", "))}.</p>
        </div>
      </div>
    `;
    renderNonAssertedAlignmentEvidence(node);
    inspectorEl.querySelectorAll("[data-copy-iri]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(button.dataset.copyIri || "");
          button.textContent = "Copied";
          setTimeout(() => { button.textContent = "Copy IRI"; }, 1000);
        } catch (_error) {
          button.textContent = "Copy failed";
        }
      });
    });
  }

  function renderRelations(graph) {
    if (!graph.center) {
      state.currentRelations = [];
      if (downloadRelationsEl) downloadRelationsEl.disabled = true;
      relationsEl.innerHTML = '<div class="explorer-empty">Visible relations will appear here after you select a term.</div>';
      return;
    }
    const rows = graph.links
      .map((link) => ({
        source: graph.nodeMap.get(link.source)?.label || link.source,
        predicate: String(link.value || link.predicate || ""),
        target: graph.nodeMap.get(link.target)?.label || link.target,
        module: link.module,
        kind: link.edgeFamily,
        path: link.profilePath || "",
        rationale: link.rationale || ""
      }))
      .sort((left, right) => left.predicate.localeCompare(right.predicate) || left.target.localeCompare(right.target));
    state.currentRelations = rows;
    if (downloadRelationsEl) downloadRelationsEl.disabled = rows.length === 0;
    if (!rows.length) {
      relationsEl.innerHTML = '<div class="explorer-empty">No visible relations remain with the current graph filters.</div>';
      return;
    }
    relationsEl.innerHTML = `
      <table class="explorer-relations">
        <thead>
          <tr><th>Source</th><th>Predicate</th><th>Target</th><th>Path</th><th>Module</th></tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.source)}</td>
              <td><code>${escapeHtml(row.predicate)}</code></td>
              <td>${escapeHtml(row.target)}</td>
              <td>${row.path ? `<code>${escapeHtml(row.path)}</code>` : "-"}</td>
              <td>${escapeHtml(row.module)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  function renderGraph(graph) {
    state.currentGraph = graph;
    hideHoverCard();
    countNodesEl.textContent = String(graph.nodes.length);
    countEdgesEl.textContent = String(graph.links.length);
    countExpandedEl.textContent = String(graph.meta.expandedCount || 0);
    if (!graph.center) {
      hideHoverCard();
      graphNoteEl.textContent = "Search for a term or choose a suggested starting point to render the ontology graph.";
      if (cy) cy.elements().remove();
      return;
    }
    const viewLabel = state.viewMode === "taxonomy" ? "taxonomy hierarchy" : state.viewMode === "combined" ? "combined taxonomy and workflow-use neighborhood" : "workflow-use neighborhood";
    graphNoteEl.textContent = `Showing the direct ${viewLabel} for ${graph.center.label}. Click a visible node to recenter and expand the exploration trail.`;
    const instance = ensureCy();
    instance.elements().remove();
    instance.add(buildCyElements(graph));
    runLayout(graph);
  }

  function syncSelection(view, suggestions, mode) {
    if (!view.nodeMap.size) {
      state.selectedId = null;
      state.seedId = null;
      state.expandedIds = new Set();
      return;
    }
    if (state.seedId && !view.nodeMap.has(state.seedId)) state.seedId = null;
    if (state.selectedId && !view.nodeMap.has(state.selectedId)) {
      state.selectedId = null;
      state.expandedIds = new Set();
    }
    if (!state.selectedId && mode === "starter") return;
    if (!state.selectedId && state.seedId && view.nodeMap.has(state.seedId)) {
      selectNode(state.seedId, { reset: false });
    }
    if (!state.seedId && suggestions.length) state.seedId = suggestions[0].id;
  }

  function currentSuggestionMode(query) {
    return normalize(query) ? "search" : "starter";
  }

  function currentSuggestionsForView(view, query) {
    return currentSuggestionMode(query) === "search" ? searchResults(query) : starterSuggestions(view);
  }

  function renderAll() {
    if (!payload) return;
    const view = buildBaseView();
    if (undoButtonEl) undoButtonEl.disabled = state.history.length === 0;
    const query = searchInputEl.value;
    const mode = currentSuggestionMode(query);
    const suggestions = currentSuggestionsForView(view, query);
    syncSelection(view, suggestions, mode);
    if (state.highlightedIndex >= suggestions.length) {
      state.highlightedIndex = Math.max(0, suggestions.length - 1);
    }
    renderSearchStatus(mode, suggestions, query);
    renderResults(suggestions, mode);
    renderTrail(view);
    const graph = buildExpandedGraph(view);
    renderGraph(graph);
    renderInspector(graph.center, graph);
    renderBreadcrumb(graph.center);
    renderRelations(graph);
  }

  function applyDeepLink() {
    const params = new URLSearchParams(window.location.search);
    const iri = params.get("iri");
    const requestedView = params.get("view");
    if (["relations", "taxonomy", "combined"].includes(requestedView)) {
      const input = root.querySelector(`[data-explorer-view][value="${requestedView}"]`);
      if (input) input.checked = true;
    }
    if (!iri || !payload) return;
    const match = (payload.nodes || []).find((node) => node.iri === iri);
    if (!match) return;
    state.seedId = match.id;
    selectNode(match.id, { reset: true });
  }

  function syncLayerCount() {
    if (!layerCountEl) return;
    const modules = Array.from(root.querySelectorAll("[data-explorer-module]"));
    const enabled = modules.filter((input) => input.checked).length;
    layerCountEl.textContent = `${enabled} of ${modules.length} enabled`;
  }

  searchInputEl.addEventListener("input", () => {
    state.highlightedIndex = 0;
    renderAll();
  });
  searchInputEl.addEventListener("keydown", (event) => {
    if (!currentSuggestions.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      state.highlightedIndex = Math.min(state.highlightedIndex + 1, currentSuggestions.length - 1);
      renderAll();
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      state.highlightedIndex = Math.max(state.highlightedIndex - 1, 0);
      renderAll();
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const node = currentSuggestions[state.highlightedIndex];
      if (!node) return;
      runUndoable(() => {
        state.seedId = node.id;
        selectNode(node.id, { reset: true });
      });
    }
  });

  root.querySelectorAll("[data-explorer-module], [data-explorer-toggle], [data-explorer-view], [data-explorer-branch]").forEach((input) => {
    input.addEventListener("change", () => {
      syncLayerCount();
      renderAll();
    });
  });
  document.addEventListener("click", (event) => {
    if (layerMenuEl?.open && !layerMenuEl.contains(event.target)) layerMenuEl.open = false;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && layerMenuEl?.open) {
      layerMenuEl.open = false;
      layerMenuEl.querySelector("summary")?.focus();
    }
  });
    root.querySelectorAll("[data-explorer-action]").forEach((button) => {
      button.addEventListener("click", () => {
      if (button.dataset.explorerAction === "undo") {
        undoLastStep();
      }
      if (button.dataset.explorerAction === "reset") {
        runUndoable(() => {
          const seed = state.seedId || state.selectedId;
          if (!seed) return;
          state.selectedId = seed;
          state.expandedIds = new Set([seed]);
          updateTrail(seed);
        });
      }
      if (button.dataset.explorerAction === "clear") {
        runUndoable(() => {
          searchInputEl.value = "";
          state.selectedId = null;
          state.seedId = null;
          state.expandedIds = new Set();
          state.trail = [];
          state.highlightedIndex = 0;
        });
      }
      });
    });
    if (downloadRelationsEl) {
      downloadRelationsEl.addEventListener("click", () => {
        downloadRelationsAsExcel(state.currentRelations || [], state.currentGraph?.center || null);
      });
    }

    syncLayerCount();
    fetch(dataPath)
    .then((response) => response.json())
    .then((data) => {
      payload = data;
      applyDeepLink();
      renderAll();
    })
    .catch((error) => {
      console.error("Failed to load explorer dataset", error);
      resultsEl.innerHTML = '<div class="explorer-empty">The explorer dataset could not be loaded.</div>';
      graphNoteEl.textContent = "The ontology graph is unavailable because the explorer dataset could not be loaded.";
    });
});
