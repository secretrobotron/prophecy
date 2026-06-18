// Ranking tab: pick stories + ordered labels, score each story across every
// pick, threshold the intersection, and rank. Scores route through
// rankingScoreFor() / rankingCombine() in score-math.js so the visible
// numbers stay in lockstep with the Books and Hypotheses tabs.

import { state } from "./state.js";
import { escapeHtml, sortedUnique } from "./utils.js";
import { rankingCombine, rankingScoreFor } from "./score-math.js";
import { switchTab } from "./nav.js";
import { renderLabelsTree, renderLabelsPaneBody } from "./labels-tab.js";

export function renderRankingTab() {
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

export function rankingAllStoryKeys() {
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

export function renderRankingTree() {
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

export function renderRankingLabelsList() {
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

export function renderRankingLabelAddOptions() {
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

export function renderRankingResults() {
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
