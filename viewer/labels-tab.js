// Labels tab: a per-book / per-story browser over the bundled labels.json.
// Also owns the drill-into-Labels helpers other tabs call to land users in
// the right book/story/filter combo.

import { state } from "./state.js";
import { escapeHtml, formatWeighted, sortedUnique } from "./utils.js";
import {
  fillCheckboxList,
  readAllValues,
  readCheckedValues,
  setAllChecked,
  setSingleChecked,
} from "./filters.js";
import { avgCertainty } from "./score-math.js";
import { switchTab } from "./nav.js";

// Derived display values aren't persisted in labels.json — they're computed
// from sufficient stats on every render via avgCertainty(). One decimal
// matches the precision Python's CLI used to ship for avg_certainty.
function fmtCert(row) {
  return avgCertainty(row).toFixed(1);
}

export function renderLabelsTab() {
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

export function renderLabelsTree() {
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

export function renderLabelsPaneBody() {
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
          const hitsStr = formatWeighted(l.hits);
          const totalStr = formatWeighted(l.total);
          const nStr = l.prompt_count != null ? ` of ${l.prompt_count}` : "";
          return `<span class="${cls}" data-category="${escapeHtml(l.category)}"
                   title="${escapeHtml(l.topic)}:${escapeHtml(l.category)} — ${hitsStr}/${totalStr}${nStr} (avg ${fmtCert(l)})">
              ${escapeHtml(l.topic)}
              <span class="label-chip-score">${hitsStr}/${totalStr}</span>
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
          <div>${formatWeighted(l.hits)} / ${formatWeighted(l.total)}${l.prompt_count != null ? ` <span class="muted">(n=${l.prompt_count})</span>` : ""} · avg cert ${fmtCert(l)}</div>
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
        ${p.weight != null && p.weight !== 1 ? `<span class="prompt-weight" title="weight ${p.weight}">w${formatWeighted(p.weight)}</span>` : ""}
        <span class="prompt-cert">${p.certainty}</span>
      </summary>
      ${reasonBlock}
    </details>
  </li>`;
}

// Drill into Labels filtered to one (category, topic) for a book. Selects
// the book in the Labels tree, expands it, and narrows the multi-selects to
// just the target so the right pane shows that label's cards.
export function drillToLabels(book, category, topic, engine) {
  state.labelsBookSelected = book;
  state.labelsStorySelected = null;
  state.labelsBookExpanded.add(book);
  // Mirror engine selection so the drill is consistent with what was visible.
  if (engine) {
    state.labelsEngine = engine;
    document.getElementById("labels-engine").value = engine;
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
export function drillToLabelsCell(book, story, category, topic, engine) {
  state.labelsBookSelected = book;
  state.labelsStorySelected = story;
  state.labelsBookExpanded.add(book);
  if (engine) {
    state.labelsEngine = engine;
    document.getElementById("labels-engine").value = engine;
  }
  setSingleChecked("labels-category", category);
  setSingleChecked("labels-topic", topic);
  switchTab("labels");
  renderLabelsTree();
  renderLabelsPaneBody();
}

// Drill into Labels at the story-detail view for one story in a book.
export function drillToLabelsStory(book, story, engine) {
  state.labelsBookSelected = book;
  state.labelsStorySelected = story;
  state.labelsBookExpanded.add(book);
  if (engine) {
    state.labelsEngine = engine;
    document.getElementById("labels-engine").value = engine;
  }
  // Don't narrow category/topic here — when reading a single story the user
  // usually wants the full label spread.
  setAllChecked("labels-category", true);
  setAllChecked("labels-topic", true);
  switchTab("labels");
  renderLabelsTree();
  renderLabelsPaneBody();
}
