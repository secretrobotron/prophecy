// Prophecy Viewer — pure browser client over the static export bundle.
//
// Data layout it expects (relative to this page):
//   data/index.json          -- manifest from `prophecy export`
//   data/prompts.json
//   data/stories.json
//   data/results/<Book>.jsonl
//
// Override the root with ?data=<url> for local testing.
//
// This file is the entry point and orchestrator. The bulk of the viewer is
// split into per-tab modules (labels-tab.js, books-tab.js, ranking-tab.js,
// hypotheses-tab.js) plus shared helpers (state.js, score-math.js,
// filters.js, utils.js, nav.js). Three smaller tabs (Prompts / Responses /
// Query) are inlined here since they each fit in one screen.

import { DATA_ROOT, state } from "./state.js";
import { debounce, escapeHtml, formatWeighted } from "./utils.js";
import {
  closeAllDropdowns,
  closeAllNavMenus,
  populateFilterOptions,
  readAllValues,
  readCheckedValues,
  setAllChecked,
} from "./filters.js";
import { computeEffectiveWeights } from "./score-math.js";
import { switchTab, validTabName } from "./nav.js";
import {
  renderLabelsPaneBody,
  renderLabelsTab,
  renderLabelsTree,
} from "./labels-tab.js";
import { renderBooksPaneBody, renderBooksTab } from "./books-tab.js";
import {
  rankingAllStoryKeys,
  renderRankingLabelAddOptions,
  renderRankingLabelsList,
  renderRankingResults,
  renderRankingTab,
  renderRankingTree,
} from "./ranking-tab.js";
import { renderHypothesesTab } from "./hypotheses-tab.js";

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
    state.promptWeights = computeEffectiveWeights(prompts);
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

    // Hypotheses are optional too — pre-baked analytical frames bundled by
    // `prophecy export` when data/hypotheses/*.yml exists. The tab shows an
    // empty state when the file is absent.
    const hypothesesFile = manifest.files && manifest.files.hypotheses;
    if (hypothesesFile) {
      try {
        state.hypotheses = await fetchJson(`${DATA_ROOT}/${hypothesesFile}`);
      } catch (err) {
        console.warn(`Failed to load hypotheses file ${hypothesesFile}:`, err);
        state.hypotheses = [];
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
    renderHypothesesTab();
    bindEvents();

    // Honour the URL hash on first paint: deep-links like ?…#books open
    // straight to that tab. Unknown / empty hash leaves the markup's
    // default (Labels) selected.
    const initial = window.location.hash.replace(/^#/, "");
    if (validTabName(initial)) {
      switchTab(initial, { fromHash: true });
    } else {
      // No deep-link: switchTab never ran, so the parent nav-menu highlight
      // hasn't been computed yet. Sync it from whichever tab-button the
      // markup already has marked active.
      const active = document.querySelector(".tab-button.active");
      if (active) {
        for (const menu of document.querySelectorAll(".nav-menu")) {
          menu.classList.toggle("active", menu.contains(active));
        }
      }
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

// ---------- Event wiring ----------

function bindEvents() {
  for (const btn of document.querySelectorAll(".tab-button")) {
    btn.addEventListener("click", () => {
      switchTab(btn.dataset.tab);
      closeAllNavMenus();
    });
  }

  // Top-bar grouping dropdowns (Analysis / Explore / Data). Only one open at
  // a time; clicks inside the panel itself don't bubble up to the document
  // close handler.
  for (const menu of document.querySelectorAll(".nav-menu")) {
    const toggle = menu.querySelector(".nav-menu-toggle");
    const panel = menu.querySelector(".nav-menu-panel");
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const willOpen = panel.hasAttribute("hidden");
      closeAllNavMenus();
      closeAllDropdowns();
      if (willOpen) {
        panel.removeAttribute("hidden");
        toggle.setAttribute("aria-expanded", "true");
      }
    });
    panel.addEventListener("click", (e) => e.stopPropagation());
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

  // Click anywhere else: close any open dropdown / nav menu.
  document.addEventListener("click", () => {
    closeAllDropdowns();
    closeAllNavMenus();
  });
  // Escape: close any open dropdown / nav menu.
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllDropdowns();
      closeAllNavMenus();
    }
  });

  // Responses tab loads its shards lazily on activation. nav.js fires
  // "tab:switch" rather than calling renderers directly so it can stay
  // dependency-free.
  document.addEventListener("tab:switch", (e) => {
    if (e.detail && e.detail.name === "responses") renderResponses();
  });
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
      // Explicit weight only — blank cell stays a dash so users can tell
      // "no weight set" apart from "weight set to 1" (only the second
      // signals an authored decision; the first inherits the uniform
      // fallback that kicks in when nobody in the topic is weighted).
      const hasWeight = p.weight !== null && p.weight !== undefined && p.weight !== "";
      const weightCell = hasWeight
        ? `<span class="mono">${p.weight}</span>`
        : `<span class="muted">—</span>`;
      return `
      <tr>
        <td class="mono">${escapeHtml(p.id)}</td>
        <td>${escapeHtml(p.category)}</td>
        <td>${escapeHtml(p.topic)}</td>
        <td>${escapeHtml(p.prompt)}</td>
        <td>${weightCell}</td>
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

  // Build an explicit-weight lookup from the loaded prompts catalog. Blank
  // / missing means "no weight authored" — render as an em-dash so it reads
  // distinctly from an explicit weight of 1.
  const explicitWeight = {};
  for (const p of state.prompts) {
    const has = p.weight !== null && p.weight !== undefined && p.weight !== "";
    explicitWeight[p.id] = has ? p.weight : null;
  }

  const tbody = document.querySelector("#responses-table tbody");
  tbody.innerHTML = matched
    .slice(0, cap)
    .map((r) => {
      const w = explicitWeight[r.prompt];
      const weightCell =
        w == null ? `<span class="muted">—</span>` : `<span class="mono">${w}</span>`;
      return `
      <tr>
        <td>${escapeHtml(r.story)}</td>
        <td>${escapeHtml(r.book)}</td>
        <td class="mono">${escapeHtml(r.prompt)}</td>
        <td>${escapeHtml(r.category)}</td>
        <td>${escapeHtml(r.topic)}</td>
        <td class="mono">${escapeHtml(r.engine)}</td>
        <td class="${r.answer ? "bool-true" : "bool-false"}">${r.answer ? "true" : "false"}</td>
        <td>${r.certainty}</td>
        <td>${weightCell}</td>
        <td class="reason">${escapeHtml(r.reason || "")}</td>
      </tr>`;
    })
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
          promptCount: 0,
          certSum: 0,
        };
        agg.set(key, bucket);
      }
      // Synthetic ids (concat:*) and prompts dropped from the catalog fall
      // back to weight 1.0 — same policy as the python aggregator.
      const w = state.promptWeights[r.prompt] ?? 1.0;
      bucket.promptCount += 1;
      bucket.total += w;
      if (r.answer) bucket.hits += w;
      bucket.certSum += w * (r.certainty || 0);
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
        <td>${formatWeighted(r.hits)}</td>
        <td>${formatWeighted(r.total)}</td>
        <td>${r.promptCount}</td>
        <td>${Math.round(r.hitRate * 100)}%</td>
        <td>${r.avgCertainty.toFixed(0)}</td>
      </tr>`,
    )
    .join("");

  document.getElementById("query-summary").textContent =
    `${rows.length} group(s) across ${books.length} book shard(s).`;
}

bootstrap();
