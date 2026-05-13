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
  shardCache: new Map(), // book -> rows[]
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

    const usedCount = (manifest.used_prompt_ids || []).length;
    document.getElementById("manifest-summary").textContent =
      `${manifest.total_results.toLocaleString()} results, ${manifest.books.length} books, ` +
      `${usedCount} of ${prompts.length} prompts used, ` +
      `${manifest.engines.length} engine(s) — generated ${manifest.generated_at}`;
    document.getElementById("data-source").textContent =
      `Data root: ${DATA_ROOT}`;

    populateFilterOptions();
    renderPrompts();
    bindEvents();
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
  const allPromptPeriods = sortedUnique(state.prompts.map((p) => p.period));
  const allPromptTopics = sortedUnique(state.prompts.map((p) => p.topic));
  fillSelect("prompts-period", allPromptPeriods);
  fillSelect("prompts-topic", allPromptTopics);

  // Query/Responses tabs reflect the cached data only (manifest facets).
  const stories = m.stories || [];
  fillSelect("responses-book", m.books);
  fillSelect("responses-story", stories);
  fillSelect("responses-period", m.periods);
  fillSelect("responses-topic", m.topics);
  fillSelect("responses-engine", m.engines);

  fillSelect("query-book", m.books);
  fillSelect("query-story", stories);

  // Multi-select checkbox lists on the Query tab. Default to all-checked so
  // an unconfigured query returns everything.
  fillCheckboxList("query-period", m.periods, true);
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

  document.getElementById("prompts-period").addEventListener("change", renderPrompts);
  document.getElementById("prompts-topic").addEventListener("change", renderPrompts);
  document.getElementById("prompts-search").addEventListener("input", debounce(renderPrompts, 150));

  for (const id of [
    "responses-book",
    "responses-story",
    "responses-period",
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

  // All/none buttons inside multi-select panels.
  for (const btn of document.querySelectorAll(".multi-actions button")) {
    btn.addEventListener("click", () => {
      const target = btn.dataset.target;
      const action = btn.dataset.action;
      setAllChecked(target, action === "all");
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

function switchTab(name) {
  for (const btn of document.querySelectorAll(".tab-button")) {
    btn.classList.toggle("active", btn.dataset.tab === name);
  }
  for (const panel of document.querySelectorAll(".tab-panel")) {
    panel.classList.toggle("active", panel.id === `tab-${name}`);
  }
  if (name === "responses") renderResponses();
}

// ---------- Prompts tab ----------

function renderPrompts() {
  const period = document.getElementById("prompts-period").value;
  const topic = document.getElementById("prompts-topic").value;
  const search = document.getElementById("prompts-search").value.toLowerCase();

  const rows = state.prompts.filter((p) => {
    if (period && p.period !== period) return false;
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
        <td>${escapeHtml(p.period)}</td>
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
  const filterPeriod = document.getElementById("responses-period").value;
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
      if (filterPeriod && r.period !== filterPeriod) continue;
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
        <td>${escapeHtml(r.period)}</td>
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
  const periodChecked = readCheckedValues("query-period");
  const periodTotal = readAllValues("query-period").length;
  const topicChecked = readCheckedValues("query-topic");
  const topicTotal = readAllValues("query-topic").length;
  const engineChecked = readCheckedValues("query-engine");
  const engineTotal = readAllValues("query-engine").length;

  const periodFilter = periodChecked.length === periodTotal ? null : new Set(periodChecked);
  const topicFilter = topicChecked.length === topicTotal ? null : new Set(topicChecked);
  const engineFilter = engineChecked.length === engineTotal ? null : new Set(engineChecked);

  const bookFilter = document.getElementById("query-book").value;
  const storyFilter = document.getElementById("query-story").value;
  const minCert = Number(document.getElementById("query-min-certainty").value) || 0;

  const books = shardsToScan(bookFilter);
  await loadShardsFor(books);

  // Aggregate by (story, book, period, topic, engine) — same shape as the python query.
  const agg = new Map();
  for (const book of books) {
    for (const r of state.shardCache.get(book) || []) {
      if (periodFilter && !periodFilter.has(r.period)) continue;
      if (topicFilter && !topicFilter.has(r.topic)) continue;
      if (engineFilter && !engineFilter.has(r.engine)) continue;
      if (storyFilter && r.story !== storyFilter) continue;
      if (r.certainty < minCert) continue;

      const key = `${r.story}\t${r.book}\t${r.period}\t${r.topic}\t${r.engine}`;
      let bucket = agg.get(key);
      if (!bucket) {
        bucket = {
          story: r.story,
          book: r.book,
          period: r.period,
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
      a.period.localeCompare(b.period) ||
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
        <td>${escapeHtml(r.period)}</td>
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
