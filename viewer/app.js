// Prophecy Viewer — pure browser client over the static export bundle.
//
// Data layout it expects (relative to this page):
//   data/index.json          -- manifest from `prophecy export`
//   data/prompts.json
//   data/stories.json
//   data/results/<Book>.jsonl
//
// Override the root with ?data=<url> for local testing.

const params = new URLSearchParams(window.location.search);
const DATA_ROOT = (params.get("data") || "data").replace(/\/$/, "");

const state = {
  manifest: null,
  prompts: [],
  stories: {},
  labels: [],            // flat list from data/labels.json (empty if not bundled)
  shardCache: new Map(), // book -> rows[]

  // Labels tab UI state
  labelsBookSelected: null,         // book whose view is shown in the right pane
  labelsBookExpanded: new Set(),    // books visually expanded in the tree
  labelsStorySelected: null,        // story currently selected (null = book-grid view)
  labelsEngine: "",                 // engine filter ("" = all engines)
  labelsCategoryFilter: null,       // Set of allowed categories, null = all
  labelsTopicFilter: null,          // Set of allowed topics, null = all
  labelsShowUnattributed: false,    // false: hide zero-hit groups (default)

  // Books tab UI state
  booksBookSelected: null,          // book whose view is shown in the right pane
  booksView: "ranked",              // "ranked" | "heatmap"
  booksEngine: "",                  // engine filter ("" = all engines, mirrors Labels)
  booksCategoryFilter: null,        // Set of allowed categories, null = all
  booksScoreMode: "weighted",       // "weighted" | "hit" | "coverage" — picks the sort key

  // Ranking tab UI state
  rankingStoriesChecked: null,      // Set of "book\tstory" keys; null = "all", populated on first render
  rankingBookExpanded: new Set(),   // books visually expanded in the tree
  rankingLabels: [],                // ordered [{category, topic}] picks
  rankingEngine: "",                // engine filter ("" = first available)
  rankingScoreMode: "weighted",     // "weighted" | "straight"
  rankingCombineMode: "position",   // "position" | "equal"
  rankingThreshold: 0,              // 0..100
};

// ---------- Bootstrap ----------

async function bootstrap() {
  try {
    const [manifest, prompts, stories] = await Promise.all([
      fetchJson(`${DATA_ROOT}/index.json`),
      fetchJson(`${DATA_ROOT}/prompts.json`),
      fetchJson(`${DATA_ROOT}/stories.json`),
    ]);
    state.manifest = manifest;
    state.prompts = prompts;
    state.stories = stories;

    // Labels are optional — only present if `prophecy label` was run before
    // the export. Don't fail bootstrap if missing; the Labels tab will say so.
    const labelsFile = manifest.files && manifest.files.labels;
    if (labelsFile) {
      try {
        const labelsPayload = await fetchJson(`${DATA_ROOT}/${labelsFile}`);
        state.labels = labelsPayload.labels || [];
      } catch (err) {
        console.warn(`Failed to load labels file ${labelsFile}:`, err);
        state.labels = [];
      }
    }

    const usedCount = (manifest.used_prompt_ids || []).length;
    document.getElementById("manifest-summary").textContent =
      `${manifest.total_results.toLocaleString()} results, ${manifest.books.length} books, ` +
      `${usedCount} of ${prompts.length} prompts used, ` +
      `${manifest.engines.length} engine(s) — generated ${manifest.generated_at}`;
    document.getElementById("data-source").textContent =
      `Data root: ${DATA_ROOT}`;

    populateFilterOptions();
    renderPrompts();
    renderLabelsTab();
    renderBooksTab();
    renderRankingTab();
    bindEvents();

    // Honour the URL hash on first paint: deep-links like ?…#books open
    // straight to that tab. Unknown / empty hash leaves the markup's
    // default (Labels) selected.
    const initial = window.location.hash.replace(/^#/, "");
    if (validTabName(initial)) {
      switchTab(initial, { fromHash: true });
    }
    // Back/forward navigation through tab history.
    window.addEventListener("hashchange", () => {
      const name = window.location.hash.replace(/^#/, "");
      if (validTabName(name)) switchTab(name, { fromHash: true });
    });
  } catch (err) {
    showFatal(err);
  }
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load ${url}: HTTP ${res.status}`);
  return res.json();
}

async function fetchJsonl(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load ${url}: HTTP ${res.status}`);
  const text = await res.text();
  const rows = [];
  for (const line of text.split("\n")) {
    if (!line) continue;
    try {
      rows.push(JSON.parse(line));
    } catch (e) {
      console.warn(`Skipping malformed JSONL line in ${url}`, e);
    }
  }
  return rows;
}

function showFatal(err) {
  const main = document.querySelector("main");
  main.innerHTML = `<p style="color:#c53030">Failed to load data: ${escapeHtml(
    err.message,
  )}</p>`;
  console.error(err);
}

// ---------- Filter option population ----------

function populateFilterOptions() {
  const m = state.manifest;

  // Prompts tab: filters reflect the prompts.tsv content (all defined prompts),
  // since the tab is a browser for prompt definitions, not for cached results.
  const allPromptCategorys = sortedUnique(state.prompts.map((p) => p.category));
  const allPromptTopics = sortedUnique(state.prompts.map((p) => p.topic));
  fillSelect("prompts-category", allPromptCategorys);
  fillSelect("prompts-topic", allPromptTopics);

  // Query/Responses tabs reflect the cached data only (manifest facets).
  const stories = m.stories || [];
  fillSelect("responses-book", m.books);
  fillSelect("responses-story", stories);
  fillSelect("responses-category", m.categories);
  fillSelect("responses-topic", m.topics);
  fillSelect("responses-engine", m.engines);

  fillSelect("query-book", m.books);
  fillSelect("query-story", stories);

  // Multi-select checkbox lists on the Query tab. Default to all-checked so
  // an unconfigured query returns everything.
  fillCheckboxList("query-category", m.categories, true);
  fillCheckboxList("query-topic", m.topics, true);
  fillCheckboxList("query-engine", m.engines, true);
}

function fillCheckboxList(containerId, options, defaultChecked) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  for (const opt of options) {
    const id = `${containerId}__${cssSafe(opt)}`;
    const label = document.createElement("label");
    label.innerHTML =
      `<input type="checkbox" value="${escapeHtml(opt)}" id="${escapeHtml(id)}"` +
      `${defaultChecked ? " checked" : ""} />` +
      `<span>${escapeHtml(opt)}</span>`;
    container.appendChild(label);
  }
  // Each toggle in this list should keep its dropdown's summary in sync.
  container.addEventListener("change", (e) => {
    if (e.target.matches('input[type="checkbox"]')) {
      updateDropdownSummary(containerId);
    }
  });
  updateDropdownSummary(containerId);
}

function updateDropdownSummary(containerId) {
  const dropdown = document.querySelector(`.multi-dropdown[data-target="${containerId}"]`);
  if (!dropdown) return;
  const summary = dropdown.querySelector(".multi-summary");
  const checked = readCheckedValues(containerId);
  const total = readAllValues(containerId).length;
  if (total === 0) {
    summary.textContent = "(none available)";
  } else if (checked.length === total) {
    summary.textContent = `All (${total})`;
  } else if (checked.length === 0) {
    summary.textContent = "None";
  } else if (checked.length <= 2) {
    summary.textContent = checked.join(", ");
  } else {
    summary.textContent = `${checked.length} of ${total}`;
  }
}

function readCheckedValues(containerId) {
  return Array.from(
    document.querySelectorAll(`#${containerId} input[type="checkbox"]:checked`),
  ).map((el) => el.value);
}

function readAllValues(containerId) {
  return Array.from(
    document.querySelectorAll(`#${containerId} input[type="checkbox"]`),
  ).map((el) => el.value);
}

function setAllChecked(containerId, checked) {
  for (const el of document.querySelectorAll(`#${containerId} input[type="checkbox"]`)) {
    el.checked = checked;
  }
  updateDropdownSummary(containerId);
}

function cssSafe(s) {
  return String(s).replace(/[^a-zA-Z0-9_-]/g, "_");
}

function sortedUnique(values) {
  return Array.from(new Set(values.filter(Boolean))).sort();
}

// Render the optional ``sources`` tags for a story as label chips.
// Returns an array of HTML strings (one chip per source); empty if the
// story has no declared sources.
function sourceChips(story) {
  const meta = state.stories[story];
  const sources = (meta && meta.sources) || [];
  return sources.map(
    (src) =>
      `<span class="source-chip" title="Source: ${escapeHtml(src)}">${escapeHtml(src)}</span>`,
  );
}

