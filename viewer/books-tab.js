// Books tab: per-book aggregate view. For a selected book, we sum across its
// stories to surface which (category, topic) labels show up and how strongly.
// Two presentations of the same underlying aggregation:
//   - Ranked: horizontal bars sorted by coverage (share of stories carrying
//     the label). Reads as "what does this book look like, overall?"
//   - Heatmap: stories × labels grid. Reads as "which subset of stories
//     does each label cluster on?" — the visual the user calls "layers".
// Clicking a label routes back to the Labels tab pre-filtered to that
// book + (category, topic) so the user can read the underlying prompts.

import { state } from "./state.js";
import { escapeHtml, sortStoriesCanonical, sortedUnique } from "./utils.js";
import {
  fillCheckboxList,
  readAllValues,
  readCheckedValues,
} from "./filters.js";
import { aggregateBooksLabels, storyScore } from "./score-math.js";
import {
  drillToLabels,
  drillToLabelsCell,
  drillToLabelsStory,
} from "./labels-tab.js";

export function renderBooksTab() {
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

export function renderBooksPaneBody() {
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

function renderBooksRanked(rows, stories, body) {
  const mode = state.booksScoreMode;
  const agg = aggregateBooksLabels(rows, stories.length, mode);
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
      drillToLabels(
        state.booksBookSelected,
        node.dataset.category,
        node.dataset.topic,
        state.booksEngine,
      );
    });
  }
}

function renderBooksHeatmap(rows, stories, body) {
  const mode = state.booksScoreMode;
  const agg = aggregateBooksLabels(rows, stories.length, mode);
  if (!agg.length) {
    body.innerHTML = `<div class="labels-empty">Nothing to display.</div>`;
    return;
  }
  // Column order: by ranked importance (same as view A). Row order:
  // canonical narrative order (chapter:verse of the first verse range), so
  // the user reads down the book the way it's traditionally narrated.
  const cols = agg;
  const rowsSorted = sortStoriesCanonical(stories, state.stories);
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
      drillToLabels(
        state.booksBookSelected,
        node.dataset.category,
        node.dataset.topic,
        state.booksEngine,
      );
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
        state.booksEngine,
      );
    });
  }
  // Row label click: open the existing story-detail view in Labels with all
  // labels visible.
  for (const node of body.querySelectorAll(".books-heat-rowhead")) {
    node.addEventListener("click", () => {
      drillToLabelsStory(
        state.booksBookSelected,
        node.dataset.story,
        state.booksEngine,
      );
    });
  }
}
