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

  let payload = null;
  let chart = null;
  let currentSuggestions = [];

  const state = {
    selectedId: null,
    showExternalNeighbors: false,
    expandedIds: new Set(),
    trail: [],
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

  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const normalize = (value) => String(value || "").trim().toLowerCase();
  const stripKey = (value) => normalize(value).replace(/[^a-z0-9]+/g, "");
  const activeModules = () => Array.from(root.querySelectorAll("[data-module-toggle]:checked")).map((input) => input.value);

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

  function syncState() {
    root.querySelectorAll("[data-visual-toggle]").forEach((input) => {
      state[input.dataset.visualToggle] = input.checked;
    });
  }

  function ensureChart() {
    if (chart) return chart;
    chart = echarts.init(chartEl, null, { renderer: "canvas" });
    return chart;
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

  function searchCandidates(view) {
    return view.nodes.filter((node) => node.local && node.category !== "Ontology");
  }

  function scoreNode(node, query) {
    const q = normalize(query);
    if (!q) return 0;

    const label = normalize(node.name);
    const localName = normalize(node.localName || "");
    const qname = normalize(node.qname);
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
    score += Math.max(...tokens.map((token) => fuzzyBonus(q, token)), 0);
    score += Math.min(Number(node.degree || 0), 120) / 30;

    return score;
  }

  function searchResults(view, query) {
    const q = normalize(query);
    if (!q) return [];
    return searchCandidates(view)
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
    const candidates = searchCandidates(view);
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

  function chartOption(graph) {
    const categoryIndex = new Map((payload.categories || []).map((category, index) => [category.name, index]));
    const expandedIds = new Set(state.expandedIds);
    const showEdgeLabels = graph.links.length <= 20;
    return {
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(12, 26, 35, 0.96)",
        borderColor: "rgba(255, 255, 255, 0.12)",
        textStyle: { color: "#eef8f7" },
        formatter: (params) => {
          if (params.dataType === "edge") {
            const data = params.data;
            return `<strong>${escapeHtml(data.value || data.predicate)}</strong><br>${escapeHtml(data.sourceLabel)} -> ${escapeHtml(data.targetLabel)}<br>Module: ${escapeHtml(data.module)}`;
          }
          const data = params.data;
          return `<strong>${escapeHtml(data.name)}</strong><br>${escapeHtml(data.display_class || data.category)}<br><code>${escapeHtml(data.iri)}</code><br>Degree: ${escapeHtml(data.degree || 0)}`;
        },
      },
      animationDurationUpdate: 650,
      animationEasingUpdate: "quarticOut",
      series: [{
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        focusNodeAdjacency: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [4, 10],
        data: graph.nodes.map((node) => {
          const isCenter = node.id === graph.center.id;
          const isExpanded = expandedIds.has(node.id);
          return {
            ...node,
            category: categoryIndex.get(node.category) ?? 0,
            symbolSize: isCenter ? 40 : isExpanded ? 30 : Math.max(16, Number(node.symbolSize || 18)),
            itemStyle: {
              color: isCenter ? "#ca6d2c" : isExpanded ? "#1f7a7a" : node.color,
              shadowBlur: isCenter ? 22 : 12,
              shadowColor: "rgba(14, 26, 33, 0.18)",
              borderWidth: isExpanded && !isCenter ? 2 : 0,
              borderColor: isExpanded && !isCenter ? "rgba(14, 26, 33, 0.24)" : "transparent",
            },
            label: {
              show: true,
              formatter: node.name,
              color: "#10242d",
              fontSize: isCenter ? 14 : 11,
            },
          };
        }),
        links: graph.links.map((link) => ({
          ...link,
          sourceLabel: graph.nodeMap.get(link.source)?.name || link.source,
          targetLabel: graph.nodeMap.get(link.target)?.name || link.target,
          lineStyle: {
            width: link.edgeFamily === "schema" ? 2 : 1.6,
            opacity: 0.88,
            curveness: 0.12,
            color: link.edgeFamily === "schema" ? "#ca6d2c" : link.edgeFamily === "object_property" ? "#1f7a7a" : "#64748b",
          },
        })),
        categories: (payload.categories || []).map((category) => ({ name: category.name, itemStyle: { color: category.color } })),
        force: {
          repulsion: 280,
          edgeLength: [105, 185],
          gravity: 0.08,
          friction: 0.2,
        },
        edgeLabel: {
          show: showEdgeLabels,
          formatter: (params) => params.data.value,
          backgroundColor: "rgba(255, 255, 255, 0.88)",
          borderRadius: 4,
          padding: [2, 4, 2, 4],
          color: "#243a44",
          fontSize: 10,
        },
        emphasis: { focus: "adjacency", lineStyle: { width: 3 } },
      }],
    };
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
      searchStatusEl.textContent = "Suggested starting points based on core classes and well-connected local terms.";
      return;
    }
    searchStatusEl.textContent = `${rows.length} ranked suggestion${rows.length === 1 ? "" : "s"} for "${query.trim()}".`;
  }

  function renderResults(rows, mode) {
    currentSuggestions = rows;
    if (!rows.length) {
      const emptyMessage = mode === "starter"
        ? "No starting points are available with the current module filters."
        : "No local terms match the current search.";
      resultsEl.innerHTML = `<div class="visual-empty">${escapeHtml(emptyMessage)}</div>`;
      return;
    }

    resultsEl.innerHTML = rows.map((node) => `
      <button class="visual-result ${node.id === state.selectedId ? "is-active" : ""} ${rows.indexOf(node) === state.highlightedIndex ? "is-highlighted" : ""}" type="button" data-result-id="${escapeHtml(node.id)}">
        <strong>${escapeHtml(node.name)}</strong>
        <small>${escapeHtml(node.display_class || node.category)}</small>
        <div class="visual-result__meta">
          <span class="visual-badge">${escapeHtml(node.localName || node.qname || node.iri)}</span>
          <span class="visual-badge">${escapeHtml(String(node.degree || 0))} links</span>
        </div>
        <small>${escapeHtml(snippet(node.description || ""))}</small>
      </button>
    `).join("");

    resultsEl.querySelectorAll("[data-result-id]").forEach((button) => {
      button.addEventListener("click", () => {
        selectNode(button.dataset.resultId, { reset: true });
        renderAll();
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
        selectNode(button.dataset.trailId, { reset: false });
        renderAll();
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
        <p><code>${escapeHtml(node.localName || node.qname)}</code></p>
      </div>
      <div class="visual-inspector__section">
        <strong>Definition</strong>
        <p>${escapeHtml(node.description || "No definition or comment recorded.")}</p>
      </div>
      <div class="visual-inspector__section">
        <strong>Explorer status</strong>
        <p>${escapeHtml(node.id === graph.center?.id ? "Current focus node." : "Visible through the current expanded neighborhood.")} Degree: ${escapeHtml(String(node.degree || 0))}. Modules: ${escapeHtml(node.modules.join(", "))}.</p>
      </div>
      ${detailSections.join("")}
    `;
  }

  function renderRelations(graph) {
    const rows = graph.links.map((link) => ({
      source: graph.nodeMap.get(link.source)?.name || link.source,
      predicate: link.value,
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
      graphNoteEl.textContent = "Search for a local term or use a starting point to initialize the explorer.";
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
      chartEl.innerHTML = '<div class="visual-empty">Search for a local term or choose a starting point to render the ontology graph.</div>';
      if (chart) {
        chart.dispose();
        chart = null;
      }
      return;
    }

    chartEl.innerHTML = "";
    const instance = ensureChart();
    instance.setOption(chartOption(graph), true);
    instance.off("click");
    instance.on("click", (params) => {
      if (params.dataType !== "node") return;
      selectNode(params.data.id, { reset: false });
      renderAll();
    });
  }

  function currentSuggestionMode(query) {
    return normalize(query) ? "search" : "starter";
  }

  function currentSuggestionsForView(view, query) {
    return currentSuggestionMode(query) === "search"
      ? searchResults(view, query)
      : starterSuggestions(view);
  }

  function syncSelection(view, suggestions, mode) {
    if (!view.nodeMap.size) {
      state.selectedId = null;
      state.expandedIds = new Set();
      return;
    }
    if (!state.selectedId || !view.nodeMap.has(state.selectedId)) {
      const fallbackId = suggestions[0]?.id || Array.from(view.nodeMap.keys())[0];
      if (fallbackId) {
        selectNode(fallbackId, { reset: true });
      }
      return;
    }
    if (mode === "search" && !suggestions.some((node) => node.id === state.selectedId)) {
      const fallbackId = suggestions[0]?.id;
      if (fallbackId) {
        selectNode(fallbackId, { reset: true });
      }
    }
  }

  function renderAll() {
    if (!payload) return;

    const view = buildBaseView();
    countModulesEl.textContent = String(view.selectedModules.length);

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
      if (button.dataset.visualAction === "reset" && state.selectedId) {
        state.expandedIds = new Set([state.selectedId]);
        renderAll();
      }
      if (button.dataset.visualAction === "clear") {
        searchInputEl.value = "";
        state.selectedId = null;
        state.expandedIds = new Set();
        state.trail = [];
        state.highlightedIndex = 0;
        renderAll();
      }
    });
  });
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
        selectNode(target.id, { reset: true });
        renderAll();
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
    if (chart) chart.resize();
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
      chartEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      resultsEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      trailEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      inspectorEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      relationsEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      graphNoteEl.textContent = error.message;
      searchStatusEl.textContent = error.message;
    });
});