function fillSelect(id, options) {
  const el = document.getElementById(id);
  // Preserve the existing "(all)" placeholder.
  for (const opt of options) {
    const o = document.createElement("option");
    o.value = opt;
    o.textContent = opt;
    el.appendChild(o);
  }
}

// ---------- Tabs ----------

function bindEvents() {
  for (const btn of document.querySelectorAll(".tab-button")) {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  }

  document.getElementById("prompts-category").addEventListener("change", renderPrompts);
  document.getElementById("prompts-topic").addEventListener("change", renderPrompts);
  document.getElementById("prompts-search").addEventListener("input", debounce(renderPrompts, 150));

  for (const id of [
    "responses-book",
    "responses-story",
    "responses-category",
    "responses-topic",
    "responses-engine",
    "responses-answer",
  ]) {
    document.getElementById(id).addEventListener("change", renderResponses);
  }
  document
    .getElementById("responses-min-certainty")
    .addEventListener("input", debounce(renderResponses, 150));

  document.getElementById("query-run").addEventListener("click", runQuery);

  // Labels tab: engine dropdown rerenders the right pane.
  document.getElementById("labels-engine").addEventListener("change", (e) => {
    state.labelsEngine = e.target.value;
    renderLabelsPaneBody();
  });

  // Labels tab: non-attributed-labels toggle. Off by default because the
  // zero-hit groups are mostly noise; turning it on reveals what the model
  // *didn't* say about each story.
  document.getElementById("labels-show-unattributed").addEventListener("change", (e) => {
    state.labelsShowUnattributed = e.target.checked;
    renderLabelsTree();
    renderLabelsPaneBody();
  });

  // Labels tab: category/topic checkbox lists rerender on change.
  for (const id of ["labels-category", "labels-topic"]) {
    document.getElementById(id).addEventListener("change", (e) => {
      if (e.target.matches('input[type="checkbox"]')) {
        renderLabelsPaneBody();
      }
    });
  }

  // Books tab: engine dropdown and category multi-select rerender the body.
  document.getElementById("books-engine").addEventListener("change", (e) => {
    state.booksEngine = e.target.value;
    renderBooksPaneBody();
  });
  document.getElementById("books-category").addEventListener("change", (e) => {
    if (e.target.matches('input[type="checkbox"]')) {
      renderBooksPaneBody();
    }
  });
  // View toggle (Ranked / Heatmap).
  for (const btn of document.querySelectorAll(".books-view-btn")) {
    btn.addEventListener("click", () => {
      state.booksView = btn.dataset.view;
      for (const b of document.querySelectorAll(".books-view-btn")) {
        const active = b.dataset.view === state.booksView;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", active ? "true" : "false");
      }
      renderBooksPaneBody();
    });
  }
  // Score mode picker — re-aggregates and re-sorts under the new metric.
  document.getElementById("books-score-mode").addEventListener("change", (e) => {
    state.booksScoreMode = e.target.value;
    renderBooksPaneBody();
  });

  // Ranking tab: all the small controls live in a static block; render the
  // body whenever any of them changes.
  document.getElementById("ranking-engine").addEventListener("change", (e) => {
    state.rankingEngine = e.target.value;
    renderRankingResults();
  });
  document.getElementById("ranking-score-mode").addEventListener("change", (e) => {
    state.rankingScoreMode = e.target.value;
    renderRankingResults();
  });
  document.getElementById("ranking-combine-mode").addEventListener("change", (e) => {
    state.rankingCombineMode = e.target.value;
    renderRankingResults();
  });
  document.getElementById("ranking-threshold").addEventListener("input", (e) => {
    state.rankingThreshold = Number(e.target.value) || 0;
    document.getElementById("ranking-threshold-value").textContent =
      `${state.rankingThreshold}%`;
    renderRankingResults();
  });
  document.getElementById("ranking-label-add").addEventListener("change", (e) => {
    const v = e.target.value;
    if (!v) return;
    const [category, topic] = v.split("\t");
    if (!state.rankingLabels.some((l) => l.category === category && l.topic === topic)) {
      state.rankingLabels.push({ category, topic });
    }
    e.target.value = "";
    renderRankingLabelsList();
    renderRankingLabelAddOptions();
    renderRankingResults();
  });

  // Ranking tree all/none.
  for (const btn of document.querySelectorAll(".ranking-tree-actions button")) {
    btn.addEventListener("click", () => {
      const all = btn.dataset.action === "all";
      state.rankingStoriesChecked = all ? new Set(rankingAllStoryKeys()) : new Set();
      renderRankingTree();
      renderRankingResults();
    });
  }

  // All/none buttons inside multi-select panels.
  for (const btn of document.querySelectorAll(".multi-actions button")) {
    btn.addEventListener("click", () => {
      const target = btn.dataset.target;
      const action = btn.dataset.action;
      setAllChecked(target, action === "all");
      if (target === "labels-category" || target === "labels-topic") {
        renderLabelsPaneBody();
      }
      if (target === "books-category") {
        renderBooksPaneBody();
      }
    });
  }

  // Open/close behavior for the multi-select dropdowns.
  for (const dropdown of document.querySelectorAll(".multi-dropdown")) {
    const toggle = dropdown.querySelector(".multi-toggle");
    const panel = dropdown.querySelector(".multi-panel");
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const willOpen = panel.hasAttribute("hidden");
      closeAllDropdowns();
      if (willOpen) {
        panel.removeAttribute("hidden");
        toggle.setAttribute("aria-expanded", "true");
      }
    });
    // Keep clicks inside the panel from bubbling up to the document handler
    // (which would close it).
    panel.addEventListener("click", (e) => e.stopPropagation());
  }

  // Click anywhere else: close any open dropdown.
  document.addEventListener("click", closeAllDropdowns);
  // Escape: close any open dropdown.
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllDropdowns();
  });
}

function closeAllDropdowns() {
  for (const dropdown of document.querySelectorAll(".multi-dropdown")) {
    const panel = dropdown.querySelector(".multi-panel");
    const toggle = dropdown.querySelector(".multi-toggle");
    if (!panel.hasAttribute("hidden")) {
      panel.setAttribute("hidden", "");
      toggle.setAttribute("aria-expanded", "false");
    }
  }
}

function switchTab(name, opts = {}) {
  for (const btn of document.querySelectorAll(".tab-button")) {
    btn.classList.toggle("active", btn.dataset.tab === name);
  }
  for (const panel of document.querySelectorAll(".tab-panel")) {
    panel.classList.toggle("active", panel.id === `tab-${name}`);
  }
  if (name === "responses") renderResponses();
  // Sync the URL hash so each tab change pushes a history entry — back
  // button then walks the user through the tabs they visited. Skip when
  // we're already responding to a hash change to avoid a feedback loop.
  if (!opts.fromHash) {
    const target = `#${name}`;
    if (window.location.hash !== target) {
      window.location.hash = name;
    }
  }
}

// The set of tab names backed by an actual panel — used to filter hash
// values so a stray `#anything` doesn't blank the UI.
function validTabName(name) {
  return Boolean(
    name && document.querySelector(`.tab-button[data-tab="${name}"]`),
  );
}

// ---------- Labels tab ----------

function renderLabelsTab() {
  // Engine dropdown reflects the set of engines actually present in labels.
  const engineSelect = document.getElementById("labels-engine");
  engineSelect.length = 1; // preserve "(all)"
  const engines = sortedUnique(state.labels.map((l) => l.engine));
  for (const e of engines) {
    const opt = document.createElement("option");
    opt.value = e;
    opt.textContent = e;
    engineSelect.appendChild(opt);
  }

  // Category/Topic multi-select checkboxes: derived from what's actually in
  // the labels file (not from prompts.tsv, since unused categories would just
  // be no-ops in this tab).
  fillCheckboxList(
    "labels-category",
    sortedUnique(state.labels.map((l) => l.category)),
    true,
  );
  fillCheckboxList(
    "labels-topic",
    sortedUnique(state.labels.map((l) => l.topic)),
    true,
  );

  renderLabelsTree();
  renderLabelsPaneBody();
}

function readLabelsFilters() {
  // Mirror the runQuery treatment: empty set = match nothing; fully-checked
  // = no filter (null).
  const catChecked = readCheckedValues("labels-category");
  const catTotal = readAllValues("labels-category").length;
  const topicChecked = readCheckedValues("labels-topic");
  const topicTotal = readAllValues("labels-topic").length;

  state.labelsCategoryFilter =
    catChecked.length === catTotal ? null : new Set(catChecked);
  state.labelsTopicFilter =
    topicChecked.length === topicTotal ? null : new Set(topicChecked);
}

