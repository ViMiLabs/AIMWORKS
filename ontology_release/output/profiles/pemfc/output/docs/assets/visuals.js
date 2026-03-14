document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-visual-explorer]");
  if (!root) return;

  const dataPath = root.dataset.visualData;
  const chartEl = root.querySelector('[data-visual-chart="term"]');
  const searchInputEl = root.querySelector("[data-visual-search]");
  const resultsEl = root.querySelector("[data-search-results]");
  const inspectorEl = root.querySelector("[data-visual-inspector]");
  const relationsEl = root.querySelector("[data-visual-relations]");
  const countNodesEl = root.querySelector('[data-visual-count="nodes"]');
  const countEdgesEl = root.querySelector('[data-visual-count="edges"]');
  const countEdgesInlineEl = root.querySelector('[data-visual-count="edges-inline"]');
  const countModulesEl = root.querySelector('[data-visual-count="modules"]');
  const countResultsEl = root.querySelector('[data-visual-count="results"]');

  let payload = null;
  let chart = null;

  const state = {
    selectedId: null,
    showExternalNeighbors: false,
  };

  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const normalize = (value) => String(value || "").trim().toLowerCase();
  const activeModules = () => Array.from(root.querySelectorAll("[data-module-toggle]:checked")).map((input) => input.value);

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
    return {
      nodes,
      links,
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
    const qname = normalize(node.qname);
    const iri = normalize(node.iri);
    const details = normalize(node.search_text || node.description || "");
    let score = 0;

    if (label === q || qname === q) score += 120;
    if (label.startsWith(q) || qname.startsWith(q)) score += 80;
    if (label.includes(q) || qname.includes(q)) score += 55;
    if (iri.includes(q)) score += 35;
    if (details.includes(q)) score += 20;
    if (normalize(node.display_class).includes(q)) score += 12;
    if (node.local) score += 8;

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
      .slice(0, 16)
      .map((row) => row.node);
  }

  function buildNeighborhood(view, seedId) {
    const seed = view.nodeMap.get(seedId);
    if (!seed) {
      return { seed: null, nodes: [], links: [], nodeMap: new Map() };
    }

    let links = view.links.filter((link) => link.source === seedId || link.target === seedId);
    if (!state.showExternalNeighbors) {
      links = links.filter((link) => {
        const neighborId = link.source === seedId ? link.target : link.source;
        const neighbor = view.nodeMap.get(neighborId);
        return !neighbor || neighbor.local || neighbor.id === seedId;
      });
    }

    const nodeIds = new Set([seedId]);
    links.forEach((link) => {
      nodeIds.add(link.source);
      nodeIds.add(link.target);
    });

    const nodes = Array.from(nodeIds)
      .map((id) => view.nodeMap.get(id))
      .filter(Boolean)
      .sort((left, right) => {
        if (left.id === seedId) return -1;
        if (right.id === seedId) return 1;
        return left.name.localeCompare(right.name);
      });
    const nodeMap = new Map(nodes.map((node) => [node.id, node]));

    return {
      seed,
      nodes,
      links: links.filter((link) => nodeMap.has(link.source) && nodeMap.has(link.target)),
      nodeMap,
    };
  }

  function chartOption(graph) {
    const categoryIndex = new Map((payload.categories || []).map((category, index) => [category.name, index]));
    const showEdgeLabels = graph.links.length <= 16;
    return {
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(12, 26, 35, 0.96)",
        borderColor: "rgba(255, 255, 255, 0.12)",
        textStyle: { color: "#eef8f7" },
        formatter: (params) => {
          if (params.dataType === "edge") {
            const data = params.data;
            return `<strong>${escapeHtml(data.value || data.predicate)}</strong><br>${escapeHtml(data.sourceLabel)} -> ${escapeHtml(data.targetLabel)}`;
          }
          const data = params.data;
          return `<strong>${escapeHtml(data.name)}</strong><br>${escapeHtml(data.display_class || data.category)}<br><code>${escapeHtml(data.iri)}</code>`;
        },
      },
      animationDurationUpdate: 700,
      animationEasingUpdate: "quarticOut",
      series: [{
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        focusNodeAdjacency: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [4, 10],
        data: graph.nodes.map((node) => ({
          ...node,
          category: categoryIndex.get(node.category) ?? 0,
          symbolSize: node.id === graph.seed.id ? 34 : Math.max(16, Number(node.symbolSize || 18)),
          itemStyle: {
            color: node.id === graph.seed.id ? "#ca6d2c" : node.color,
            shadowBlur: node.id === graph.seed.id ? 20 : 12,
            shadowColor: "rgba(14, 26, 33, 0.16)",
          },
          label: {
            show: true,
            formatter: node.name,
            color: "#10242d",
            fontSize: node.id === graph.seed.id ? 13 : 11,
          },
        })),
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
          repulsion: 260,
          edgeLength: [110, 180],
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

  function renderResults(rows) {
    countResultsEl.textContent = String(rows.length);
    if (!rows.length) {
      resultsEl.innerHTML = '<div class="visual-empty">No local terms match the current search.</div>';
      return;
    }

    resultsEl.innerHTML = rows.map((node) => `
      <button class="visual-result ${node.id === state.selectedId ? "is-active" : ""}" type="button" data-result-id="${escapeHtml(node.id)}">
        <strong>${escapeHtml(node.name)}</strong>
        <small>${escapeHtml(node.display_class || node.category)}</small>
        <div class="visual-result__meta">
          <span class="visual-badge">${escapeHtml(node.modules.join(", "))}</span>
          <span class="visual-badge">${escapeHtml(node.qname || node.iri)}</span>
        </div>
      </button>
    `).join("");

    resultsEl.querySelectorAll("[data-result-id]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedId = button.dataset.resultId;
        renderAll();
      });
    });
  }

  function renderInspector(node) {
    if (!node) {
      inspectorEl.innerHTML = '<div class="visual-empty">Select a search result to inspect its label, class, units, mappings, and release metadata.</div>';
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
        <strong>QName / local form</strong>
        <p><code>${escapeHtml(node.qname)}</code></p>
      </div>
      <div class="visual-inspector__section">
        <strong>Definition</strong>
        <p>${escapeHtml(node.description || "No definition or comment recorded.")}</p>
      </div>
      <div class="visual-inspector__section">
        <strong>Source modules</strong>
        <p>${escapeHtml(node.modules.join(", "))}</p>
      </div>
      ${detailSections.join("")}
    `;
  }

  function renderRelations(graph) {
    const rows = graph.links.map((link) => ({
      source: graph.nodeMap.get(link.source)?.name || link.source,
      predicate: link.value,
      target: graph.nodeMap.get(link.target)?.name || link.target,
      module: link.module,
    }));

    relationsEl.innerHTML = renderTable(
      [
        { label: "Source", render: (row) => escapeHtml(row.source) },
        { label: "Predicate", render: (row) => `<code>${escapeHtml(row.predicate)}</code>` },
        { label: "Target", render: (row) => escapeHtml(row.target) },
        { label: "Module", render: (row) => escapeHtml(row.module) },
      ],
      rows,
      "Visible relations will appear here after you select a term."
    );
  }

  function renderGraph(graph) {
    countNodesEl.textContent = String(graph.nodes.length);
    countEdgesEl.textContent = String(graph.links.length);
    countEdgesInlineEl.textContent = String(graph.links.length);

    if (!graph.seed) {
      chartEl.innerHTML = '<div class="visual-empty">Search for a local term to render its one-hop neighborhood.</div>';
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
      renderInspector(params.data);
    });
  }

  function renderAll() {
    if (!payload) return;

    const view = buildBaseView();
    countModulesEl.textContent = String(view.selectedModules.length);

    const results = searchResults(view, searchInputEl.value);
    const resultIds = new Set(results.map((node) => node.id));
    if (!resultIds.has(state.selectedId)) {
      state.selectedId = results[0]?.id || null;
    }

    renderResults(results);
    const graph = buildNeighborhood(view, state.selectedId);
    renderGraph(graph);
    renderInspector(graph.seed);
    renderRelations(graph);
  }

  root.querySelectorAll("[data-module-toggle], [data-visual-toggle]").forEach((input) => {
    input.addEventListener("change", renderAll);
  });
  searchInputEl.addEventListener("input", renderAll);
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
      inspectorEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      relationsEl.innerHTML = `<div class="visual-empty">${message}</div>`;
    });
});
