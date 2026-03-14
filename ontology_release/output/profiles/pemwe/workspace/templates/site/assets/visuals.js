document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-visual-explorer]");
  if (!root) return;

  const dataPath = root.dataset.visualData;
  const graphPanel = root.querySelector('[data-visual-panel="graph"]');
  const searchPanel = root.querySelector('[data-visual-panel="search"]');
  const summaryPanel = root.querySelector('[data-visual-panel="summary"]');
  const triplesPanel = root.querySelector('[data-visual-panel="triples"]');
  const sourcePanel = root.querySelector('[data-visual-panel="source"]');
  const graphChartEl = root.querySelector('[data-visual-chart="graph"]');
  const searchChartEl = root.querySelector('[data-visual-chart="search"]');
  const summarySectionsEl = root.querySelector("[data-summary-sections]");
  const triplesTableEl = root.querySelector("[data-triples-table]");
  const matchesTableEl = root.querySelector("[data-search-matches]");
  const edgesTableEl = root.querySelector("[data-search-edges]");
  const inspectorEl = root.querySelector("[data-visual-inspector]");
  const sourceSelectEl = root.querySelector("[data-source-select]");
  const sourceStatusEl = root.querySelector("[data-source-status]");
  const sourceCodeEl = root.querySelector("[data-source-code]");
  const sourceDownloadEl = root.querySelector("[data-source-download]");
  const searchInputEl = root.querySelector("[data-visual-search]");
  const layoutSelectEl = root.querySelector("[data-visual-layout]");
  const maxNodesEl = root.querySelector("[data-search-max]");
  const countNodesEl = root.querySelector('[data-visual-count="nodes"]');
  const countEdgesEl = root.querySelector('[data-visual-count="edges"]');
  const countModulesEl = root.querySelector('[data-visual-count="modules"]');
  const tabs = Array.from(root.querySelectorAll("[data-visual-tab]"));
  const panels = {
    graph: graphPanel,
    search: searchPanel,
    summary: summaryPanel,
    triples: triplesPanel,
    source: sourcePanel,
  };

  let payload = null;
  let graphChart = null;
  let searchChart = null;

  const state = {
    hideExternal: true,
    includeBNodes: false,
    showSchemaEdges: true,
    showObjectPropertyEdges: true,
    showTypeEdges: false,
    includeNeighbors: true,
    includeLinksAmongResults: true,
    layout: "force",
    maxNodes: 400,
  };

  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const nodeMapFromPayload = () => new Map((payload?.nodes || []).map((node) => [node.id, node]));
  const activeModules = () => Array.from(root.querySelectorAll("[data-module-toggle]:checked")).map((input) => input.value);

  function renderLegend() {
    const legendSlots = root.querySelectorAll("[data-legend-item]");
    if (!payload) return;
    const styleMap = new Map(payload.categories.map((row) => [row.name, row.color]));
    legendSlots.forEach((slot) => {
      const name = slot.dataset.legendItem;
      const color = styleMap.get(name) || "#94a3b8";
      slot.innerHTML = `<span class="visual-legend__swatch" style="background:${escapeHtml(color)}"></span><span>${escapeHtml(name)}</span>`;
    });
  }

  function syncState() {
    state.layout = layoutSelectEl.value;
    state.maxNodes = Number(maxNodesEl.value) || 400;
    root.querySelectorAll("[data-visual-toggle]").forEach((input) => {
      state[input.dataset.visualToggle] = input.checked;
    });
    root.querySelectorAll("[data-search-toggle]").forEach((input) => {
      state[input.dataset.searchToggle] = input.checked;
    });
  }

  function nodeAllowed(node) {
    if (!state.includeBNodes && node.category === "BlankNode") return false;
    if (state.hideExternal && !node.local) return false;
    return true;
  }

  function edgeAllowed(link) {
    if (link.edgeFamily === "schema" && !state.showSchemaEdges) return false;
    if (link.edgeFamily === "object_property" && !state.showObjectPropertyEdges) return false;
    if (link.edgeFamily === "type" && !state.showTypeEdges) return false;
    return true;
  }

  function buildBaseView() {
    syncState();
    const selectedModules = new Set(activeModules());
    const nodes = payload.nodes || [];
    const seededIds = new Set();
    nodes.forEach((node) => {
      if (node.modules.some((moduleId) => selectedModules.has(moduleId))) {
        seededIds.add(node.id);
      }
    });
    let links = (payload.links || []).filter((link) => selectedModules.has(link.module) && edgeAllowed(link));
    links.forEach((link) => {
      seededIds.add(link.source);
      seededIds.add(link.target);
    });
    const filteredNodes = nodes.filter((node) => seededIds.has(node.id) && nodeAllowed(node));
    const allowedIds = new Set(filteredNodes.map((node) => node.id));
    return {
      nodes: filteredNodes,
      links: links.filter((link) => allowedIds.has(link.source) && allowedIds.has(link.target)),
      nodeMap: nodeMapFromPayload(),
      selectedModules: Array.from(selectedModules),
    };
  }

  function filterGraphByQuery(baseView, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) {
      return { nodes: [], links: [], matchedRows: [], edgeRows: [] };
    }
    const nodeById = new Map(baseView.nodes.map((node) => [node.id, node]));
    const matches = (node) => {
      const haystack = [node.name, node.id, node.value, node.description, node.qname].join(" ").toLowerCase();
      return haystack.includes(q);
    };
    const matchedIds = new Set(baseView.nodes.filter(matches).map((node) => node.id));
    if (!matchedIds.size) {
      return { nodes: [], links: [], matchedRows: [], edgeRows: [] };
    }

    const keepIds = new Set(matchedIds);
    const keptLinks = [];
    baseView.links.forEach((link) => {
      if (matchedIds.has(link.source) || matchedIds.has(link.target)) {
        keptLinks.push(link);
        if (state.includeNeighbors) {
          keepIds.add(link.source);
          keepIds.add(link.target);
        }
      }
    });
    if (state.includeLinksAmongResults) {
      baseView.links.forEach((link) => {
        if (keepIds.has(link.source) && keepIds.has(link.target)) {
          keptLinks.push(link);
        }
      });
    }

    const uniqueLinks = [];
    const seenLinks = new Set();
    keptLinks.forEach((link) => {
      const key = `${link.source}|${link.predicate}|${link.target}|${link.module}|${link.edgeFamily}`;
      if (seenLinks.has(key)) return;
      seenLinks.add(key);
      uniqueLinks.push(link);
    });

    let orderedIds = Array.from(keepIds);
    if (orderedIds.length > state.maxNodes) {
      const prioritized = [...matchedIds, ...orderedIds.filter((id) => !matchedIds.has(id))];
      orderedIds = prioritized.slice(0, state.maxNodes);
    }
    const limitedIds = new Set(orderedIds);
    const filteredNodes = orderedIds.map((id) => nodeById.get(id)).filter(Boolean);
    const filteredLinks = uniqueLinks.filter((link) => limitedIds.has(link.source) && limitedIds.has(link.target));
    return {
      nodes: filteredNodes,
      links: filteredLinks,
      matchedRows: Array.from(matchedIds)
        .map((id) => nodeById.get(id))
        .filter(Boolean)
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((node) => ({
          label: node.name,
          iri: node.iri,
          category: node.category,
          modules: node.modules.join(", "),
        })),
      edgeRows: filteredLinks.map((link) => ({
        source: nodeById.get(link.source)?.name || link.source,
        predicate: link.value,
        target: nodeById.get(link.target)?.name || link.target,
        module: link.module,
      })),
    };
  }

  function chartOption(nodes, links, title, subtitle) {
    const categoryIndex = new Map(payload.categories.map((category, index) => [category.name, index]));
    const showLabels = nodes.length <= 110;
    const showEdgeLabels = links.length <= 160;
    return {
      title: {
        text: title,
        subtext: subtitle,
        left: "center",
        top: 14,
        textStyle: {
          fontFamily: "Iowan Old Style, Palatino Linotype, Georgia, serif",
          fontSize: 24,
          color: "#0e1a21",
          fontWeight: 700,
        },
        subtextStyle: { color: "#56636c", fontSize: 12 },
      },
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(12, 26, 35, 0.96)",
        borderColor: "rgba(255, 255, 255, 0.12)",
        textStyle: { color: "#eef8f7" },
        formatter: (params) => {
          if (params.dataType === "edge") {
            const data = params.data;
            return `<strong>${escapeHtml(data.value || data.predicate)}</strong><br>${escapeHtml(data.source)} → ${escapeHtml(data.target)}<br>Module: ${escapeHtml(data.module)}`;
          }
          const data = params.data;
          return `<strong>${escapeHtml(data.name)}</strong><br>${escapeHtml(data.category)}<br><code>${escapeHtml(data.iri)}</code>`;
        },
      },
      legend: [{
        data: payload.categories.map((category) => category.name),
        orient: "vertical",
        left: 10,
        top: 70,
        itemGap: 14,
        textStyle: { color: "#56636c" },
      }],
      animationDurationUpdate: 900,
      animationEasingUpdate: "quarticOut",
      series: [{
        type: "graph",
        layout: state.layout,
        roam: true,
        draggable: true,
        focusNodeAdjacency: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [4, 10],
        data: nodes.map((node) => ({
          ...node,
          category: categoryIndex.get(node.category) ?? 0,
          symbolSize: node.symbolSize,
          itemStyle: { color: node.color, shadowBlur: 12, shadowColor: "rgba(14, 26, 33, 0.14)" },
          label: { show: showLabels, formatter: node.name, color: "#10242d", fontSize: 11 },
        })),
        links: links.map((link) => ({
          ...link,
          lineStyle: {
            width: link.edgeFamily === "object_property" ? 1.4 : 1.8,
            opacity: 0.86,
            curveness: link.edgeFamily === "type" ? 0.08 : 0.16,
            color: link.edgeFamily === "object_property" ? "#1f7a7a" : link.edgeFamily === "schema" ? "#ca6d2c" : "#64748b",
          },
        })),
        categories: payload.categories.map((category) => ({ name: category.name, itemStyle: { color: category.color } })),
        force: { repulsion: 220, edgeLength: [90, 180], gravity: 0.06, friction: 0.22 },
        circular: { rotateLabel: true },
        lineStyle: { opacity: 0.86 },
        edgeLabel: {
          show: showEdgeLabels,
          formatter: (params) => params.data.value,
          backgroundColor: "rgba(255, 255, 255, 0.86)",
          borderRadius: 4,
          padding: [2, 4, 2, 4],
          color: "#243a44",
          fontSize: 10,
        },
        emphasis: { focus: "adjacency", lineStyle: { width: 3 } },
      }],
    };
  }

  function ensureChart(chart, element) {
    if (chart) return chart;
    return echarts.init(element, null, { renderer: "canvas" });
  }

  function renderTable(headers, rows, emptyMessage) {
    if (!rows.length) {
      return `<div class="visual-empty">${escapeHtml(emptyMessage)}</div>`;
    }
    const headerHtml = headers.map((header) => `<th>${escapeHtml(header.label)}</th>`).join("");
    const rowHtml = rows.map((row) => `<tr>${headers.map((header) => `<td>${header.render(row)}</td>`).join("")}</tr>`).join("");
    return `<table class="data-table"><thead><tr>${headerHtml}</tr></thead><tbody>${rowHtml}</tbody></table>`;
  }

  function showInspector(node, baseView) {
    if (!node) {
      inspectorEl.innerHTML = '<div class="visual-empty">Click a node in the graph to inspect its label, IRI, module membership, description, and local neighborhood.</div>';
      return;
    }
    const relatedLinks = baseView.links.filter((link) => link.source === node.id || link.target === node.id).slice(0, 8);
    const relationRows = relatedLinks.length
      ? `<div class="visual-inspector__section"><strong>Visible relations</strong><ul class="simple-list">${relatedLinks.map((link) => {
          const sourceLabel = baseView.nodeMap.get(link.source)?.name || link.source;
          const targetLabel = baseView.nodeMap.get(link.target)?.name || link.target;
          return `<li><code>${escapeHtml(link.value)}</code>: ${escapeHtml(sourceLabel)} → ${escapeHtml(targetLabel)}</li>`;
        }).join("")}</ul></div>`
      : "";
    inspectorEl.innerHTML = `
      <div>
        <h3>${escapeHtml(node.name)}</h3>
        <div class="visual-inspector__meta">
          <span class="visual-chip">${escapeHtml(node.category)}</span>
          <span class="visual-chip">${node.local ? "Local" : "External"}</span>
          ${node.modules.map((moduleId) => `<span class="visual-chip">${escapeHtml(moduleId)}</span>`).join("")}
        </div>
      </div>
      <div class="visual-inspector__section">
        <strong>IRI</strong>
        <p><a href="${escapeHtml(node.iri)}"><code>${escapeHtml(node.iri)}</code></a></p>
      </div>
      <div class="visual-inspector__section">
        <strong>Description</strong>
        <p>${escapeHtml(node.description)}</p>
      </div>
      <div class="visual-inspector__section">
        <strong>QName / local form</strong>
        <p><code>${escapeHtml(node.qname)}</code></p>
      </div>
      ${relationRows}
    `;
  }

  function bindInspector(chart, baseView) {
    chart.off("click");
    chart.on("click", (params) => {
      if (params.dataType !== "node") return;
      showInspector(params.data, baseView);
    });
  }

  function renderCounts(baseView) {
    countNodesEl.textContent = String(baseView.nodes.length);
    countEdgesEl.textContent = String(baseView.links.length);
    countModulesEl.textContent = String(baseView.selectedModules.length);
  }

  function renderGraph(baseView) {
    if (graphPanel.hidden || graphChartEl.clientWidth <= 0) return;
    if (!baseView.nodes.length || !baseView.links.length) {
      graphChartEl.innerHTML = '<div class="visual-empty">No nodes or edges are available with the current filters. Try enabling more modules or turning off the external-vocabulary filter.</div>';
      if (graphChart) {
        graphChart.dispose();
        graphChart = null;
      }
      showInspector(null, baseView);
      return;
    }
    graphChartEl.innerHTML = "";
    graphChart = ensureChart(graphChart, graphChartEl);
    graphChart.setOption(chartOption(baseView.nodes, baseView.links, "Ontology graph", "Module-aware view of the current published release"), true);
    bindInspector(graphChart, baseView);
  }

  function renderSearch(baseView) {
    const result = filterGraphByQuery(baseView, searchInputEl.value);
    if (!searchPanel.hidden && searchChartEl.clientWidth > 0) {
      if (!searchInputEl.value.trim()) {
        searchChartEl.innerHTML = '<div class="visual-empty">Type a term to build a filtered search graph from the currently selected modules.</div>';
        if (searchChart) {
          searchChart.dispose();
          searchChart = null;
        }
      } else if (!result.nodes.length) {
        searchChartEl.innerHTML = '<div class="visual-empty">No matches found for the current query. Try a broader term or loosen the filters.</div>';
        if (searchChart) {
          searchChart.dispose();
          searchChart = null;
        }
      } else {
        searchChartEl.innerHTML = "";
        searchChart = ensureChart(searchChart, searchChartEl);
        searchChart.setOption(chartOption(result.nodes, result.links, `Search view: ${searchInputEl.value.trim()}`, "Matched terms plus optional one-hop context"), true);
        bindInspector(searchChart, {
          ...baseView,
          nodes: result.nodes,
          links: result.links,
          nodeMap: new Map(result.nodes.map((node) => [node.id, node])),
        });
      }
    }
    matchesTableEl.innerHTML = renderTable(
      [
        { label: "Label", render: (row) => escapeHtml(row.label) },
        { label: "IRI", render: (row) => `<code>${escapeHtml(row.iri)}</code>` },
        { label: "Category", render: (row) => escapeHtml(row.category) },
        { label: "Modules", render: (row) => escapeHtml(row.modules) },
      ],
      result.matchedRows,
      "No matched nodes yet."
    );
    edgesTableEl.innerHTML = renderTable(
      [
        { label: "Source", render: (row) => escapeHtml(row.source) },
        { label: "Predicate", render: (row) => `<code>${escapeHtml(row.predicate)}</code>` },
        { label: "Target", render: (row) => escapeHtml(row.target) },
        { label: "Module", render: (row) => escapeHtml(row.module) },
      ],
      result.edgeRows,
      "No visible edges in the current search view."
    );
  }

  function renderSummary(baseView) {
    const sections = [
      { key: "Class", title: "Classes" },
      { key: "ObjectProperty", title: "Object properties" },
      { key: "DatatypeProperty", title: "Datatype properties" },
      { key: "AnnotationProperty", title: "Annotation properties" },
      { key: "Individual", title: "Individuals and controlled terms" },
    ];
    summarySectionsEl.innerHTML = sections.map((section) => {
      const rows = baseView.nodes
        .filter((node) => node.category === section.key)
        .sort((a, b) => a.name.localeCompare(b.name));
      return `
        <section class="visual-table-section">
          <div class="visual-section-heading">
            <div>
              <h3>${escapeHtml(section.title)}</h3>
              <p>${rows.length} rows in the current filtered view.</p>
            </div>
          </div>
          <div class="visual-table-shell">
            ${renderTable(
              [
                { label: "Label", render: (row) => escapeHtml(row.name) },
                { label: "IRI", render: (row) => `<code>${escapeHtml(row.iri)}</code>` },
                { label: "Scope", render: (row) => escapeHtml(row.local ? "Local" : "External") },
                { label: "Modules", render: (row) => escapeHtml(row.modules.join(", ")) },
                { label: "Description", render: (row) => escapeHtml(row.description) },
              ],
              rows,
              `No ${section.title.toLowerCase()} are visible with the current filters.`
            )}
          </div>
        </section>
      `;
    }).join("");
  }

  function renderTriples(baseView) {
    const allowedModules = new Set(baseView.selectedModules);
    const rows = (payload.triples || []).filter((row) => allowedModules.has(row.module)).slice(0, 320);
    triplesTableEl.innerHTML = renderTable(
      [
        { label: "Module", render: (row) => escapeHtml(row.module) },
        { label: "Subject", render: (row) => `<code>${escapeHtml(row.subject_label)}</code>` },
        { label: "Predicate", render: (row) => `<code>${escapeHtml(row.predicate_label)}</code>` },
        { label: "Object", render: (row) => row.object_is_literal ? escapeHtml(row.object) : `<code>${escapeHtml(row.object_label)}</code>` },
      ],
      rows,
      "No triples are available for the selected modules."
    );
  }

  async function fetchFirstAvailable(urls) {
    for (const url of urls) {
      if (!url) continue;
      try {
        const response = await fetch(url);
        if (response.ok) {
          return { text: await response.text(), url };
        }
      } catch (error) {
      }
    }
    throw new Error("Unable to load module source from the available publication paths.");
  }

  async function renderSource() {
    if (!payload) return;
    const modules = payload.modules || [];
    const preferred = sourceSelectEl.value || activeModules()[0] || modules[0]?.id;
    const module = modules.find((row) => row.id === preferred) || modules[0];
    if (!module) {
      sourceStatusEl.textContent = "No source modules are available.";
      sourceCodeEl.textContent = "";
      return;
    }
    sourceSelectEl.value = module.id;
    sourceDownloadEl.href = module.path || "#";
    sourceStatusEl.textContent = `Loading ${module.label}...`;
    try {
      const loaded = await fetchFirstAvailable([module.path, module.fallback]);
      sourceStatusEl.innerHTML = `Showing <strong>${escapeHtml(module.label)}</strong> from <code>${escapeHtml(loaded.url)}</code>.`;
      sourceCodeEl.textContent = loaded.text;
    } catch (error) {
      sourceStatusEl.textContent = "Source preview is unavailable from this page context. Use the deployed Pages URL or a local static HTTP server.";
      sourceCodeEl.textContent = "";
    }
  }

  function setActiveTab(tabId) {
    tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.visualTab === tabId));
    Object.entries(panels).forEach(([key, panel]) => {
      panel.hidden = key !== tabId;
    });
    requestAnimationFrame(() => {
      if (graphChart) graphChart.resize();
      if (searchChart) searchChart.resize();
      renderAll();
    });
  }

  function renderAll() {
    if (!payload) return;
    const baseView = buildBaseView();
    renderCounts(baseView);
    renderGraph(baseView);
    renderSearch(baseView);
    renderSummary(baseView);
    renderTriples(baseView);
    if (!sourcePanel.hidden) {
      renderSource();
    }
  }

  root.querySelectorAll("[data-module-toggle], [data-visual-toggle], [data-search-toggle]").forEach((input) => {
    input.addEventListener("change", renderAll);
  });
  layoutSelectEl.addEventListener("change", renderAll);
  maxNodesEl.addEventListener("input", renderAll);
  searchInputEl.addEventListener("input", renderAll);
  sourceSelectEl.addEventListener("change", () => {
    if (payload) renderSource();
  });
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActiveTab(tab.dataset.visualTab));
  });
  window.addEventListener("resize", () => {
    if (graphChart) graphChart.resize();
    if (searchChart) searchChart.resize();
  });

  fetch(dataPath)
    .then((response) => {
      if (!response.ok) throw new Error(`Failed to load explorer data from ${dataPath}`);
      return response.json();
    })
    .then((json) => {
      payload = json;
      renderLegend();
      const defaultSource = (payload.modules || []).find((module) => module.default) || (payload.modules || [])[0];
      if (defaultSource) {
        sourceSelectEl.value = defaultSource.id;
      }
      renderAll();
    })
    .catch((error) => {
      const message = escapeHtml(error.message);
      graphChartEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      searchChartEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      summarySectionsEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      triplesTableEl.innerHTML = `<div class="visual-empty">${message}</div>`;
      sourceStatusEl.textContent = error.message;
      sourceCodeEl.textContent = "";
    });
});