function filteredLabels() {
  // Apply engine + category + topic filters in one pass.
  return state.labels.filter((l) => {
    if (state.labelsEngine && l.engine !== state.labelsEngine) return false;
    if (state.labelsCategoryFilter && !state.labelsCategoryFilter.has(l.category))
      return false;
    if (state.labelsTopicFilter && !state.labelsTopicFilter.has(l.topic)) return false;
    // labels.json now includes zero-hit groups; treat anything missing the
    // attributed field as legacy data that *was* attributed (any signal).
    const isAttributed = l.attributed !== undefined ? l.attributed : l.hits > 0;
    if (!state.labelsShowUnattributed && !isAttributed) return false;
    return true;
  });
}

function renderLabelsTree() {
  const root = document.getElementById("labels-book-list");
  // The tree shows the attribution-aware universe — when the user toggles on
  // "show non-attributed", stories that only have negative results appear
  // here too. Engine/category/topic filters still don't reorder the tree.
  const treeSource = state.labels.filter((l) => {
    const isAttributed = l.attributed !== undefined ? l.attributed : l.hits > 0;
    return state.labelsShowUnattributed || isAttributed;
  });
  const labeledBooks = sortedUnique(treeSource.map((l) => l.book));
  const books = labeledBooks.length
    ? labeledBooks
    : Array.from(state.manifest.books || []);

  root.innerHTML = books
    .map((book) => {
      const isExpanded = state.labelsBookExpanded.has(book);
      const isActive = state.labelsBookSelected === book;
      const stories = sortedUnique(
        treeSource.filter((l) => l.book === book).map((l) => l.story),
      );
      const storyItems = stories
        .map((s) => {
          const cls = state.labelsStorySelected === s ? "tree-story active" : "tree-story";
          const chips = sourceChips(s).join("");
          const chipHtml = chips ? ` <span class="source-chip-row">${chips}</span>` : "";
          return `<li class="${cls}" data-book="${escapeHtml(book)}" data-story="${escapeHtml(s)}">${escapeHtml(s)}${chipHtml}</li>`;
        })
        .join("");

      return `
        <li class="tree-book ${isExpanded ? "expanded" : ""} ${isActive ? "active" : ""}" data-book="${escapeHtml(book)}">
          <div class="tree-book-title">
            <span class="tree-book-chevron" data-role="chevron" role="button" aria-label="Toggle ${escapeHtml(book)}">▶</span>
            <span data-role="book-name">${escapeHtml(book)}</span>
          </div>
          <ul class="tree-story-list">${storyItems}</ul>
        </li>`;
    })
    .join("");

  // Chevron click: toggle expand/collapse only. Doesn't change which book is
  // selected, so the right pane keeps showing whatever it was showing.
  for (const node of root.querySelectorAll(".tree-book-chevron")) {
    node.addEventListener("click", (e) => {
      e.stopPropagation();
      const book = node.closest(".tree-book").dataset.book;
      if (state.labelsBookExpanded.has(book)) {
        state.labelsBookExpanded.delete(book);
      } else {
        state.labelsBookExpanded.add(book);
      }
      renderLabelsTree();
    });
  }

  // Book name click: select the book, ensure expanded, show book grid. Never
  // collapses — that's what the chevron is for.
  for (const node of root.querySelectorAll('[data-role="book-name"]')) {
    node.addEventListener("click", () => {
      const book = node.closest(".tree-book").dataset.book;
      state.labelsBookSelected = book;
      state.labelsStorySelected = null;
      state.labelsBookExpanded.add(book);
      renderLabelsTree();
      renderLabelsPaneBody();
    });
  }

  // Story click: drill into the per-story detail.
  for (const node of root.querySelectorAll(".tree-story")) {
    node.addEventListener("click", (e) => {
      e.stopPropagation();
      state.labelsBookSelected = node.dataset.book;
      state.labelsStorySelected = node.dataset.story;
      state.labelsBookExpanded.add(node.dataset.book);
      renderLabelsTree();
      renderLabelsPaneBody();
    });
  }
}

function renderLabelsPaneBody() {
  // Always re-read the filter checkboxes before rendering so the right pane
  // is consistent with the toolbar.
  readLabelsFilters();

  const title = document.getElementById("labels-pane-title");
  const body = document.getElementById("labels-pane-body");

  if (!state.labels.length) {
    title.textContent = "No labels available";
    body.innerHTML = `<div class="labels-empty">
      Run <code>python -m prophecy label</code> and re-export to populate this tab.
    </div>`;
    return;
  }

  if (!state.labelsBookSelected) {
    title.textContent = "Select a book";
    body.innerHTML = `<div class="labels-empty">Pick a book on the left to see its stories and labels.</div>`;
    return;
  }

  const filtered = filteredLabels();
  const bookLabels = filtered.filter((l) => l.book === state.labelsBookSelected);

  if (!bookLabels.length) {
    title.textContent = state.labelsBookSelected;
    body.innerHTML = `<div class="labels-empty">No labels for this book with the current filters.</div>`;
    return;
  }

  if (!state.labelsStorySelected) {
    renderBookGrid(bookLabels, title, body);
  } else {
    const storyLabels = bookLabels.filter((l) => l.story === state.labelsStorySelected);
    if (!storyLabels.length) {
      title.innerHTML = `${escapeHtml(state.labelsStorySelected)} <span class="muted">(${escapeHtml(state.labelsBookSelected)})</span>`;
      body.innerHTML = `<div class="labels-empty">No labels for this story with the current filters.</div>`;
      return;
    }
    renderStoryDetail(
      state.labelsStorySelected,
      state.labelsBookSelected,
      storyLabels,
      title,
      body,
    );
  }
}

function renderBookGrid(bookLabels, title, body) {
  const book = state.labelsBookSelected;
  title.textContent = `${book}`;

  // Group labels by story; render one row per story with chips.
  const byStory = new Map();
  for (const l of bookLabels) {
    if (!byStory.has(l.story)) byStory.set(l.story, []);
    byStory.get(l.story).push(l);
  }

  // Stable, alphabetical order by story title.
  const stories = Array.from(byStory.keys()).sort();
  const rows = stories
    .map((story) => {
      const labels = byStory.get(story);
      // Most distinctive labels first (highest hit count).
      labels.sort((a, b) => b.hits - a.hits || a.topic.localeCompare(b.topic));
      const chips = [
        ...sourceChips(story),
        ...labels.map((l) => {
          const isAttributed = l.attributed !== undefined ? l.attributed : l.hits > 0;
          const cls = isAttributed ? "label-chip" : "label-chip label-chip-unattributed";
          return `<span class="${cls}" data-category="${escapeHtml(l.category)}"
                   title="${escapeHtml(l.topic)}:${escapeHtml(l.category)} — ${l.hits}/${l.total} (avg ${l.avg_certainty})">
              ${escapeHtml(l.topic)}
              <span class="label-chip-score">${l.hits}/${l.total}</span>
            </span>`;
        }),
      ].join("");
      const labelCount = labels.length;
      return `
        <div class="story-grid-row" data-story="${escapeHtml(story)}">
          <div class="story-grid-name">
            ${escapeHtml(story)}
            <span class="story-meta">${labelCount} label${labelCount === 1 ? "" : "s"}</span>
          </div>
          <div class="story-grid-chips">${chips}</div>
        </div>`;
    })
    .join("");

  body.innerHTML = `<div class="story-grid">${rows}</div>`;

  // Click a row → drill into story detail.
  for (const row of body.querySelectorAll(".story-grid-row")) {
    row.addEventListener("click", () => {
      state.labelsStorySelected = row.dataset.story;
      renderLabelsTree();
      renderLabelsPaneBody();
    });
  }
}

