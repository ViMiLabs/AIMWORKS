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
  const directSummaryEl = root.querySelector("[data-visual-direct-summary]");
  const neighborSummaryEl = root.querySelector("[data-visual-neighbor-summary]");
  const classFiltersEl = root.querySelector("[data-visual-class-filters]");
  const neighborGroupsEl = root.querySelector("[data-visual-neighbor-groups]");
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
    showExternalNeighbors: true,
    expandedIds: new Set(),
    trail: [],
    history: [],
    highlightedIndex: 0,
    neighborVisibilityMode: "all",
    hiddenPredicateKeys: new Set(),
    hiddenClassKeys: new Set(),
    hiddenDirectNodeIds: new Set(),
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
  const MAX_EDGE_LABELS = 24;
  const MAX_HISTORY = 40;
  const DENSE_GRAPH_NODE_THRESHOLD = 32;
  const DENSE_GRAPH_EDGE_THRESHOLD = 40;
  const RADIAL_RING_BASE = 14;
  const RADIAL_RING_STEP = 8;
  const RADIAL_RING_GAP = 170;

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
  const classKey = (value) => stripKey(value || "other");
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

  function resetDirectVisibilityState() {
    state.neighborVisibilityMode = "all";
    state.hiddenPredicateKeys = new Set();
    state.hiddenClassKeys = new Set();
    state.hiddenDirectNodeIds = new Set();
  }

  function captureSnapshot() {
    return {
      selectedId: state.selectedId,
      seedId: state.seedId,
      expandedIds: Array.from(state.expandedIds),
      trail: state.trail.slice(),
      highlightedIndex: state.highlightedIndex,
      neighborVisibilityMode: state.neighborVisibilityMode,
      hiddenPredicateKeys: Array.from(state.hiddenPredicateKeys),
      hiddenClassKeys: Array.from(state.hiddenClassKeys),
      hiddenDirectNodeIds: Array.from(state.hiddenDirectNodeIds),
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
    state.neighborVisibilityMode = snapshot.neighborVisibilityMode || "all";
    state.hiddenPredicateKeys = new Set(snapshot.hiddenPredicateKeys || []);
    state.hiddenClassKeys = new Set(snapshot.hiddenClassKeys || []);
    state.hiddenDirectNodeIds = new Set(snapshot.hiddenDirectNodeIds || []);
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
    const centerChanged = state.selectedId !== nodeId;
    state.selectedId = nodeId;
    if (centerChanged) {
      resetDirectVisibilityState();
    }
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
            "label": "data(labelText)",
            "color": "#10242d",
            "font-size": "data(fontSize)",
            "font-family": "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
            "text-wrap": "wrap",
            "text-max-width": "data(textMaxWidth)",
            "text-valign": "center",
            "text-halign": "center",
            "text-background-opacity": "data(textBackgroundOpacity)",
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
          selector: "node.outside-label",
          style: {
            "text-valign": "bottom",
            "text-margin-y": 10,
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
            "opacity": "data(opacity)",
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
          selector: "edge.dense-edge",
          style: {
            "text-background-opacity": 0.72,
          },
        },
        {
          selector: "edge.direct-edge",
          style: {
            "line-style": "solid",
            "opacity": 0.9,
          },
        },
        {
          selector: "edge.context-edge",
          style: {
            "line-style": "dashed",
            "opacity": 0.22,
            "target-arrow-shape": "vee",
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

  function computeDepthMap(centerId, links) {
    const adjacency = new Map();
    links.forEach((link) => {
      if (!adjacency.has(link.source)) adjacency.set(link.source, new Set());
      if (!adjacency.has(link.target)) adjacency.set(link.target, new Set());
      adjacency.get(link.source).add(link.target);
      adjacency.get(link.target).add(link.source);
    });

    const depthMap = { [centerId]: 0 };
    const queue = [centerId];
    while (queue.length) {
      const current = queue.shift();
      const currentDepth = Number(depthMap[current] || 0);
      Array.from(adjacency.get(current) || []).forEach((neighborId) => {
        if (Object.prototype.hasOwnProperty.call(depthMap, neighborId)) return;
        depthMap[neighborId] = currentDepth + 1;
        queue.push(neighborId);
      });
    }
    return depthMap;
  }

  function linkKey(link) {
    return `${link.source}|${link.target}|${link.predicate}|${link.module}`;
  }

  function isDirectLink(centerId, link) {
    return link.source === centerId || link.target === centerId;
  }

  function buildDirectRows(view, center) {
    if (!center) return [];
    return (view.adjacency.get(center.id) || [])
      .filter((link) => {
        const neighborId = link.source === center.id ? link.target : link.source;
        const neighbor = view.nodeMap.get(neighborId);
        if (!neighbor) return false;
        if (!state.showExternalNeighbors && !neighbor.local) return false;
        return true;
      })
      .map((link) => {
        const neighborId = link.source === center.id ? link.target : link.source;
        const neighbor = view.nodeMap.get(neighborId);
        const predicate = linkLabel(link);
        const neighborClassLabel = neighbor.display_class || neighbor.category || "Other";
        return {
          id: linkKey(link),
          link,
          predicate,
          predicateKey: stripKey(predicate || link.predicate),
          neighborId,
          neighbor,
          neighborClassLabel,
          neighborClassKey: classKey(neighborClassLabel),
          locality: neighbor.local ? "local" : "external",
        };
      })
      .sort((left, right) => {
        const predicateOrder = left.predicate.localeCompare(right.predicate);
        if (predicateOrder !== 0) return predicateOrder;
        return left.neighbor.name.localeCompare(right.neighbor.name);
      });
  }

  function directRowVisible(row) {
    if (state.hiddenPredicateKeys.has(row.predicateKey)) return false;
    if (state.hiddenClassKeys.has(row.neighborClassKey)) return false;
    if (state.hiddenDirectNodeIds.has(row.neighborId)) return false;
    if (state.neighborVisibilityMode === "local" && !row.neighbor.local) return false;
    if (state.neighborVisibilityMode === "external" && row.neighbor.local) return false;
    return true;
  }

  function summarizeDirectRows(rows, visibleRows) {
    const visibleRowIds = new Set(visibleRows.map((row) => row.id));
    const totalNeighborIds = new Set(rows.map((row) => row.neighborId));
    const visibleNeighborIds = new Set(visibleRows.map((row) => row.neighborId));
    const classMap = new Map();
    const groupMap = new Map();

    rows.forEach((row) => {
      if (!classMap.has(row.neighborClassKey)) {
        classMap.set(row.neighborClassKey, {
          key: row.neighborClassKey,
          label: row.neighborClassLabel,
          totalRows: 0,
          totalNodes: new Set(),
          visibleNodes: new Set(),
        });
      }
      const classEntry = classMap.get(row.neighborClassKey);
      classEntry.totalRows += 1;
      classEntry.totalNodes.add(row.neighborId);
      if (visibleRowIds.has(row.id)) {
        classEntry.visibleNodes.add(row.neighborId);
      }

      if (!groupMap.has(row.predicateKey)) {
        groupMap.set(row.predicateKey, {
          key: row.predicateKey,
          label: row.predicate,
          rows: [],
          classLabels: new Set(),
          visibleRows: 0,
          visibleNodes: new Set(),
          totalNodes: new Set(),
        });
      }
      const groupEntry = groupMap.get(row.predicateKey);
      groupEntry.rows.push(row);
      groupEntry.classLabels.add(row.neighborClassLabel);
      groupEntry.totalNodes.add(row.neighborId);
      if (visibleRowIds.has(row.id)) {
        groupEntry.visibleRows += 1;
        groupEntry.visibleNodes.add(row.neighborId);
      }
    });

    return {
      totalRowCount: rows.length,
      visibleRowCount: visibleRows.length,
      totalNeighborCount: totalNeighborIds.size,
      visibleNeighborCount: visibleNeighborIds.size,
      hiddenNeighborCount: Math.max(totalNeighborIds.size - visibleNeighborIds.size, 0),
      classes: Array.from(classMap.values())
        .map((entry) => ({
          key: entry.key,
          label: entry.label,
          totalRows: entry.totalRows,
          totalNodes: entry.totalNodes.size,
          visibleNodes: entry.visibleNodes.size,
        }))
        .sort((left, right) => {
          if (right.totalNodes !== left.totalNodes) return right.totalNodes - left.totalNodes;
          return left.label.localeCompare(right.label);
        }),
      groups: Array.from(groupMap.values())
        .map((entry) => ({
          key: entry.key,
          label: entry.label,
          rows: entry.rows,
          classLabels: Array.from(entry.classLabels).sort((left, right) => left.localeCompare(right)),
          visibleRows: entry.visibleRows,
          totalRows: entry.rows.length,
          visibleNodes: entry.visibleNodes.size,
          totalNodes: entry.totalNodes.size,
        }))
        .sort((left, right) => {
          if (right.totalRows !== left.totalRows) return right.totalRows - left.totalRows;
          return left.label.localeCompare(right.label);
        }),
    };
  }

  function buildExpandedGraph(view) {
    const center = view.nodeMap.get(state.selectedId);
    if (!center) {
      return {
        center: null,
        nodes: [],
        links: [],
        nodeMap: new Map(),
        meta: {
          expandedCount: 0,
          hiddenNeighborCount: 0,
          selectionLabel: "",
          directRows: [],
          directSummary: summarizeDirectRows([], []),
          visibleDirectRowIds: new Set(),
          visibleDirectNodeIds: new Set(),
        },
      };
    }

    const directRows = buildDirectRows(view, center);
    const visibleDirectRows = directRows.filter((row) => directRowVisible(row));
    const visibleDirectRowIds = new Set(visibleDirectRows.map((row) => row.id));
    const visibleDirectNodeIds = new Set(visibleDirectRows.map((row) => row.neighborId));
    const hiddenDirectNodeIds = new Set(
      Array.from(new Set(directRows.map((row) => row.neighborId))).filter((neighborId) => !visibleDirectNodeIds.has(neighborId))
    );
    const expandedIds = new Set(Array.from(state.expandedIds).filter((id) => view.nodeMap.has(id)));
    expandedIds.add(center.id);
    hiddenDirectNodeIds.forEach((nodeId) => expandedIds.delete(nodeId));

    const visibleIds = new Set([center.id]);
    const hiddenNeighborIds = new Set();

    Array.from(expandedIds).forEach((sourceId) => {
      const related = (view.adjacency.get(sourceId) || [])
        .filter((link) => {
          const neighborId = link.source === sourceId ? link.target : link.source;
          const neighbor = view.nodeMap.get(neighborId);
          if (!neighbor) return false;
          if (!state.showExternalNeighbors && !neighbor.local && neighbor.id !== center.id) {
            hiddenNeighborIds.add(`${link.source}|${link.target}|${link.predicate}`);
            return false;
          }
          if ((hiddenDirectNodeIds.has(link.source) && link.source !== center.id) || (hiddenDirectNodeIds.has(link.target) && link.target !== center.id)) {
            return false;
          }
          if (isDirectLink(center.id, link) && !visibleDirectRowIds.has(linkKey(link))) {
            return false;
          }
          return true;
        })
        .sort((left, right) => rankExpansionLink(view, sourceId, right) - rankExpansionLink(view, sourceId, left));

      related.forEach((link) => {
        visibleIds.add(link.source);
        visibleIds.add(link.target);
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
    const links = view.links.filter((link) => {
      if (!nodeMap.has(link.source) || !nodeMap.has(link.target)) return false;
      if (isDirectLink(center.id, link) && !visibleDirectRowIds.has(linkKey(link))) return false;
      return true;
    });
    const depthMap = computeDepthMap(center.id, links);

    return {
      center,
      nodes,
      links,
      nodeMap,
      meta: {
        expandedCount: expandedIds.size,
        hiddenNeighborCount: hiddenNeighborIds.size,
        selectionLabel: center.name,
        depthMap,
        directRows,
        directSummary: summarizeDirectRows(directRows, visibleDirectRows),
        visibleDirectRowIds,
        visibleDirectNodeIds,
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

  function graphIsDense(graph) {
    return graph.nodes.length >= DENSE_GRAPH_NODE_THRESHOLD || graph.links.length >= DENSE_GRAPH_EDGE_THRESHOLD;
  }

  function shortDisplayName(label, length = 30) {
    const value = String(label || "").trim();
    if (!value) return "";
    return value.length <= length ? value : `${value.slice(0, length - 1)}...`;
  }

  function splitIntoRings(nodes) {
    const rings = [];
    let cursor = 0;
    let ringIndex = 0;
    while (cursor < nodes.length) {
      const capacity = RADIAL_RING_BASE + (ringIndex * RADIAL_RING_STEP);
      rings.push(nodes.slice(cursor, cursor + capacity));
      cursor += capacity;
      ringIndex += 1;
    }
    return rings;
  }

  function radialPositions(graph) {
    const positions = new Map();
    if (!graph.center) return positions;
    positions.set(graph.center.id, { x: 0, y: 0 });

    const depthGroups = new Map();
    graph.nodes.forEach((node) => {
      if (node.id === graph.center.id) return;
      const depth = Number(graph.meta.depthMap?.[node.id] ?? 1);
      if (!depthGroups.has(depth)) depthGroups.set(depth, []);
      depthGroups.get(depth).push(node);
    });

    const depths = Array.from(depthGroups.keys()).sort((left, right) => left - right);
    let radius = 220;
    depths.forEach((depth) => {
      const ordered = depthGroups.get(depth)
        .slice()
        .sort((left, right) => {
          const leftExpanded = state.expandedIds.has(left.id) ? 1 : 0;
          const rightExpanded = state.expandedIds.has(right.id) ? 1 : 0;
          if (rightExpanded !== leftExpanded) return rightExpanded - leftExpanded;
          const leftLocal = left.local ? 1 : 0;
          const rightLocal = right.local ? 1 : 0;
          if (rightLocal !== leftLocal) return rightLocal - leftLocal;
          const leftDegree = Number(left.degree || 0);
          const rightDegree = Number(right.degree || 0);
          if (rightDegree !== leftDegree) return rightDegree - leftDegree;
          return left.name.localeCompare(right.name);
        });
      const rings = splitIntoRings(ordered);
      rings.forEach((ringNodes, ringIndex) => {
        const ringRadius = radius + (ringIndex * RADIAL_RING_GAP);
        const angleOffset = ((depth + ringIndex) % 2) * (Math.PI / Math.max(ringNodes.length, 2));
        ringNodes.forEach((node, index) => {
          const angle = angleOffset + ((Math.PI * 2 * index) / Math.max(ringNodes.length, 1));
          positions.set(node.id, {
            x: Math.cos(angle) * ringRadius,
            y: Math.sin(angle) * ringRadius,
          });
        });
      });
      radius += Math.max(1, rings.length) * RADIAL_RING_GAP + 48;
    });

    return positions;
  }

  function buildCyElements(graph) {
    const denseGraph = graphIsDense(graph);
    const showEdgeLabels = graph.links.length <= MAX_EDGE_LABELS;
    const expandedIds = new Set(state.expandedIds);
    const visibleDirectNodeIds = new Set(graph.meta.visibleDirectNodeIds || []);
    const visibleDirectRowIds = new Set(graph.meta.visibleDirectRowIds || []);
    const nodeElements = graph.nodes.map((node) => {
      const isCenter = node.id === graph.center.id;
      const isExpanded = expandedIds.has(node.id);
      const isDirectNeighbor = visibleDirectNodeIds.has(node.id);
      const depth = Number(graph.meta.depthMap?.[node.id] ?? (isCenter ? 0 : 1));
      const outsideLabel = denseGraph && !isCenter && !isDirectNeighbor;
      return {
        data: {
          id: node.id,
          name: node.name,
          labelText: denseGraph && !isCenter && !isExpanded ? shortDisplayName(node.name, 28) : node.name,
          iri: node.iri,
          qname: nodeQname(node),
          localName: node.localName || "",
          description: node.description || "",
          display_class: node.display_class || node.category,
          degree: Number(node.degree || 0),
          depth,
          modules: node.modules || [],
          fill: isCenter ? "#ca6d2c" : isExpanded ? "#1f7a7a" : node.color,
          borderColor: isExpanded && !isCenter ? "#10242d" : "rgba(16, 36, 45, 0.18)",
          borderWidth: isExpanded ? 2 : 1,
          size: isCenter
            ? 58
            : isExpanded
              ? (denseGraph ? 34 : 42)
              : Math.max(denseGraph ? 18 : 24, Math.min(denseGraph ? 30 : 40, Number(node.symbolSize || 18) + (denseGraph ? 4 : 8))),
          fontSize: isCenter ? 14 : isExpanded ? (denseGraph ? 10 : 11) : (denseGraph ? 9 : 11),
          textMaxWidth: isCenter ? 220 : denseGraph ? 118 : 150,
          textBackgroundOpacity: isCenter ? 0.92 : denseGraph ? 0.72 : 0.88,
        },
        classes: `${isCenter ? "center " : ""}${isExpanded ? "expanded " : ""}${isDirectNeighbor ? "direct-node " : "context-node "}${outsideLabel ? "outside-label" : ""}`.trim(),
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
        opacity: denseGraph
          ? (link.edgeFamily === "schema" ? 0.72 : 0.46)
          : 0.9,
        sourceLabel: graph.nodeMap.get(link.source)?.name || link.source,
        targetLabel: graph.nodeMap.get(link.target)?.name || link.target,
        isDirect: visibleDirectRowIds.has(linkKey(link)),
      },
      classes: `${showEdgeLabels ? "" : "no-label "}${denseGraph ? "dense-edge " : ""}${visibleDirectRowIds.has(linkKey(link)) ? "direct-edge" : "context-edge"}`.trim(),
    }));

    return [...nodeElements, ...edgeElements];
  }

  function runLayout(instance, graph) {
    if (!instance.nodes().length) return;
    if (graphIsDense(graph)) {
      const positions = radialPositions(graph);
      instance.layout({
        name: "preset",
        animate: false,
        fit: true,
        padding: graph.links.length > 90 ? 120 : 84,
        positions: (node) => positions.get(node.id()) || { x: 0, y: 0 },
      }).run();
    } else {
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
    }
    const centerNode = instance.getElementById(graph.center.id);
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
          <span class="visual-badge">${escapeHtml(String(node.degree || 0))} direct links</span>
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

  function renderDirectSummary(graph) {
    if (!directSummaryEl) return;
    if (!graph.center) {
      directSummaryEl.textContent = "Direct-neighborhood counts appear here after you select a term.";
      return;
    }
    const summary = graph.meta.directSummary;
    directSummaryEl.innerHTML = `
      <span><strong>${escapeHtml(String(summary.totalRowCount))}</strong> direct relations</span>
      <span><strong>${escapeHtml(String(summary.totalNeighborCount))}</strong> connected nodes</span>
      <span><strong>${escapeHtml(String(summary.visibleNeighborCount))}</strong> currently visible</span>
    `;
  }

  function renderNeighborPanel(graph) {
    if (!neighborSummaryEl || !classFiltersEl || !neighborGroupsEl) return;
    if (!graph.center) {
      neighborSummaryEl.innerHTML = '<div class="visual-empty">Select a term to review its full direct neighborhood and manage what is shown in the graph.</div>';
      classFiltersEl.innerHTML = "";
      neighborGroupsEl.innerHTML = '<div class="visual-empty">Connected nodes grouped by relation will appear here after you select a term.</div>';
      return;
    }

    const summary = graph.meta.directSummary;
    const visibleDirectRowIds = new Set(graph.meta.visibleDirectRowIds || []);
    const visibleDirectNodeIds = new Set(graph.meta.visibleDirectNodeIds || []);

    neighborSummaryEl.innerHTML = `
      <div class="visual-neighbor-summary__headline">
        <div>
          <strong>${escapeHtml(graph.center.name)}</strong>
          <small>${escapeHtml(graph.center.display_class || graph.center.category)}</small>
        </div>
        <span class="visual-chip">${escapeHtml(String(summary.visibleNeighborCount))} visible / ${escapeHtml(String(summary.totalNeighborCount))} total</span>
      </div>
      <div class="visual-neighbor-summary__stats">
        <span class="visual-chip">Direct relations ${escapeHtml(String(summary.totalRowCount))}</span>
        <span class="visual-chip">Connected nodes ${escapeHtml(String(summary.totalNeighborCount))}</span>
        <span class="visual-chip">Hidden nodes ${escapeHtml(String(summary.hiddenNeighborCount))}</span>
      </div>
    `;

    classFiltersEl.innerHTML = summary.classes.map((entry) => `
      <button
        type="button"
        class="visual-filter-chip ${state.hiddenClassKeys.has(entry.key) ? "" : "is-active"}"
        data-neighbor-class-key="${escapeHtml(entry.key)}"
        aria-pressed="${state.hiddenClassKeys.has(entry.key) ? "false" : "true"}"
      >
        <span>${escapeHtml(entry.label)}</span>
        <small>${escapeHtml(String(entry.visibleNodes))}/${escapeHtml(String(entry.totalNodes))}</small>
      </button>
    `).join("");

    if (!summary.groups.length) {
      neighborGroupsEl.innerHTML = '<div class="visual-empty">No direct neighbors remain under the current module and external-term filters.</div>';
      return;
    }

    neighborGroupsEl.innerHTML = summary.groups.map((group) => `
      <section class="visual-neighbor-group">
        <header class="visual-neighbor-group__head">
          <div>
            <strong><code>${escapeHtml(group.label)}</code></strong>
            <div class="visual-neighbor-group__meta">
              <span class="visual-chip">${escapeHtml(String(group.visibleNodes))}/${escapeHtml(String(group.totalNodes))} nodes visible</span>
              <span class="visual-chip">${escapeHtml(String(group.visibleRows))}/${escapeHtml(String(group.totalRows))} relations visible</span>
            </div>
          </div>
          <div class="visual-neighbor-group__actions">
            <button type="button" class="copy-button" data-neighbor-group-action="show" data-predicate-key="${escapeHtml(group.key)}">Show group</button>
            <button type="button" class="copy-button" data-neighbor-group-action="hide" data-predicate-key="${escapeHtml(group.key)}">Hide group</button>
          </div>
        </header>
        <div class="visual-neighbor-group__classes">
          ${group.classLabels.slice(0, 6).map((label) => `<span class="visual-chip">${escapeHtml(label)}</span>`).join("")}
        </div>
        <div class="visual-neighbor-group__rows">
          ${group.rows.map((row) => `
            <div class="visual-neighbor-row ${visibleDirectRowIds.has(row.id) ? "is-visible" : "is-hidden"}">
              <div class="visual-neighbor-row__body">
                <strong>${escapeHtml(row.neighbor.name)}</strong>
                <div class="visual-neighbor-row__meta">
                  <span class="visual-chip">${escapeHtml(row.neighborClassLabel)}</span>
                  <span class="visual-chip">${row.neighbor.local ? "Local" : "External"}</span>
                  ${row.neighbor.modules.map((moduleId) => `<span class="visual-chip">${escapeHtml(moduleId)}</span>`).join("")}
                </div>
                <small>${escapeHtml(visibleDirectNodeIds.has(row.neighborId) ? "Shown in graph." : "Hidden from graph by the current controls.")}</small>
              </div>
              <div class="visual-neighbor-row__actions">
                <button type="button" class="copy-button" data-neighbor-node-action="${visibleDirectNodeIds.has(row.neighborId) ? "hide" : "show"}" data-neighbor-id="${escapeHtml(row.neighborId)}">${visibleDirectNodeIds.has(row.neighborId) ? "Hide node" : "Show node"}</button>
                <button type="button" class="copy-button" data-neighbor-node-action="focus" data-neighbor-id="${escapeHtml(row.neighborId)}">Focus</button>
              </div>
            </div>
          `).join("")}
        </div>
      </section>
    `).join("");

    classFiltersEl.querySelectorAll("[data-neighbor-class-key]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          const key = button.dataset.neighborClassKey;
          if (state.hiddenClassKeys.has(key)) {
            state.hiddenClassKeys.delete(key);
          } else {
            state.hiddenClassKeys.add(key);
          }
        });
      });
    });

    neighborGroupsEl.querySelectorAll("[data-neighbor-group-action]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          const key = button.dataset.predicateKey;
          if (button.dataset.neighborGroupAction === "show") {
            state.hiddenPredicateKeys.delete(key);
          } else {
            state.hiddenPredicateKeys.add(key);
          }
        });
      });
    });

    neighborGroupsEl.querySelectorAll("[data-neighbor-node-action]").forEach((button) => {
      button.addEventListener("click", () => {
        runUndoable(() => {
          const nodeId = button.dataset.neighborId;
          if (button.dataset.neighborNodeAction === "focus") {
            state.hiddenDirectNodeIds.delete(nodeId);
            state.seedId = nodeId;
            selectNode(nodeId, { reset: false });
            return;
          }
          if (button.dataset.neighborNodeAction === "show") {
            state.hiddenDirectNodeIds.delete(nodeId);
            return;
          }
          state.hiddenDirectNodeIds.add(nodeId);
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
          <p>${escapeHtml(node.id === graph.center?.id ? "Current focus node." : "Visible through the current expanded neighborhood.")} ${escapeHtml(node.id === state.seedId ? "This is also the current search seed." : "")} Direct links: ${escapeHtml(String(node.degree || 0))}. Modules: ${escapeHtml(node.modules.join(", "))}.</p>
      </div>
      ${detailSections.join("")}
    `;
  }

  function renderRelations(graph) {
    const directIds = new Set(graph.meta.visibleDirectRowIds || []);
    const rows = graph.links
      .map((link) => ({
        source: graph.nodeMap.get(link.source)?.name || link.source,
        predicate: linkLabel(link),
        target: graph.nodeMap.get(link.target)?.name || link.target,
        edgeFamily: link.edgeFamily,
        module: link.module,
        scope: directIds.has(linkKey(link)) ? "Direct" : "Context",
      }))
      .sort((left, right) => {
        if (left.scope !== right.scope) return left.scope === "Direct" ? -1 : 1;
        const predicateOrder = left.predicate.localeCompare(right.predicate);
        if (predicateOrder !== 0) return predicateOrder;
        return left.target.localeCompare(right.target);
      });

    relationsEl.innerHTML = renderTable(
      [
        { label: "Scope", render: (row) => escapeHtml(row.scope) },
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
    const summary = graph.meta.directSummary;
    if (!graph.links.length) {
      graphNoteEl.textContent = "This term is loaded, but no visible relationships remain with the current module and external-term filters.";
      return;
    }
    if (!state.showExternalNeighbors && graph.meta.hiddenNeighborCount > 0) {
      graphNoteEl.textContent = `The connected-node panel lists the full direct neighborhood for ${graph.meta.selectionLabel}. The graph currently shows ${summary.visibleNeighborCount} direct node${summary.visibleNeighborCount === 1 ? "" : "s"} and ${graph.links.length} visible relation${graph.links.length === 1 ? "" : "s"}; ${graph.meta.hiddenNeighborCount} directly linked external relation${graph.meta.hiddenNeighborCount === 1 ? "" : "s"} are hidden because the external-term toggle is off.`;
      return;
    }
    graphNoteEl.textContent = `The connected-node panel lists the full direct neighborhood for ${graph.meta.selectionLabel}. The graph currently shows ${summary.visibleNeighborCount} direct node${summary.visibleNeighborCount === 1 ? "" : "s"} out of ${summary.totalNeighborCount}, plus any second-hop context revealed by expansion. Click any visible node to expand further or use Undo to step back.`;
  }

  function renderGraph(graph) {
    countNodesEl.textContent = String(graph.nodes.length);
    countEdgesEl.textContent = String(graph.links.length);
    countEdgesInlineEl.textContent = String(graph.links.length);
    countExpandedEl.textContent = String(graph.meta.expandedCount);
    renderDirectSummary(graph);
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
    runLayout(instance, graph);
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
    renderNeighborPanel(graph);
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
          resetDirectVisibilityState();
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
          resetDirectVisibilityState();
        });
      }
    });
  });
  root.querySelectorAll("[data-neighbor-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      runUndoable(() => {
        const action = button.dataset.neighborPreset;
        if (action === "show-all") {
          resetDirectVisibilityState();
          return;
        }
        if (action === "hide-all") {
          state.neighborVisibilityMode = "all";
          state.hiddenPredicateKeys = new Set();
          state.hiddenClassKeys = new Set();
          state.hiddenDirectNodeIds = new Set(
            (buildExpandedGraph(buildBaseView()).meta.directRows || []).map((row) => row.neighborId)
          );
          return;
        }
        if (action === "reset-direct" && state.selectedId) {
          state.expandedIds = new Set([state.selectedId]);
          resetDirectVisibilityState();
          return;
        }
        if (action === "local-only") {
          resetDirectVisibilityState();
          state.neighborVisibilityMode = "local";
          return;
        }
        if (action === "external-only") {
          resetDirectVisibilityState();
          state.neighborVisibilityMode = "external";
        }
      });
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
      if (directSummaryEl) directSummaryEl.textContent = error.message;
      if (neighborSummaryEl) neighborSummaryEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      if (classFiltersEl) classFiltersEl.innerHTML = "";
      if (neighborGroupsEl) neighborGroupsEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      inspectorEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      relationsEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      graphNoteEl.textContent = error.message;
      searchStatusEl.textContent = error.message;
    });
});
