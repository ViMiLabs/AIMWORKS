document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-visual-explorer]");
  if (!root) return;

  const dataPath = root.dataset.visualData;
  const chartEl = root.querySelector('[data-visual-chart="term"]');
  const searchInputEl = root.querySelector("[data-visual-search]");
  const resultsEl = root.querySelector("[data-search-results]");
  const searchStatusEl = root.querySelector("[data-search-status]");
  const graphNoteEl = root.querySelector("[data-visual-graph-note]");
  const trailEl = root.querySelector("[data-visual-trail]");
  const inspectorEl = root.querySelector("[data-visual-inspector]");
  const relationsEl = root.querySelector("[data-visual-relations]");
  const countNodesEl = root.querySelector('[data-visual-count="nodes"]');
  const countEdgesEl = root.querySelector('[data-visual-count="edges"]');
  const countEdgesInlineEl = root.querySelector('[data-visual-count="edges-inline"]');
  const countModulesEl = root.querySelector('[data-visual-count="modules"]');
  const countExpandedEl = root.querySelector('[data-visual-count="expanded"]');
  const undoButtonEl = root.querySelector('[data-visual-action="undo"]');

  let payload = null;
  let cy = null;
  let currentSuggestions = [];

  const state = {
    selectedId: null,
    seedId: null,
    showExternalNeighbors: false,
    expandedIds: new Set(),
    trail: [],
    history: [],
    highlightedIndex: 0,
  };

  const STARTER_LABELS = [
    "measurement",
    "property",
    "parameter",
    "matter",
    "instrument",
    "manufacturing",
    "process",
    "data",
    "metadata",
    "agent",
  ];
  const MAX_SUGGESTIONS = 16;
  const MAX_VISIBLE_NODES = 72;
  const MAX_NEW_NEIGHBORS_PER_SOURCE = 22;
  const MAX_EDGE_LABELS = 50;
  const MAX_HISTORY = 40;

  const CANONICAL_PREFIXES = [
    ["https://w3id.org/h2kg/hydrogen-ontology#", "h2kg"],
    ["http://purl.org/holy/ns#", "holy"],
    ["https://w3id.org/emmo/domain/electrochemistry#", "electrochemistry"],
    ["https://w3id.org/emmo/domain/pemfc#", "pemfc"],
    ["https://w3id.org/emmo#", "emmo"],
    ["http://qudt.org/schema/qudt/", "qudt"],
    ["http://qudt.org/vocab/unit/", "unit"],
    ["http://qudt.org/vocab/quantitykind/", "quantitykind"],
    ["http://purl.obolibrary.org/obo/CHEBI_", "chebi"],
    ["http://openenergy-platform.org/ontology/oeo/", "oeo"],
  ];

  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const normalize = (value) => String(value || "").trim().toLowerCase();
  const stripKey = (value) => normalize(value).replace(/[^a-z0-9]+/g, "");
  const activeModules = () => Array.from(root.querySelectorAll("[data-module-toggle]:checked")).map((input) => input.value);
  const moduleInputs = () => Array.from(root.querySelectorAll("[data-module-toggle]"));

  function canonicalQnameFromIri(iri, fallback = "") {
    const value = String(iri || "");
    for (const [base, prefix] of CANONICAL_PREFIXES.slice().sort((left, right) => right[0].length - left[0].length)) {
      if (value.startsWith(base)) {
        const local = value.slice(base.length);
        return local ? `${prefix}:${local}` : `${prefix}:`;
      }
    }
    return /^ns\d+:/.test(String(fallback || "")) ? (fallback || value) : (fallback || value);
  }

  function nodeQname(node) {
    return canonicalQnameFromIri(node.iri, node.qname || "");
  }

  function linkLabel(link) {
    return canonicalQnameFromIri(link.predicate, link.value || "");
  }

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
    if (distance === 0) return 30;
    if (distance === 1) return 18;
    if (distance === 2) return 9;
    return 0;
  }

  function updateTrail(nodeId) {
    if (!nodeId) return;
    state.trail = state.trail.filter((value) => value !== nodeId);
    state.trail.push(nodeId);
    if (state.trail.length > 8) {
      state.trail = state.trail.slice(state.trail.length - 8);
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
      toggles: Object.fromEntries(
        Array.from(root.querySelectorAll("[data-visual-toggle]")).map((input) => [input.dataset.visualToggle, input.checked])
      ),
    };
  }

  function pushHistorySnapshot() {
    state.history.push(captureSnapshot());
    if (state.history.length > MAX_HISTORY) {
      state.history = state.history.slice(state.history.length - MAX_HISTORY);
    }
  }

  function applySnapshot(snapshot) {
    if (!snapshot) return;
    searchInputEl.value = snapshot.searchValue || "";
    const selectedModules = new Set(snapshot.activeModules || []);
    moduleInputs().forEach((input) => {
      input.checked = selectedModules.has(input.value);
    });
    root.querySelectorAll("[data-visual-toggle]").forEach((input) => {
      input.checked = Boolean(snapshot.toggles?.[input.dataset.visualToggle]);
    });
    state.selectedId = snapshot.selectedId || null;
    state.seedId = snapshot.seedId || null;
    state.expandedIds = new Set(snapshot.expandedIds || []);
    state.trail = Array.isArray(snapshot.trail) ? snapshot.trail.slice(-8) : [];
    state.highlightedIndex = Number.isInteger(snapshot.highlightedIndex) ? snapshot.highlightedIndex : 0;
    syncState();
  }

  function undoLastStep() {
    if (!state.history.length) return;
    applySnapshot(state.history.pop());
    renderAll();
  }

  function runUndoable(action) {
    pushHistorySnapshot();
    action();
    renderAll();
  }

  function selectNode(nodeId, options = {}) {
    if (!nodeId) return;
    state.selectedId = nodeId;
    if (options.reset || !state.expandedIds.size) {
      state.expandedIds = new Set([nodeId]);
    } else {
      state.expandedIds.add(nodeId);
    }
    state.highlightedIndex = 0;
    updateTrail(nodeId);
  }

  function chooseSuggestion(nodeId) {
    if (!nodeId) return;
    ensureNodeModulesActive(nodeId);
    state.seedId = nodeId;
    selectNode(nodeId, { reset: true });
  }

  function ensureNodeModulesActive(nodeId) {
    const node = (payload?.nodes || []).find((candidate) => candidate.id === nodeId);
    if (!node) return;
    const inputMap = new Map(moduleInputs().map((input) => [input.value, input]));
    node.modules.forEach((moduleId) => {
      const input = inputMap.get(moduleId);
      if (input && !input.checked) {
        input.checked = true;
      }
    });
  }

  function syncState() {
    root.querySelectorAll("[data-visual-toggle]").forEach((input) => {
      state[input.dataset.visualToggle] = input.checked;
    });
  }

  function setChartEmpty(message) {
    chartEl.classList.add("is-empty");
    chartEl.dataset.emptyMessage = message;
  }

  function clearChartEmpty() {
    chartEl.classList.remove("is-empty");
    chartEl.dataset.emptyMessage = "";
  }

  function ensureCy() {
    if (cy) return cy;
    cy = cytoscape({
      container: chartEl,
      elements: [],
      minZoom: 0.25,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      selectionType: "single",
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(fill)",
            "border-color": "data(borderColor)",
            "border-width": "data(borderWidth)",
            "width": "data(size)",
            "height": "data(size)",
            "label": "data(name)",
            "color": "#10242d",
            "font-size": "11px",
            "font-family": "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
            "text-wrap": "wrap",
            "text-max-width": "150px",
            "text-valign": "center",
            "text-halign": "center",
            "text-background-opacity": 0.88,
            "text-background-color": "#ffffff",
            "text-background-padding": "3px",
            "text-background-shape": "roundrectangle",
          },
        },
        {
          selector: "node.center",
          style: {
            "font-size": "14px",
            "font-weight": "700",
            "z-index": 10,
          },
        },
        {
          selector: "edge",
          style: {
            "curve-style": "bezier",
            "line-color": "data(color)",
            "target-arrow-color": "data(color)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.9,
            "width": "data(width)",
            "opacity": 0.9,
            "label": "data(label)",
            "font-size": "9px",
            "color": "#334155",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.86,
            "text-background-padding": "2px",
            "text-background-shape": "roundrectangle",
            "text-rotation": "autorotate",
          },
        },
        {
          selector: "edge.no-label",
          style: {
            "label": "",
          },
        },
        {
          selector: ":selected",
          style: {
            "overlay-color": "#ca6d2c",
            "overlay-opacity": 0.08,
          },
        },
      ],
    });
    cy.on("tap", "node", (event) => {
      runUndoable(() => {
        selectNode(event.target.id(), { reset: false });
      });
    });
    cy.on("tap", "edge", (event) => {
      const edge = event.target.data();
      graphNoteEl.textContent = `Selected relation ${edge.label} between ${edge.sourceLabel} and ${edge.targetLabel}.`;
    });
    return cy;
  }

  function buildBaseView() {
    syncState();
    const selectedModules = new Set(activeModules());
    const nodes = (payload.nodes || []).filter((node) => {
      if (node.category === "BlankNode") return false;
      return node.modules.some((moduleId) => selectedModules.has(moduleId));
    });
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links = (payload.links || []).filter((link) => {
      if (!selectedModules.has(link.module)) return false;
      return nodeMap.has(link.source) && nodeMap.has(link.target);
    });
    const adjacency = new Map();
    links.forEach((link) => {
      if (!adjacency.has(link.source)) adjacency.set(link.source, []);
      if (!adjacency.has(link.target)) adjacency.set(link.target, []);
      adjacency.get(link.source).push(link);
      adjacency.get(link.target).push(link);
    });
    return {
      nodes,
      links,
      adjacency,
      nodeMap,
      selectedModules: Array.from(selectedModules),
    };
  }

  function isSearchableNode(node) {
    const localName = String(node.localName || "");
    const iri = String(node.iri || "");
    if (!node.local || node.category === "Ontology" || node.category === "BlankNode") return false;
    if (localName.startsWith("_") || /_QV$/i.test(localName)) return false;
    if (iri.startsWith("file:///")) return false;
    return true;
  }

  function searchCandidates() {
    return (payload?.nodes || []).filter((node) => isSearchableNode(node));
  }

  function starterCandidates(view) {
    return view.nodes.filter((node) => isSearchableNode(node) && node.modules.includes("vocabulary"));
  }

  function scoreNode(node, query) {
    const q = normalize(query);
    if (!q) return 0;

    const label = normalize(node.name);
    const localName = normalize(node.localName || "");
    const qname = normalize(nodeQname(node));
    const iri = normalize(node.iri);
    const details = normalize(node.search_text || node.description || "");
    const tokens = [label, localName, qname, node.display_class || "", node.units || ""];
    let score = 0;

    if (label === q || localName === q || qname === q) score += 150;
    if (label.startsWith(q) || localName.startsWith(q) || qname.startsWith(q)) score += 90;
    if (label.includes(q) || localName.includes(q) || qname.includes(q)) score += 65;
    if (iri.includes(q)) score += 38;
    if (details.includes(q)) score += 24;
    if (normalize(node.display_class).includes(q)) score += 18;
    if (node.modules.includes("vocabulary")) score += 16;
    if (node.modules.includes("schema")) score += 8;
    score += Math.max(...tokens.map((token) => fuzzyBonus(q, token)), 0);
    score += Math.min(Number(node.degree || 0), 120) / 30;

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
        return left.node.name.localeCompare(right.node.name);
      })
      .slice(0, MAX_SUGGESTIONS)
      .map((row) => row.node);
  }

  function starterSuggestions(view) {
    const candidates = starterCandidates(view);
    const starters = [];
    const seen = new Set();

    STARTER_LABELS.forEach((target) => {
      const match = candidates.find((node) => {
        const label = normalize(node.name);
        const localName = normalize(node.localName || "");
        return label === target || localName === target;
      });
      if (match && !seen.has(match.id)) {
        starters.push(match);
        seen.add(match.id);
      }
    });

    candidates
      .slice()
      .sort((left, right) => {
        const leftScore = (left.category === "Class" ? 24 : 0) + Math.min(Number(left.degree || 0), 120);
        const rightScore = (right.category === "Class" ? 24 : 0) + Math.min(Number(right.degree || 0), 120);
        if (rightScore !== leftScore) return rightScore - leftScore;
        return left.name.localeCompare(right.name);
      })
      .forEach((node) => {
        if (!seen.has(node.id) && starters.length < 10) {
          starters.push(node);
          seen.add(node.id);
        }
      });

    return starters;
  }

  function rankExpansionLink(view, sourceId, link) {
    const neighborId = link.source === sourceId ? link.target : link.source;
    const neighbor = view.nodeMap.get(neighborId);
    if (!neighbor) return -999;
    let score = 0;
    if (neighbor.local) score += 70;
    if (neighbor.category === "Class") score += 18;
    if (neighbor.category === "ObjectProperty" || neighbor.category === "DatatypeProperty") score += 14;
    if (link.edgeFamily === "schema") score += 22;
    if (link.edgeFamily === "object_property") score += 16;
    score -= Math.min(Number(neighbor.degree || 0), 160) / 12;
    return score;
  }

  function buildExpandedGraph(view) {
    const center = view.nodeMap.get(state.selectedId);
    if (!center) {
      return {
        center: null,
        nodes: [],
        links: [],
        nodeMap: new Map(),
        meta: { expandedCount: 0, hiddenNeighborCount: 0, selectionLabel: "" },
      };
    }

    const expandedIds = new Set(Array.from(state.expandedIds).filter((id) => view.nodeMap.has(id)));
    expandedIds.add(center.id);

    const visibleIds = new Set([center.id]);
    let hiddenNeighborCount = 0;

    Array.from(expandedIds).forEach((sourceId) => {
      const related = (view.adjacency.get(sourceId) || [])
        .filter((link) => {
          const neighborId = link.source === sourceId ? link.target : link.source;
          const neighbor = view.nodeMap.get(neighborId);
          if (!neighbor) return false;
          if (!state.showExternalNeighbors && !neighbor.local && neighbor.id !== center.id) return false;
          return true;
        })
        .sort((left, right) => rankExpansionLink(view, sourceId, right) - rankExpansionLink(view, sourceId, left));

      let newNeighbors = 0;
      related.forEach((link) => {
        const neighborId = link.source === sourceId ? link.target : link.source;
        const isNew = !visibleIds.has(neighborId);
        if (isNew && (visibleIds.size >= MAX_VISIBLE_NODES || newNeighbors >= MAX_NEW_NEIGHBORS_PER_SOURCE)) {
          hiddenNeighborCount += 1;
          return;
        }
        visibleIds.add(link.source);
        visibleIds.add(link.target);
        if (isNew) {
          newNeighbors += 1;
        }
      });
    });

    const nodes = Array.from(visibleIds)
      .map((id) => view.nodeMap.get(id))
      .filter(Boolean)
      .sort((left, right) => {
        if (left.id === center.id) return -1;
        if (right.id === center.id) return 1;
        return left.name.localeCompare(right.name);
      });
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));
    const links = view.links.filter((link) => nodeMap.has(link.source) && nodeMap.has(link.target));

    return {
      center,
      nodes,
      links,
      nodeMap,
      meta: {
        expandedCount: expandedIds.size,
        hiddenNeighborCount,
        selectionLabel: center.name,
      },
    };
  }

  function edgeColor(edgeFamily) {
    if (edgeFamily === "schema") return "#ca6d2c";
    if (edgeFamily === "relation" || edgeFamily === "object_property") return "#1f7a7a";
    if (edgeFamily === "unit") return "#8b5cf6";
    if (edgeFamily === "quantity_kind") return "#0284c7";
    if (edgeFamily === "provenance") return "#7c3aed";
    return "#64748b";
  }

  function buildCyElements(graph) {
    const showEdgeLabels = graph.links.length <= MAX_EDGE_LABELS;
    const expandedIds = new Set(state.expandedIds);
    const nodeElements = graph.nodes.map((node) => {
      const isCenter = node.id === graph.center.id;
      const isExpanded = expandedIds.has(node.id);
      return {
        data: {
          id: node.id,
          name: node.name,
          iri: node.iri,
          qname: nodeQname(node),
          localName: node.localName || "",
          description: node.description || "",
          display_class: node.display_class || node.category,
          degree: Number(node.degree || 0),
          modules: node.modules || [],
          fill: isCenter ? "#ca6d2c" : isExpanded ? "#1f7a7a" : node.color,
          borderColor: isExpanded && !isCenter ? "#10242d" : "rgba(16, 36, 45, 0.18)",
          borderWidth: isExpanded ? 2 : 1,
          size: isCenter ? 54 : isExpanded ? 42 : Math.max(24, Number(node.symbolSize || 18) + 8),
        },
        classes: `${isCenter ? "center " : ""}${isExpanded ? "expanded" : ""}`.trim(),
      };
    });

    const edgeElements = graph.links.map((link, index) => ({
      data: {
        id: `edge-${index}-${link.source}-${link.target}-${link.predicate}`,
        source: link.source,
        target: link.target,
        label: showEdgeLabels ? linkLabel(link) : "",
        predicate: link.predicate,
        module: link.module,
        edgeFamily: link.edgeFamily,
        color: edgeColor(link.edgeFamily),
        width: link.edgeFamily === "schema" ? 2.6 : link.edgeFamily === "relation" || link.edgeFamily === "object_property" ? 2.1 : 1.7,
        sourceLabel: graph.nodeMap.get(link.source)?.name || link.source,
        targetLabel: graph.nodeMap.get(link.target)?.name || link.target,
      },
      classes: showEdgeLabels ? "" : "no-label",
    }));

    return [...nodeElements, ...edgeElements];
  }

  function runLayout(instance, centerId) {
    if (!instance.nodes().length) return;
    instance.layout({
      name: "cose",
      animate: false,
      fit: true,
      padding: 36,
      nodeRepulsion: 420000,
      idealEdgeLength: 130,
      edgeElasticity: 120,
      gravity: 0.22,
      numIter: 900,
      initialTemp: 180,
      coolingFactor: 0.95,
      componentSpacing: 80,
    }).run();
    const centerNode = instance.getElementById(centerId);
    if (centerNode && centerNode.nonempty()) {
      instance.center(centerNode);
    }
  }

  function renderTable(headers, rows, emptyMessage) {
    if (!rows.length) {
      return `<div class="visual-empty">${escapeHtml(emptyMessage)}</div>`;
    }
    const headerHtml = headers.map((header) => `<th>${escapeHtml(header.label)}</th>`).join("");
    const rowHtml = rows.map((row) => `<tr>${headers.map((header) => `<td>${header.render(row)}</td>`).join("")}</tr>`).join("");
    return `<table class="data-table"><thead><tr>${headerHtml}</tr></thead><tbody>${rowHtml}</tbody></table>`;
  }

  function snippet(text, length = 120) {
    const value = String(text || "").trim();
    if (!value) return "";
    return value.length <= length ? value : `${value.slice(0, length - 1)}...`;
  }

  function renderSearchStatus(mode, rows, query) {
    if (mode === "starter") {
      searchStatusEl.textContent = "Suggested starting points from the published local ontology. Choose one to seed the graph.";
      return;
    }
    searchStatusEl.textContent = `${rows.length} local ontology suggestion${rows.length === 1 ? "" : "s"} for "${query.trim()}". Choose one to recenter the graph.`;
  }

  function renderResults(rows, mode) {
    currentSuggestions = rows;
    if (!rows.length) {
      const emptyMessage = mode === "starter"
        ? "No starting points are available with the current module filters."
        : "No local ontology terms match the current search.";
      resultsEl.innerHTML = `<div class="visual-empty">${escapeHtml(emptyMessage)}</div>`;
      return;
    }

    resultsEl.innerHTML = rows.map((node) => `
      <button class="visual-result ${node.id === state.seedId ? "is-active" : ""} ${rows.indexOf(node) === state.highlightedIndex ? "is-highlighted" : ""}" type="button" data-result-id="${escapeHtml(node.id)}">
        <strong>${escapeHtml(node.name)}</strong>
        <small>${escapeHtml(node.display_class || node.category)}</small>
        <div class="visual-result__meta">
          <span class="visual-badge">${escapeHtml(node.localName || nodeQname(node) || node.iri)}</span>
          <span class="visual-badge">${escapeHtml(node.modules.join(", "))}</span>
          <span class="visual-badge">${escapeHtml(String(node.degree || 0))} links</span>
        </div>
        <small>${escapeHtml(snippet(node.description || ""))}</small>
      </button>
    `).join("");

    resultsEl.querySelectorAll("[data-result-id]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          chooseSuggestion(button.dataset.resultId);
        });
      });
    });
  }

  function renderTrail(view) {
    const rows = state.trail
      .map((id) => view.nodeMap.get(id))
      .filter(Boolean);
    if (!rows.length) {
      trailEl.innerHTML = '<div class="visual-empty">The exploration trail will appear after you select a term.</div>';
      return;
    }
    trailEl.innerHTML = rows.map((node) => `
      <button type="button" class="visual-trail__item ${node.id === state.selectedId ? "is-active" : ""}" data-trail-id="${escapeHtml(node.id)}">
        ${escapeHtml(node.name)}
      </button>
    `).join("");
    trailEl.querySelectorAll("[data-trail-id]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          selectNode(button.dataset.trailId, { reset: false });
        });
      });
    });
  }

  function renderInspector(node, graph) {
    if (!node) {
      inspectorEl.innerHTML = '<div class="visual-empty">Select a suggestion to inspect its label, class, units, mappings, and release metadata.</div>';
      return;
    }

    const detailSections = [];
    if (node.units) detailSections.push(`<div class="visual-inspector__section"><strong>Units</strong><p>${escapeHtml(node.units)}</p></div>`);
    if (node.superclasses) detailSections.push(`<div class="visual-inspector__section"><strong>Superclasses</strong><p>${escapeHtml(node.superclasses)}</p></div>`);
    if (node.domain) detailSections.push(`<div class="visual-inspector__section"><strong>Domain</strong><p>${escapeHtml(node.domain)}</p></div>`);
    if (node.range) detailSections.push(`<div class="visual-inspector__section"><strong>Range</strong><p>${escapeHtml(node.range)}</p></div>`);
    if (node.mappings_text) detailSections.push(`<div class="visual-inspector__section"><strong>Mappings</strong><p>${escapeHtml(node.mappings_text)}</p></div>`);

    inspectorEl.innerHTML = `
      <div>
        <h3>${escapeHtml(node.name)}</h3>
        <div class="visual-inspector__meta">
          <span class="visual-chip">${escapeHtml(node.display_class || node.category)}</span>
          <span class="visual-chip">${node.local ? "Local" : "External"}</span>
          <span class="visual-chip">${escapeHtml(node.deprecated || "Active")}</span>
        </div>
      </div>
      <div class="visual-inspector__section">
        <strong>IRI</strong>
        <p><a href="${escapeHtml(node.iri)}"><code>${escapeHtml(node.iri)}</code></a></p>
      </div>
      <div class="visual-inspector__section">
        <strong>Local form</strong>
        <p><code>${escapeHtml(node.localName || nodeQname(node))}</code></p>
      </div>
      <div class="visual-inspector__section">
        <strong>Definition</strong>
        <p>${escapeHtml(node.description || "No definition or comment recorded.")}</p>
      </div>
      <div class="visual-inspector__section">
        <strong>Explorer status</strong>
        <p>${escapeHtml(node.id === graph.center?.id ? "Current focus node." : "Visible through the current expanded neighborhood.")} ${escapeHtml(node.id === state.seedId ? "This is also the current search seed." : "")} Degree: ${escapeHtml(String(node.degree || 0))}. Modules: ${escapeHtml(node.modules.join(", "))}.</p>
      </div>
      ${detailSections.join("")}
    `;
  }

  function renderRelations(graph) {
    const rows = graph.links.map((link) => ({
      source: graph.nodeMap.get(link.source)?.name || link.source,
      predicate: linkLabel(link),
      target: graph.nodeMap.get(link.target)?.name || link.target,
      edgeFamily: link.edgeFamily,
      module: link.module,
    }));

    relationsEl.innerHTML = renderTable(
      [
        { label: "Source", render: (row) => escapeHtml(row.source) },
        { label: "Predicate", render: (row) => `<code>${escapeHtml(row.predicate)}</code>` },
        { label: "Target", render: (row) => escapeHtml(row.target) },
        { label: "Kind", render: (row) => escapeHtml(row.edgeFamily) },
        { label: "Module", render: (row) => escapeHtml(row.module) },
      ],
      rows,
      "Visible relations will appear here after you select a term."
    );
  }

  function renderGraphNote(graph) {
    if (!graph.center) {
      graphNoteEl.textContent = "Search for a local ontology term or use a suggested starting point to initialize the explorer.";
      return;
    }
    if (!graph.links.length) {
      graphNoteEl.textContent = "This term is loaded, but no visible relationships remain with the current module and external-term filters.";
      return;
    }
    if (graph.meta.hiddenNeighborCount > 0) {
      graphNoteEl.textContent = `Showing a readable connected subset around ${graph.meta.selectionLabel}. ${graph.meta.hiddenNeighborCount} additional neighbor links are hidden for clarity. Click a visible node to keep exploring.`;
      return;
    }
    graphNoteEl.textContent = `Showing the current connected neighborhood around ${graph.meta.selectionLabel}. Click any visible node to expand further.`;
  }

  function renderGraph(graph) {
    countNodesEl.textContent = String(graph.nodes.length);
    countEdgesEl.textContent = String(graph.links.length);
    countEdgesInlineEl.textContent = String(graph.links.length);
    countExpandedEl.textContent = String(graph.meta.expandedCount);
    renderGraphNote(graph);

    if (!graph.center) {
      setChartEmpty("Search for a local ontology term or choose a starting point to render the ontology graph.");
      if (cy) {
        cy.elements().remove();
      }
      return;
    }

    clearChartEmpty();
    const instance = ensureCy();
    instance.elements().remove();
    instance.add(buildCyElements(graph));
    runLayout(instance, graph.center.id);
  }

  function currentSuggestionMode(query) {
    return normalize(query) ? "search" : "starter";
  }

  function currentSuggestionsForView(view, query) {
    return currentSuggestionMode(query) === "search"
      ? searchResults(query)
      : starterSuggestions(view);
  }

  function syncSelection(view, suggestions, mode) {
    if (!view.nodeMap.size) {
      state.selectedId = null;
      state.seedId = null;
      state.expandedIds = new Set();
      return;
    }
    if (state.seedId && !view.nodeMap.has(state.seedId)) {
      state.seedId = null;
    }
    if (state.selectedId && !view.nodeMap.has(state.selectedId)) {
      state.selectedId = null;
      state.expandedIds = new Set();
    }
    if (!state.selectedId) {
      if (mode === "starter") {
        const fallbackId = (state.seedId && view.nodeMap.has(state.seedId))
          ? state.seedId
          : (suggestions.find((node) => view.nodeMap.has(node.id))?.id || Array.from(view.nodeMap.keys())[0]);
        if (fallbackId) {
          if (!state.seedId && suggestions.some((node) => node.id === fallbackId)) {
            state.seedId = fallbackId;
          }
          selectNode(fallbackId, { reset: true });
        }
      } else if (state.seedId && view.nodeMap.has(state.seedId)) {
        selectNode(state.seedId, { reset: false });
      }
      return;
    }
    if (!state.seedId && suggestions.length) {
      state.seedId = suggestions[0].id;
    }
  }

  function renderAll() {
    if (!payload) return;

    const view = buildBaseView();
    countModulesEl.textContent = String(view.selectedModules.length);
    if (undoButtonEl) {
      undoButtonEl.disabled = state.history.length === 0;
    }

    const query = searchInputEl.value;
    const mode = currentSuggestionMode(query);
    const results = currentSuggestionsForView(view, query);
    syncSelection(view, results, mode);
    if (state.highlightedIndex >= results.length) {
      state.highlightedIndex = Math.max(0, results.length - 1);
    }

    renderSearchStatus(mode, results, query);
    renderResults(results, mode);
    renderTrail(view);

    const graph = buildExpandedGraph(view);
    renderGraph(graph);
    renderInspector(graph.center, graph);
    renderRelations(graph);
  }

  root.querySelectorAll("[data-module-toggle], [data-visual-toggle]").forEach((input) => {
    input.addEventListener("change", renderAll);
  });
  root.querySelectorAll("[data-visual-action]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.visualAction === "undo") {
        undoLastStep();
      }
      if (button.dataset.visualAction === "reset" && (state.seedId || state.selectedId)) {
        runUndoable(() => {
          const seed = state.seedId || state.selectedId;
          state.selectedId = seed;
          state.expandedIds = new Set([seed]);
        });
      }
      if (button.dataset.visualAction === "clear") {
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
  searchInputEl.addEventListener("input", () => {
    state.highlightedIndex = 0;
    renderAll();
  });
  searchInputEl.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "z") {
      event.preventDefault();
      undoLastStep();
      return;
    }
    if (!currentSuggestions.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      state.highlightedIndex = Math.min(state.highlightedIndex + 1, currentSuggestions.length - 1);
      renderAll();
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      state.highlightedIndex = Math.max(state.highlightedIndex - 1, 0);
      renderAll();
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const target = currentSuggestions[state.highlightedIndex] || currentSuggestions[0];
      if (target) {
        runUndoable(() => {
          chooseSuggestion(target.id);
        });
      }
      return;
    }
    if (event.key === "Escape") {
      searchInputEl.value = "";
      state.highlightedIndex = 0;
      renderAll();
    }
  });
  window.addEventListener("resize", () => {
    if (!cy) return;
    cy.resize();
    cy.fit(cy.elements(), 36);
  });
  window.addEventListener("keydown", (event) => {
    const target = event.target;
    const isEditableTarget = target instanceof HTMLElement
      && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
    if (isEditableTarget) return;
    if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "z") {
      event.preventDefault();
      undoLastStep();
    }
  });

  fetch(dataPath)
    .then((response) => {
      if (!response.ok) throw new Error(`Failed to load explorer data from ${dataPath}`);
      return response.json();
    })
    .then((json) => {
      payload = json;
      renderAll();
    })
    .catch((error) => {
      const message = escapeHtml(error.message);
      setChartEmpty(error.message);
      resultsEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      trailEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      inspectorEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      relationsEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      graphNoteEl.textContent = error.message;
      searchStatusEl.textContent = error.message;
    });
});