function renderStoryDetail(story, book, storyLabels, title, body) {
  const sources = sourceChips(story).join("");
  const sourcesHtml = sources ? ` <span class="source-chip-row">${sources}</span>` : "";
  title.innerHTML =
    `${escapeHtml(story)} <span class="muted">(${escapeHtml(book)})</span>${sourcesHtml}`;

  // Order labels by hit count desc.
  storyLabels.sort((a, b) => b.hits - a.hits || a.topic.localeCompare(b.topic));

  const cards = storyLabels.map((l) => renderLabelCard(l, storyLabels)).join("");

  const meta = state.stories[story] || {};
  const verseRefs = (meta.verses || []).join(", ");
  const verseRefsHtml = verseRefs
    ? `<div class="story-text-verses muted">${escapeHtml(meta.book || book)} ${escapeHtml(verseRefs)}</div>`
    : "";
  // The export bundles Hebrew text per story (when the corpus is present).
  // Collapse to a couple of lines by default — most pericopes are long
  // enough that showing the full text crowds out the labels. A fade-out
  // gradient signals there's more below; the toggle expands the box.
  const textHtml = meta.text
    ? `<section class="story-text" data-collapsed="true">
         ${verseRefsHtml}
         <div class="story-text-clip">
           <p class="story-text-body" dir="rtl" lang="he">${escapeHtml(meta.text)}</p>
         </div>
         <button class="story-text-toggle" type="button" aria-expanded="false">
           <span class="story-text-toggle-show">Show full text ▾</span>
           <span class="story-text-toggle-hide">Show less ▴</span>
         </button>
       </section>`
    : `<section class="story-text story-text-missing muted">
         No biblical text bundled for this story — re-run <code>prophecy export</code> with a Bible corpus available.
       </section>`;

  body.innerHTML = `${textHtml}<div class="label-cards">${cards}</div>`;

  // Wire up the collapse/expand toggle. If the text fits without overflow,
  // strip the collapsed state entirely so the gradient + button don't appear
  // for short passages.
  const textSection = body.querySelector(".story-text[data-collapsed]");
  if (textSection) {
    const clip = textSection.querySelector(".story-text-clip");
    const toggle = textSection.querySelector(".story-text-toggle");
    // Read after layout so scrollHeight reflects the constrained height.
    requestAnimationFrame(() => {
      if (clip.scrollHeight <= clip.clientHeight + 1) {
        textSection.removeAttribute("data-collapsed");
        toggle.remove();
      }
    });
    toggle.addEventListener("click", () => {
      const collapsed = textSection.getAttribute("data-collapsed") === "true";
      textSection.setAttribute("data-collapsed", collapsed ? "false" : "true");
      toggle.setAttribute("aria-expanded", collapsed ? "true" : "false");
    });
  }
}

// Render one label card. True prompts are listed inline; false prompts hide
// under a native <details> disclosure so the default view only shows positive
// signal, but the full evidence is one click away.
function renderLabelCard(l, storyLabels) {
  const pct = l.total ? (l.hits / l.total) * 100 : 0;
  const truePrompts = l.prompts.filter((p) => p.answer);
  const falsePrompts = l.prompts.filter((p) => !p.answer);
  const trueRows = truePrompts.map(renderPromptRow).join("");
  const falseRows = falsePrompts.map(renderPromptRow).join("");
  const falseBlock = falsePrompts.length
    ? `<details class="label-card-false">
         <summary>Show ${falsePrompts.length} false answer${falsePrompts.length === 1 ? "" : "s"}</summary>
         <ul class="label-card-prompts">${falseRows}</ul>
       </details>`
    : "";
  const engineNote =
    state.labelsEngine || storyLabels.every((x) => x.engine === l.engine)
      ? ""
      : `<span class="muted" style="font-size:11px"> · ${escapeHtml(l.engine)}</span>`;
  const isAttributed = l.attributed !== undefined ? l.attributed : l.hits > 0;
  const cardClasses = isAttributed
    ? "label-card"
    : "label-card label-card-unattributed";
  // For unattributed groups every prompt is false — there's nothing to show
  // inline. Open the false-list by default so the rationale is still one
  // click away to skim.
  const promptsHtml = isAttributed
    ? `<ul class="label-card-prompts">${trueRows}</ul>${falseBlock}`
    : falsePrompts.length
      ? `<details class="label-card-false" open>
           <summary>${falsePrompts.length} false answer${falsePrompts.length === 1 ? "" : "s"}</summary>
           <ul class="label-card-prompts">${falseRows}</ul>
         </details>`
      : "";
  return `
    <article class="${cardClasses}" data-category="${escapeHtml(l.category)}">
      <div class="label-card-head">
        <h3 class="label-card-title">
          ${escapeHtml(l.topic)}
          <span class="label-card-category">:${escapeHtml(l.category)}</span>
          ${engineNote}
        </h3>
        <div class="label-card-score">
          <div>${l.hits} / ${l.total} · avg cert ${l.avg_certainty}</div>
          <div class="label-card-bar"><div class="label-card-bar-fill" style="width:${pct.toFixed(1)}%"></div></div>
        </div>
      </div>
      ${promptsHtml}
    </article>`;
}

function renderPromptRow(p) {
  const ans = p.answer ? "✓" : "✗";
  const ansCls = p.answer ? "answer-true" : "answer-false";
  const liCls = p.answer ? "" : "is-false";
  // Cache id provenance: show the last 8 chars of the MD5 (full stem stays
  // in the cache filename) so the user can grep the cache folder back to
  // the exact result. Fall back gracefully on legacy entries without one.
  const cacheTag = p.cache_id
    ? `<span class="prompt-cache" title="cache: ${escapeHtml(p.cache_id)}.json">${escapeHtml(p.cache_id.slice(-8))}</span>`
    : "";
  const reason = (p.reason || "").trim();
  const reasonBlock = reason
    ? `<div class="prompt-rationale">${escapeHtml(reason)}</div>`
    : `<div class="prompt-rationale prompt-rationale-empty muted">(no rationale recorded)</div>`;
  // <details> turns the row itself into the click target. The summary holds
  // the existing grid layout; the rationale unfolds below it when clicked.
  return `<li class="${liCls}">
    <details class="prompt-row">
      <summary class="prompt-row-summary">
        <span class="answer-mark ${ansCls}">${ans}</span>
        <span class="prompt-id">#${escapeHtml(p.id)}</span>
        ${cacheTag}
        <span class="prompt-text">${escapeHtml(p.prompt)}</span>
        <span class="prompt-cert">${p.certainty}</span>
      </summary>
      ${reasonBlock}
    </details>
  </li>`;
}

// ---------- Books tab ----------
//
// Per-book aggregate view. For a selected book, we sum across its stories to
// surface which (category, topic) labels show up and how strongly. Two
// presentations of the same underlying aggregation:
//   - Ranked: horizontal bars sorted by coverage (share of stories carrying
//     the label). Reads as "what does this book look like, overall?"
//   - Heatmap: stories × labels grid. Reads as "which subset of stories
//     does each label cluster on?" — the visual the user calls "layers".
// Clicking a label routes back to the Labels tab pre-filtered to that
// book + (category, topic) so the user can read the underlying prompts.

function renderBooksTab() {
  const engineSelect = document.getElementById("books-engine");
  engineSelect.length = 1; // preserve "(all)"
  const engines = sortedUnique(state.labels.map((l) => l.engine));
  for (const e of engines) {
    const opt = document.createElement("option");
    opt.value = e;
    opt.textContent = e;
    engineSelect.appendChild(opt);
  }

  fillCheckboxList(
    "books-category",
    sortedUnique(state.labels.map((l) => l.category)),
    true,
  );

  renderBooksList();
  renderBooksPaneBody();
}

function readBooksFilters() {
  const catChecked = readCheckedValues("books-category");
  const catTotal = readAllValues("books-category").length;
  state.booksCategoryFilter =
    catChecked.length === catTotal ? null : new Set(catChecked);
}

// Labels filtered by current engine + category. The book filter is applied
// per-render where needed, since the tree shows all books regardless.
function filteredBooksLabels() {
  return state.labels.filter((l) => {
    if (state.booksEngine && l.engine !== state.booksEngine) return false;
    if (state.booksCategoryFilter && !state.booksCategoryFilter.has(l.category)) return false;
    const isAttributed = l.attributed !== undefined ? l.attributed : l.hits > 0;
    if (!isAttributed) return false;
    return true;
  });
}

function renderBooksList() {
  const root = document.getElementById("books-list");
  // The book list is the universe of books that have any attributed labels —
  // unfiltered by category/engine so the user can always pick a book and
  // discover that the current filter hides everything in it.
  const universe = state.labels.filter((l) => {
    const isAttributed = l.attributed !== undefined ? l.attributed : l.hits > 0;
    return isAttributed;
  });
  const books = sortedUnique(universe.map((l) => l.book));
  root.innerHTML = books
    .map((book) => {
      const active = state.booksBookSelected === book ? " active" : "";
      return `<li class="books-list-item${active}" data-book="${escapeHtml(book)}">${escapeHtml(book)}</li>`;
    })
    .join("");
  for (const node of root.querySelectorAll(".books-list-item")) {
    node.addEventListener("click", () => {
      state.booksBookSelected = node.dataset.book;
      renderBooksList();
      renderBooksPaneBody();
    });
  }
}

