
document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-explorer-root]");
  if (!root) return;

  const dataPath = root.dataset.explorerData;
  const referencePage = root.dataset.referencePage || "../hydrogen-ontology.html";
  const searchInputEl = root.querySelector("[data-explorer-search]");
  const searchStatusEl = root.querySelector("[data-explorer-search-status]");
  const resultsEl = root.querySelector("[data-explorer-results]");
  const trailEl = root.querySelector("[data-explorer-trail]");
  const graphNoteEl = root.querySelector("[data-explorer-graph-note]");
  const inspectorEl = root.querySelector("[data-explorer-inspector]");
  const relationsEl = root.querySelector("[data-explorer-relations]");
  const chartEl = root.querySelector("[data-explorer-chart]");
  const countNodesEl = root.querySelector('[data-explorer-count="nodes"]');
  const countEdgesEl = root.querySelector('[data-explorer-count="edges"]');
  const countExpandedEl = root.querySelector('[data-explorer-count="expanded"]');
  const undoButtonEl = root.querySelector('[data-explorer-action="undo"]');

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
  let cy = null;
  let currentSuggestions = [];

  const state = {
    selectedId: null,
    seedId: null,
    expandedIds: new Set(),
    trail: [],
    history: [],
    highlightedIndex: 0
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
  const toggleEnabled = (name) => Boolean(root.querySelector(`[data-explorer-toggle="${name}"]`)?.checked);
  const nodeQname = (node) => String(node.qname || node.localName || node.iri || "");
  const nodeAnchorHref = (node) => `${referencePage}#${encodeURIComponent(node.anchor || node.localName || "")}`;

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
    return (payload?.nodes || []).filter((node) => {
      if (!isSearchableNode(node)) return false;
      if (!allowExternal && !node.local) return false;
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
    const nodes = (payload.nodes || []).filter((node) => (node.modules || []).some((moduleId) => selectedModules.has(moduleId)));
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links = (payload.links || []).filter((link) => selectedModules.has(link.module) && nodeMap.has(link.source) && nodeMap.has(link.target));
    const adjacency = new Map();
    links.forEach((link) => {
      if (!adjacency.has(link.source)) adjacency.set(link.source, []);
      if (!adjacency.has(link.target)) adjacency.set(link.target, []);
      adjacency.get(link.source).push(link);
      adjacency.get(link.target).push(link);
    });
    return { nodes, nodeMap, links, adjacency };
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
            "background-color": (ele) => ele.data("isCenter") ? "#c86a2b" : ele.data("isLocal") ? "#0f6d7a" : "#9a6d4f",
            "label": "data(label)",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": 120,
            "color": "#132129",
            "text-valign": "bottom",
            "text-margin-y": 8,
            "width": (ele) => ele.data("isCenter") ? 38 : 28,
            "height": (ele) => ele.data("isCenter") ? 38 : 28,
            "border-width": 1.4,
            "border-color": "rgba(19,33,41,0.18)"
          }
        },
        {
          selector: "edge",
          style: {
            "line-color": "rgba(19,33,41,0.24)",
            "target-arrow-color": "rgba(19,33,41,0.24)",
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
    return cy;
  }

  function runLayout(graph) {
    const instance = ensureCy();
    if (!graph.nodes.length) return;
    const dense = graph.nodes.length > 28 || graph.links.length > 34;
    instance.layout(
      dense
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
        isCenter: node.id === graph.center?.id
      }
    }));
    const edges = graph.links.map((link) => ({
      data: {
        id: `${link.source}|${link.target}|${link.predicate}|${link.module}`,
        source: link.source,
        target: link.target,
        label: String(link.value || link.predicate || "")
      }
    }));
    return [...nodes, ...edges];
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
        <div class="explorer-inspector__section">
          <strong>Graph role</strong>
          <p>${escapeHtml(node.id === graph.center?.id ? "Current focus term." : "Visible through the current expanded neighborhood.")} Direct links in the explorer dataset: ${escapeHtml(String(node.degree || 0))}. Modules: ${escapeHtml((node.modules || []).join(", "))}.</p>
        </div>
      </div>
    `;
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
      relationsEl.innerHTML = '<div class="explorer-empty">Visible relations will appear here after you select a term.</div>';
      return;
    }
    const rows = graph.links
      .map((link) => ({
        source: graph.nodeMap.get(link.source)?.label || link.source,
        predicate: String(link.value || link.predicate || ""),
        target: graph.nodeMap.get(link.target)?.label || link.target,
        module: link.module,
        kind: link.edgeFamily
      }))
      .sort((left, right) => left.predicate.localeCompare(right.predicate) || left.target.localeCompare(right.target));
    if (!rows.length) {
      relationsEl.innerHTML = '<div class="explorer-empty">No visible relations remain with the current graph filters.</div>';
      return;
    }
    relationsEl.innerHTML = `
      <table class="explorer-relations">
        <thead>
          <tr><th>Source</th><th>Predicate</th><th>Target</th><th>Module</th></tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.source)}</td>
              <td><code>${escapeHtml(row.predicate)}</code></td>
              <td>${escapeHtml(row.target)}</td>
              <td>${escapeHtml(row.module)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  function renderGraph(graph) {
    countNodesEl.textContent = String(graph.nodes.length);
    countEdgesEl.textContent = String(graph.links.length);
    countExpandedEl.textContent = String(graph.meta.expandedCount || 0);
    if (!graph.center) {
      graphNoteEl.textContent = "Search for a term or choose a suggested starting point to render the ontology graph.";
      if (cy) cy.elements().remove();
      return;
    }
    graphNoteEl.textContent = `Showing the direct visible neighborhood for ${graph.center.label}. Click a visible node to recenter and expand the exploration trail.`;
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
    renderRelations(graph);
  }

  function applyDeepLink() {
    const params = new URLSearchParams(window.location.search);
    const iri = params.get("iri");
    if (!iri || !payload) return;
    const match = (payload.nodes || []).find((node) => node.iri === iri);
    if (!match) return;
    state.seedId = match.id;
    selectNode(match.id, { reset: true });
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

  root.querySelectorAll("[data-explorer-module], [data-explorer-toggle]").forEach((input) => {
    input.addEventListener("change", renderAll);
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