function renderBooksPaneBody() {
  readBooksFilters();

  const title = document.getElementById("books-pane-title");
  const body = document.getElementById("books-pane-body");

  if (!state.labels.length) {
    title.textContent = "No labels available";
    body.innerHTML = `<div class="labels-empty">
      Run <code>python -m prophecy label</code> and re-export to populate this tab.
    </div>`;
    return;
  }

  if (!state.booksBookSelected) {
    title.textContent = "Select a book";
    body.innerHTML = `<div class="labels-empty">Pick a book on the left to see how labels layer across its stories.</div>`;
    return;
  }

  const filtered = filteredBooksLabels().filter(
    (l) => l.book === state.booksBookSelected,
  );
  const stories = sortedUnique(filtered.map((l) => l.story));
  title.innerHTML = `${escapeHtml(state.booksBookSelected)} <span class="muted">— ${stories.length} stor${stories.length === 1 ? "y" : "ies"}</span>`;

  if (!filtered.length) {
    body.innerHTML = `<div class="labels-empty">No attributed labels for this book under the current filters.</div>`;
    return;
  }

  if (state.booksView === "ranked") {
    renderBooksRanked(filtered, stories, body);
  } else {
    renderBooksHeatmap(filtered, stories, body);
  }
}

// Per-story score for one label row, in [0, 1]. "Weighted" multiplies hit
// rate by the model's self-rated certainty so weak hits with low certainty
// are discounted; "hit" ignores certainty; "coverage" is the binary
// presence signal used to count toward layer coverage.
function storyScore(row, mode) {
  const hitRate = row.total > 0 ? row.hits / row.total : 0;
  if (mode === "hit") return hitRate;
  if (mode === "coverage") return hitRate > 0 ? 1 : 0;
  // "weighted" (default): hit_rate × certainty. avg_certainty is 0-100.
  const cert = (row.avg_certainty || 0) / 100;
  return hitRate * cert;
}

// Aggregate by (category, topic) across the given (already book-filtered)
// label rows. Computes both layer strength (mean per-story score under the
// chosen mode) and coverage (share of stories with any signal). The chosen
// score mode selects the sort key — both numbers stay displayed so the
// user can read "widespread-but-weak" vs "narrow-but-strong" by eye.
function aggregateBooksLabels(rows, totalStories) {
  const mode = state.booksScoreMode;
  const byKey = new Map();
  for (const r of rows) {
    const key = `${r.category}\t${r.topic}`;
    let agg = byKey.get(key);
    if (!agg) {
      agg = {
        category: r.category,
        topic: r.topic,
        stories_hit: new Set(),
        score_sum: 0,
        score_count: 0,
      };
      byKey.set(key, agg);
    }
    const score = storyScore(r, mode);
    agg.score_sum += score;
    agg.score_count += 1;
    if (score > 0) {
      agg.stories_hit.add(r.story);
    }
  }
  const out = [];
  for (const a of byKey.values()) {
    const coverage =
      totalStories > 0 ? a.stories_hit.size / totalStories : 0;
    const layer_score = a.score_count > 0 ? a.score_sum / a.score_count : 0;
    out.push({
      category: a.category,
      topic: a.topic,
      story_count: a.stories_hit.size,
      total_stories: totalStories,
      coverage,
      layer_score,
    });
  }
  // Sort by the selected primary metric, falling back to the other so ties
  // don't shuffle every render.
  const primary = (a) => (mode === "coverage" ? a.coverage : a.layer_score);
  const secondary = (a) => (mode === "coverage" ? a.layer_score : a.coverage);
  out.sort((a, b) => primary(b) - primary(a) || secondary(b) - secondary(a));
  return out;
}

// Parse "chapter:verse" or "chapter:verse-chapter:verse" → numeric sort key.
// Returns [chapter, verse] for the *first* verse of the range.
function firstVersePos(verseRange) {
  if (!verseRange) return [Infinity, Infinity];
  const start = String(verseRange).split("-")[0];
  const parts = start.split(":");
  const ch = Number(parts[0]) || 0;
  const v = Number(parts[1]) || 0;
  return [ch, v];
}

// Canonical narrative order for stories in a book: by the (chapter, verse)
// of the first verse range. Stories with no metadata fall to the end
// alphabetically so the order is always stable.
function sortStoriesCanonical(stories) {
  return stories.slice().sort((a, b) => {
    const ma = state.stories[a];
    const mb = state.stories[b];
    const va = ma && Array.isArray(ma.verses) ? ma.verses[0] : null;
    const vb = mb && Array.isArray(mb.verses) ? mb.verses[0] : null;
    const [ca, ra] = firstVersePos(va);
    const [cb, rb] = firstVersePos(vb);
    if (ca !== cb) return ca - cb;
    if (ra !== rb) return ra - rb;
    return a.localeCompare(b);
  });
}

function renderBooksRanked(rows, stories, body) {
  const agg = aggregateBooksLabels(rows, stories.length);
  const mode = state.booksScoreMode;
  // The bar fill follows the chosen score mode: Weighted/Hit show layer
  // strength; Coverage shows coverage. Either way the *other* number is
  // surfaced as text so the user sees both dimensions.
  const items = agg
    .map((a) => {
      const coveragePct = Math.round(a.coverage * 100);
      const scorePct = Math.round(a.layer_score * 100);
      const fillPct = mode === "coverage" ? coveragePct : scorePct;
      const primaryLabel =
        mode === "coverage" ? `${coveragePct}%` : `${scorePct}%`;
      const secondaryLabel =
        mode === "coverage"
          ? `${a.story_count}/${a.total_stories} · score ${scorePct}%`
          : `${a.story_count}/${a.total_stories} stories · cov ${coveragePct}%`;
      return `<li class="books-bar-row" data-category="${escapeHtml(a.category)}" data-topic="${escapeHtml(a.topic)}" title="Open ${escapeHtml(a.category)} / ${escapeHtml(a.topic)} in Labels">
        <div class="books-bar-label">
          <span class="books-bar-cat" data-category="${escapeHtml(a.category)}">${escapeHtml(a.category)}</span>
          <span class="books-bar-topic">${escapeHtml(a.topic)}</span>
        </div>
        <div class="books-bar-track" role="img" aria-label="${scorePct}% layer score, ${coveragePct}% coverage">
          <div class="books-bar-fill" data-category="${escapeHtml(a.category)}" style="width: ${fillPct}%"></div>
        </div>
        <div class="books-bar-stats mono">
          <span class="books-bar-cov">${primaryLabel}</span>
          <span class="muted">${secondaryLabel}</span>
        </div>
      </li>`;
    })
    .join("");
  body.innerHTML = `<ol class="books-bar-list">${items}</ol>`;
  for (const node of body.querySelectorAll(".books-bar-row")) {
    node.addEventListener("click", () => {
      drillToLabels(state.booksBookSelected, node.dataset.category, node.dataset.topic);
    });
  }
}

function renderBooksHeatmap(rows, stories, body) {
  const agg = aggregateBooksLabels(rows, stories.length);
  if (!agg.length) {
    body.innerHTML = `<div class="labels-empty">Nothing to display.</div>`;
    return;
  }
  // Column order: by ranked importance (same as view A). Row order:
  // canonical narrative order (chapter:verse of the first verse range), so
  // the user reads down the book the way it's traditionally narrated.
  const cols = agg;
  const rowsSorted = sortStoriesCanonical(stories);
  const mode = state.booksScoreMode;
  const cellByKey = new Map();
  for (const r of rows) {
    const key = `${r.story}\t${r.category}\t${r.topic}`;
    const score = storyScore(r, mode);
    // Same (story, label) may appear under multiple engines if the user has
    // both selected — take the max so cells show the strongest signal.
    const prev = cellByKey.get(key) || 0;
    cellByKey.set(key, Math.max(prev, score));
  }

  const headerCells = cols
    .map((c) => {
      return `<th class="books-heat-colhead" data-category="${escapeHtml(c.category)}" data-topic="${escapeHtml(c.topic)}" title="${escapeHtml(c.category)} / ${escapeHtml(c.topic)} — click to open in Labels">
        <div class="books-heat-coltag" data-category="${escapeHtml(c.category)}">${escapeHtml(c.category)}</div>
        <div class="books-heat-coltopic">${escapeHtml(c.topic)}</div>
      </th>`;
    })
    .join("");

  const bodyRows = rowsSorted
    .map((story) => {
      const cells = cols
        .map((c) => {
          const score = cellByKey.get(`${story}\t${c.category}\t${c.topic}`) || 0;
          const pct = Math.round(score * 100);
          // Intensity steps keep colors readable and the visual rhythm
          // discrete — easier to see banding than a smooth gradient.
          let intensity = "i0";
          if (pct >= 75) intensity = "i4";
          else if (pct >= 50) intensity = "i3";
          else if (pct >= 25) intensity = "i2";
          else if (pct > 0) intensity = "i1";
          const scoreLabel =
            mode === "coverage" ? (pct > 0 ? "100%" : "0%") : `${pct}%`;
          const title = pct > 0
            ? `${escapeHtml(story)} — ${escapeHtml(c.category)} / ${escapeHtml(c.topic)}: ${scoreLabel} (click to open story)`
            : `${escapeHtml(story)} — no hit on ${escapeHtml(c.category)} / ${escapeHtml(c.topic)}`;
          return `<td class="books-heat-cell ${intensity}" data-story="${escapeHtml(story)}" data-category="${escapeHtml(c.category)}" data-topic="${escapeHtml(c.topic)}" title="${title}"></td>`;
        })
        .join("");
      return `<tr><th class="books-heat-rowhead" data-story="${escapeHtml(story)}">${escapeHtml(story)}</th>${cells}</tr>`;
    })
    .join("");

  body.innerHTML = `<div class="books-heat-wrap"><table class="books-heat">
    <thead><tr><th></th>${headerCells}</tr></thead>
    <tbody>${bodyRows}</tbody>
  </table></div>`;

  // Column header click: filter Labels to (book, category, topic).
  for (const node of body.querySelectorAll(".books-heat-colhead")) {
    node.addEventListener("click", () => {
      drillToLabels(state.booksBookSelected, node.dataset.category, node.dataset.topic);
    });
  }
  // Cell click: open the story detail in Labels with category/topic narrowed
  // to this cell's label so the user can immediately see why the cell has
  // its score (the underlying prompts + answers).
  for (const node of body.querySelectorAll(".books-heat-cell")) {
    node.addEventListener("click", () => {
      drillToLabelsCell(
        state.booksBookSelected,
        node.dataset.story,
        node.dataset.category,
        node.dataset.topic,
      );
    });
  }
  // Row label click: open the existing story-detail view in Labels with all
  // labels visible.
  for (const node of body.querySelectorAll(".books-heat-rowhead")) {
    node.addEventListener("click", () => {
      drillToLabelsStory(state.booksBookSelected, node.dataset.story);
    });
  }
}

// Drill into Labels filtered to one (category, topic) for a book. Selects
// the book in the Labels tree, expands it, and narrows the multi-selects to
// just the target so the right pane shows that label's cards.
function drillToLabels(book, category, topic) {
  state.labelsBookSelected = book;
  state.labelsStorySelected = null;
  state.labelsBookExpanded.add(book);
  // Mirror engine selection so the drill is consistent with what was visible.
  if (state.booksEngine) {
    state.labelsEngine = state.booksEngine;
    document.getElementById("labels-engine").value = state.booksEngine;
  }
  setSingleChecked("labels-category", category);
  setSingleChecked("labels-topic", topic);
  switchTab("labels");
  renderLabelsTree();
  renderLabelsPaneBody();
}

// Drill into Labels at the story-detail view, narrowed to one (category,
// topic) — the "why is this cell that colour?" jump. Shows the story's
// label cards filtered to just the clicked label so the prompts +
// rationales for that exact score are immediately visible.
function drillToLabelsCell(book, story, category, topic) {
  state.labelsBookSelected = book;
  state.labelsStorySelected = story;
  state.labelsBookExpanded.add(book);
  if (state.booksEngine) {
    state.labelsEngine = state.booksEngine;
    document.getElementById("labels-engine").value = state.booksEngine;
  }
  setSingleChecked("labels-category", category);
  setSingleChecked("labels-topic", topic);
  switchTab("labels");
  renderLabelsTree();
  renderLabelsPaneBody();
}

// Drill into Labels at the story-detail view for one story in a book.
function drillToLabelsStory(book, story) {
  state.labelsBookSelected = book;
  state.labelsStorySelected = story;
  state.labelsBookExpanded.add(book);
  if (state.booksEngine) {
    state.labelsEngine = state.booksEngine;
    document.getElementById("labels-engine").value = state.booksEngine;
  }
  // Don't narrow category/topic here — when reading a single story the user
  // usually wants the full label spread.
  setAllChecked("labels-category", true);
  setAllChecked("labels-topic", true);
  switchTab("labels");
  renderLabelsTree();
  renderLabelsPaneBody();
}

// Helper: tick exactly one checkbox in a multi-select list, untick all others.
function setSingleChecked(containerId, value) {
  let matched = false;
  for (const el of document.querySelectorAll(`#${containerId} input[type="checkbox"]`)) {
    const should = el.value === value;
    el.checked = should;
    if (should) matched = true;
  }
  // If the target value isn't present (shouldn't happen, but be safe), leave
  // everything checked rather than leaving the user stranded with nothing.
  if (!matched) {
    setAllChecked(containerId, true);
  }
  updateDropdownSummary(containerId);
}

// ---------- Ranking tab ----------

function renderRankingTab() {
  // Populate the engine dropdown from the labels file. Default to "(all)" so
  // the user can see everything if there's only one engine.
  const engineSelect = document.getElementById("ranking-engine");
  engineSelect.length = 1;
  const engines = sortedUnique(state.labels.map((l) => l.engine));
  for (const e of engines) {
    const opt = document.createElement("option");
    opt.value = e;
    opt.textContent = e;
    engineSelect.appendChild(opt);
  }
  engineSelect.value = state.rankingEngine;

  // First render: default to all stories checked.
  if (state.rankingStoriesChecked === null) {
    state.rankingStoriesChecked = new Set(rankingAllStoryKeys());
    // Default-expand all books (typically just one).
    for (const book of rankingAllBooks()) state.rankingBookExpanded.add(book);
  }

  renderRankingTree();
  renderRankingLabelsList();
  renderRankingLabelAddOptions();
  renderRankingResults();
}

// Universe of (book, story) pairs the tree shows — derived from labels.json so
// the ranking view is consistent with what's actually scoreable.
function rankingStoryPairs() {
  const seen = new Set();
  const pairs = [];
  for (const l of state.labels) {
    const key = `${l.book}\t${l.story}`;
    if (seen.has(key)) continue;
    seen.add(key);
    pairs.push({ book: l.book, story: l.story });
  }
  pairs.sort(
    (a, b) => a.book.localeCompare(b.book) || a.story.localeCompare(b.story),
  );
  return pairs;
}

function rankingAllStoryKeys() {
  return rankingStoryPairs().map((p) => `${p.book}\t${p.story}`);
}

function rankingAllBooks() {
  return sortedUnique(rankingStoryPairs().map((p) => p.book));
}

function rankingAllLabelKeys() {
  // Distinct (category, topic) pairs present in the labels file. We use this
  // both for the "+ Add" dropdown and to validate picks at render time.
  const seen = new Set();
  const pairs = [];
  for (const l of state.labels) {
    const key = `${l.category}\t${l.topic}`;
    if (seen.has(key)) continue;
    seen.add(key);
    pairs.push({ category: l.category, topic: l.topic });
  }
  pairs.sort(
    (a, b) =>
      a.category.localeCompare(b.category) || a.topic.localeCompare(b.topic),
  );
  return pairs;
}

function renderRankingTree() {
  const root = document.getElementById("ranking-book-list");
  const pairs = rankingStoryPairs();
  const byBook = new Map();
  for (const p of pairs) {
    if (!byBook.has(p.book)) byBook.set(p.book, []);
    byBook.get(p.book).push(p.story);
  }

  const checked = state.rankingStoriesChecked || new Set();

  root.innerHTML = Array.from(byBook.entries())
    .map(([book, stories]) => {
      const isExpanded = state.rankingBookExpanded.has(book);
      const totalCount = stories.length;
      const checkedCount = stories.filter((s) =>
        checked.has(`${book}\t${s}`),
      ).length;
      // tri-state: indeterminate when partial
      const bookChecked = checkedCount === totalCount;
      const bookIndeterminate = checkedCount > 0 && checkedCount < totalCount;

      const storyItems = stories
        .map((s) => {
          const isOn = checked.has(`${book}\t${s}`);
          return `<li class="tree-story" data-book="${escapeHtml(book)}" data-story="${escapeHtml(s)}">
              <input type="checkbox" class="tree-story-check" ${isOn ? "checked" : ""} />
              <span class="tree-story-label">${escapeHtml(s)}</span>
            </li>`;
        })
        .join("");

      return `
        <li class="tree-book ${isExpanded ? "expanded" : ""}" data-book="${escapeHtml(book)}">
          <div class="tree-book-title">
            <span class="tree-book-chevron" data-role="chevron" role="button" aria-label="Toggle ${escapeHtml(book)}">▶</span>
            <input type="checkbox" class="tree-book-check" ${bookChecked ? "checked" : ""} />
            <span data-role="book-name">${escapeHtml(book)}</span>
            <span class="muted" style="font-size:11px">${checkedCount}/${totalCount}</span>
          </div>
          <ul class="tree-story-list">${storyItems}</ul>
        </li>`;
    })
    .join("");

  // Apply tri-state visually (must be set via JS — HTML attr isn't enough).
  for (const cb of root.querySelectorAll(".tree-book-check")) {
    const book = cb.closest(".tree-book").dataset.book;
    const stories = byBook.get(book) || [];
    const c = stories.filter((s) => checked.has(`${book}\t${s}`)).length;
    cb.indeterminate = c > 0 && c < stories.length;
  }

  // Chevron click: expand/collapse only.
  for (const node of root.querySelectorAll(".tree-book-chevron")) {
    node.addEventListener("click", (e) => {
      e.stopPropagation();
      const book = node.closest(".tree-book").dataset.book;
      if (state.rankingBookExpanded.has(book)) state.rankingBookExpanded.delete(book);
      else state.rankingBookExpanded.add(book);
      renderRankingTree();
    });
  }
  // Book name click: just toggle expand (no separate selection concept here).
  for (const node of root.querySelectorAll('[data-role="book-name"]')) {
    node.addEventListener("click", () => {
      const book = node.closest(".tree-book").dataset.book;
      if (state.rankingBookExpanded.has(book)) state.rankingBookExpanded.delete(book);
      else state.rankingBookExpanded.add(book);
      renderRankingTree();
    });
  }

  // Book checkbox: toggle all stories under it.
  for (const cb of root.querySelectorAll(".tree-book-check")) {
    cb.addEventListener("click", (e) => e.stopPropagation());
    cb.addEventListener("change", () => {
      const book = cb.closest(".tree-book").dataset.book;
      const stories = byBook.get(book) || [];
      if (!state.rankingStoriesChecked) state.rankingStoriesChecked = new Set();
      if (cb.checked) {
        for (const s of stories) state.rankingStoriesChecked.add(`${book}\t${s}`);
      } else {
        for (const s of stories) state.rankingStoriesChecked.delete(`${book}\t${s}`);
      }
      renderRankingTree();
      renderRankingResults();
    });
  }

  // Story checkbox: toggle individual.
  for (const cb of root.querySelectorAll(".tree-story-check")) {
    cb.addEventListener("click", (e) => e.stopPropagation());
    cb.addEventListener("change", () => {
      const li = cb.closest(".tree-story");
      const key = `${li.dataset.book}\t${li.dataset.story}`;
      if (!state.rankingStoriesChecked) state.rankingStoriesChecked = new Set();
      if (cb.checked) state.rankingStoriesChecked.add(key);
      else state.rankingStoriesChecked.delete(key);
      renderRankingTree();
      renderRankingResults();
    });
  }

  // Clicking the story label text is a friendly alias for toggling its box.
  for (const node of root.querySelectorAll(".tree-story-label")) {
    node.addEventListener("click", () => {
      const cb = node.parentElement.querySelector(".tree-story-check");
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event("change"));
    });
  }
}

function renderRankingLabelsList() {
  const list = document.getElementById("ranking-labels-list");
  list.innerHTML = state.rankingLabels
    .map((l, idx) => {
      const last = idx === state.rankingLabels.length - 1;
      const first = idx === 0;
      return `<li data-idx="${idx}">
        <span class="rank-num">${idx + 1}</span>
        <span class="rank-label">${escapeHtml(l.category)}: ${escapeHtml(l.topic)}</span>
        <span class="rank-buttons">
          <button type="button" data-act="up" ${first ? "disabled" : ""} aria-label="Move up">▲</button>
          <button type="button" data-act="down" ${last ? "disabled" : ""} aria-label="Move down">▼</button>
          <button type="button" data-act="remove" aria-label="Remove">✕</button>
        </span>
      </li>`;
    })
    .join("");

  for (const btn of list.querySelectorAll("button")) {
    btn.addEventListener("click", () => {
      const li = btn.closest("li");
      const idx = Number(li.dataset.idx);
      const act = btn.dataset.act;
      const arr = state.rankingLabels;
      if (act === "up" && idx > 0) {
        [arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]];
      } else if (act === "down" && idx < arr.length - 1) {
        [arr[idx + 1], arr[idx]] = [arr[idx], arr[idx + 1]];
      } else if (act === "remove") {
        arr.splice(idx, 1);
      }
      renderRankingLabelsList();
      renderRankingLabelAddOptions();
      renderRankingResults();
    });
  }
}

function renderRankingLabelAddOptions() {
  const sel = document.getElementById("ranking-label-add");
  sel.length = 1; // keep "(choose…)"
  const picked = new Set(
    state.rankingLabels.map((l) => `${l.category}\t${l.topic}`),
  );
  for (const p of rankingAllLabelKeys()) {
    const key = `${p.category}\t${p.topic}`;
    if (picked.has(key)) continue;
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = `${p.category}: ${p.topic}`;
    sel.appendChild(opt);
  }
}

// Score a single (story, book, label) tuple under the current score mode.
// Returns null if there's no labels.json row matching the filter (so the caller
// can decide whether to treat as 0 or skip).
function rankingScoreFor(book, story, label) {
  for (const l of state.labels) {
    if (l.book !== book || l.story !== story) continue;
    if (l.category !== label.category || l.topic !== label.topic) continue;
    if (state.rankingEngine && l.engine !== state.rankingEngine) continue;
    if (!l.total) return 0;
    if (state.rankingScoreMode === "weighted") {
      let sum = 0;
      for (const p of l.prompts) {
        if (p.answer) sum += Number(p.certainty) || 0;
      }
      return sum / l.total;
    }
    return (l.hits / l.total) * 100;
  }
  return null;
}

function rankingCombine(scores) {
  // scores is an array aligned with state.rankingLabels (same length).
  if (!scores.length) return 0;
  if (state.rankingCombineMode === "equal") {
    let s = 0;
    for (const v of scores) s += v;
    return s / scores.length;
  }
  // Position-weighted: weight_i = N - i, normalized by sum of weights.
  const n = scores.length;
  let weighted = 0;
  let weightSum = 0;
  for (let i = 0; i < n; i++) {
    const w = n - i;
    weighted += w * scores[i];
    weightSum += w;
  }
  return weightSum ? weighted / weightSum : 0;
}

function renderRankingResults() {
  const summary = document.getElementById("ranking-summary");
  const body = document.getElementById("ranking-results-body");

  if (!state.labels.length) {
    summary.textContent = "No labels available";
    body.innerHTML = `<div class="ranking-empty">
      Run <code>python -m prophecy label</code> and re-export to populate this tab.
    </div>`;
    return;
  }
  if (!state.rankingLabels.length) {
    summary.textContent = "Pick labels and stories to rank.";
    body.innerHTML = `<div class="ranking-empty">Add at least one label above to rank stories.</div>`;
    return;
  }
  const checked = state.rankingStoriesChecked || new Set();
  if (!checked.size) {
    summary.textContent = "No stories selected";
    body.innerHTML = `<div class="ranking-empty">Check at least one story on the left.</div>`;
    return;
  }

  const thr = state.rankingThreshold;
  const labels = state.rankingLabels;

  // Score every checked story across every picked label. Intersection
  // threshold semantics: a story is dropped if it scores below the threshold
  // on any picked label (or has no data for it — null treated as 0).
  const rows = [];
  for (const key of checked) {
    const [book, story] = key.split("\t");
    const scores = labels.map((lab) => {
      const v = rankingScoreFor(book, story, lab);
      return v == null ? 0 : v;
    });
    if (scores.some((s) => s < thr)) continue;
    const combined = rankingCombine(scores);
    rows.push({ book, story, scores, combined });
  }

  rows.sort(
    (a, b) => b.combined - a.combined || a.story.localeCompare(b.story),
  );

  const modeLabel =
    state.rankingScoreMode === "weighted" ? "weighted" : "straight";
  const combineLabel =
    state.rankingCombineMode === "position" ? "position-weighted" : "equal-avg";
  summary.textContent = `${rows.length} of ${checked.size} stories pass · ${modeLabel} score · ${combineLabel} combine · threshold ${thr}%`;

  if (!rows.length) {
    body.innerHTML = `<div class="ranking-empty">No stories clear the threshold for every picked label. Lower the threshold or pick different labels.</div>`;
    return;
  }

  const headerCells = labels
    .map(
      (l, i) =>
        `<th title="${escapeHtml(l.category)}: ${escapeHtml(l.topic)}">${i + 1}. ${escapeHtml(l.topic)}</th>`,
    )
    .join("");
  const rowHtml = rows
    .map((r, idx) => {
      const scoreCells = r.scores
        .map((s) => {
          const w = Math.max(0, Math.min(100, s));
          return `<td class="score-cell score-cell-bar">${s.toFixed(1)}<span class="score-bar" style="width:${w * 0.6}px"></span></td>`;
        })
        .join("");
      return `<tr class="story-row" data-book="${escapeHtml(r.book)}" data-story="${escapeHtml(r.story)}">
        <td class="mono">${idx + 1}</td>
        <td>${escapeHtml(r.story)}</td>
        <td>${escapeHtml(r.book)}</td>
        ${scoreCells}
        <td class="score-cell score-combined">${r.combined.toFixed(1)}</td>
      </tr>`;
    })
    .join("");

  body.innerHTML = `<table>
    <thead><tr>
      <th>Rank</th><th>Story</th><th>Book</th>
      ${headerCells}
      <th>Combined</th>
    </tr></thead>
    <tbody>${rowHtml}</tbody>
  </table>`;

  // Click a row → drill into that story in the Labels tab.
  for (const tr of body.querySelectorAll("tr.story-row")) {
    tr.addEventListener("click", () => {
      state.labelsBookSelected = tr.dataset.book;
      state.labelsStorySelected = tr.dataset.story;
      state.labelsBookExpanded.add(tr.dataset.book);
      switchTab("labels");
      renderLabelsTree();
      renderLabelsPaneBody();
    });
  }
}

// ---------- Prompts tab ----------

function renderPrompts() {
  const category = document.getElementById("prompts-category").value;
  const topic = document.getElementById("prompts-topic").value;
  const search = document.getElementById("prompts-search").value.toLowerCase();

  const rows = state.prompts.filter((p) => {
    if (category && p.category !== category) return false;
    if (topic && p.topic !== topic) return false;
    if (search && !p.prompt.toLowerCase().includes(search)) return false;
    return true;
  });

  const counts = state.manifest.result_count_by_prompt || {};
  const tbody = document.querySelector("#prompts-table tbody");
  tbody.innerHTML = rows
    .map((p) => {
      const count = counts[p.id] || 0;
      const cellClass = count > 0 ? "bool-true mono" : "muted mono";
      const label = count > 0 ? String(count) : "—";
      return `
      <tr>
        <td class="mono">${escapeHtml(p.id)}</td>
        <td>${escapeHtml(p.category)}</td>
        <td>${escapeHtml(p.topic)}</td>
        <td>${escapeHtml(p.prompt)}</td>
        <td class="${cellClass}">${label}</td>
      </tr>`;
    })
    .join("");

  const usedInView = rows.filter((p) => (counts[p.id] || 0) > 0).length;
  document.getElementById("prompts-count").textContent =
    `${rows.length} / ${state.prompts.length} prompt(s), ${usedInView} with results`;
}

// ---------- Responses tab ----------

async function loadShardsFor(books) {
  const needed = books.filter((b) => !state.shardCache.has(b));
  if (!needed.length) return;

  const shardsByBook = new Map(state.manifest.shards.map((s) => [s.book, s]));
  await Promise.all(
    needed.map(async (book) => {
      const shardInfo = shardsByBook.get(book);
      if (!shardInfo) {
        state.shardCache.set(book, []);
        return;
      }
      const rows = await fetchJsonl(`${DATA_ROOT}/${shardInfo.file}`);
      state.shardCache.set(book, rows);
    }),
  );
}

function shardsToScan(filterBook) {
  return filterBook ? [filterBook] : state.manifest.books;
}

async function renderResponses() {
  const filterBook = document.getElementById("responses-book").value;
  const filterStory = document.getElementById("responses-story").value;
  const filterCategory = document.getElementById("responses-category").value;
  const filterTopic = document.getElementById("responses-topic").value;
  const filterEngine = document.getElementById("responses-engine").value;
  const filterAnswer = document.getElementById("responses-answer").value;
  const minCert = Number(document.getElementById("responses-min-certainty").value) || 0;

  const books = shardsToScan(filterBook);
  await loadShardsFor(books);

  const matched = [];
  const cap = 1000; // hard cap to keep the DOM responsive
  for (const book of books) {
    for (const r of state.shardCache.get(book) || []) {
      if (filterStory && r.story !== filterStory) continue;
      if (filterCategory && r.category !== filterCategory) continue;
      if (filterTopic && r.topic !== filterTopic) continue;
      if (filterEngine && r.engine !== filterEngine) continue;
      if (filterAnswer !== "" && String(r.answer) !== filterAnswer) continue;
      if (r.certainty < minCert) continue;
      matched.push(r);
      if (matched.length > cap * 2) break;
    }
    if (matched.length > cap * 2) break;
  }

  const tbody = document.querySelector("#responses-table tbody");
  tbody.innerHTML = matched
    .slice(0, cap)
    .map(
      (r) => `
      <tr>
        <td>${escapeHtml(r.story)}</td>
        <td>${escapeHtml(r.book)}</td>
        <td class="mono">${escapeHtml(r.prompt)}</td>
        <td>${escapeHtml(r.category)}</td>
        <td>${escapeHtml(r.topic)}</td>
        <td class="mono">${escapeHtml(r.engine)}</td>
        <td class="${r.answer ? "bool-true" : "bool-false"}">${r.answer ? "true" : "false"}</td>
        <td>${r.certainty}</td>
        <td class="reason">${escapeHtml(r.reason || "")}</td>
      </tr>`,
    )
    .join("");

  const more = matched.length > cap ? ` (showing first ${cap})` : "";
  document.getElementById("responses-count").textContent =
    `${matched.length.toLocaleString()} match${more}`;
}

// ---------- Query tab ----------

async function runQuery() {
  // For each checkbox group: an empty selection means "match nothing" (let the
  // user see no rows rather than secretly include everything). A fully-checked
  // group is equivalent to no filter; we detect that explicitly to skip the
  // .includes() check on the hot path.
  const categoryChecked = readCheckedValues("query-category");
  const categoryTotal = readAllValues("query-category").length;
  const topicChecked = readCheckedValues("query-topic");
  const topicTotal = readAllValues("query-topic").length;
  const engineChecked = readCheckedValues("query-engine");
  const engineTotal = readAllValues("query-engine").length;

  const categoryFilter = categoryChecked.length === categoryTotal ? null : new Set(categoryChecked);
  const topicFilter = topicChecked.length === topicTotal ? null : new Set(topicChecked);
  const engineFilter = engineChecked.length === engineTotal ? null : new Set(engineChecked);

  const bookFilter = document.getElementById("query-book").value;
  const storyFilter = document.getElementById("query-story").value;
  const minCert = Number(document.getElementById("query-min-certainty").value) || 0;

  const books = shardsToScan(bookFilter);
  await loadShardsFor(books);

  // Aggregate by (story, book, category, topic, engine) — same shape as the python query.
  const agg = new Map();
  for (const book of books) {
    for (const r of state.shardCache.get(book) || []) {
      if (categoryFilter && !categoryFilter.has(r.category)) continue;
      if (topicFilter && !topicFilter.has(r.topic)) continue;
      if (engineFilter && !engineFilter.has(r.engine)) continue;
      if (storyFilter && r.story !== storyFilter) continue;
      if (r.certainty < minCert) continue;

      const key = `${r.story}\t${r.book}\t${r.category}\t${r.topic}\t${r.engine}`;
      let bucket = agg.get(key);
      if (!bucket) {
        bucket = {
          story: r.story,
          book: r.book,
          category: r.category,
          topic: r.topic,
          engine: r.engine,
          hits: 0,
          total: 0,
          certSum: 0,
        };
        agg.set(key, bucket);
      }
      bucket.total += 1;
      if (r.answer) bucket.hits += 1;
      bucket.certSum += r.certainty || 0;
    }
  }

  const rows = Array.from(agg.values()).map((b) => ({
    ...b,
    hitRate: b.total ? b.hits / b.total : 0,
    avgCertainty: b.total ? b.certSum / b.total : 0,
  }));
  rows.sort(
    (a, b) =>
      b.hitRate - a.hitRate ||
      a.story.localeCompare(b.story) ||
      a.category.localeCompare(b.category) ||
      a.topic.localeCompare(b.topic) ||
      a.engine.localeCompare(b.engine),
  );

  const tbody = document.querySelector("#query-table tbody");
  tbody.innerHTML = rows
    .map(
      (r) => `
      <tr>
        <td>${escapeHtml(r.story)}</td>
        <td>${escapeHtml(r.book)}</td>
        <td>${escapeHtml(r.category)}</td>
        <td>${escapeHtml(r.topic)}</td>
        <td class="mono">${escapeHtml(r.engine)}</td>
        <td>${r.hits}</td>
        <td>${r.total}</td>
        <td>${Math.round(r.hitRate * 100)}%</td>
        <td>${r.avgCertainty.toFixed(0)}</td>
      </tr>`,
    )
    .join("");

  document.getElementById("query-summary").textContent =
    `${rows.length} group(s) across ${books.length} book shard(s).`;
}

// ---------- Utilities ----------

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

bootstrap();
