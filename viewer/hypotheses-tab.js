// Hypotheses tab: pre-baked analytical frames bundled by `prophecy export`
// from data/hypotheses/*.yml. Each hypothesis names a slice (by source tag
// and/or book), one or two label "buckets" (single bucket = confirmatory,
// A vs B = comparative), and a thesis statement. The viewer reads the
// bundle and presents a gallery: pick a hypothesis on the left, see its
// verdict, per-engine spread, per-story evidence, heatmap, exemplars,
// counter-evidence, and notes on the right.
//
// All scoring reuses storyScore()/hypBucketScore()/hypTopExemplar() from
// score-math.js so the Hypotheses verdicts can't drift from what users see
// in the Books or Ranking tabs.

import { state } from "./state.js";
import {
  escapeHtml,
  sortStoriesCanonical,
  sortedUnique,
} from "./utils.js";
import { setAllChecked, updateDropdownSummary } from "./filters.js";
import {
  allLabeledStories,
  hypBucketScore,
  hypTopExemplar,
  meanOver,
  storyScore,
} from "./score-math.js";
import { switchTab } from "./nav.js";
import {
  drillToLabelsCell,
  drillToLabelsStory,
  renderLabelsPaneBody,
  renderLabelsTree,
} from "./labels-tab.js";

export function renderHypothesesTab() {
  if (!state.hypotheses.length) {
    document.getElementById("hyp-list").innerHTML = "";
    document.getElementById("hyp-report").innerHTML =
      `<div class="hyp-empty">
        No hypotheses bundled. Author <code>data/hypotheses/*.yml</code> files and re-run
        <code>python -m prophecy export</code>.
      </div>`;
    return;
  }
  // Default selection: first hypothesis. Sticky across re-renders so changing
  // a knob doesn't yank the user back to the top of the list.
  if (
    !state.hypothesisSelected ||
    !state.hypotheses.some((h) => h.id === state.hypothesisSelected)
  ) {
    state.hypothesisSelected = state.hypotheses[0].id;
    // Inherit the author's default scoring on first open of a hypothesis.
    const defScoring = state.hypotheses[0].default_scoring;
    if (defScoring) state.hypScoreMode = defScoring;
  }
  renderHypothesesList();
  renderHypothesisReport();
}

function renderHypothesesList() {
  const root = document.getElementById("hyp-list");
  root.innerHTML = state.hypotheses
    .map((h) => {
      const active = h.id === state.hypothesisSelected ? " active" : "";
      const slice = h.slice || {};
      const sliceBits = [];
      if (slice.sources && slice.sources.length) sliceBits.push(slice.sources.join("+"));
      if (slice.books && slice.books.length) sliceBits.push(slice.books.join("/"));
      const sliceText = sliceBits.length ? sliceBits.join(" · ") : "all";
      return `<li class="hyp-list-item${active}" data-id="${escapeHtml(h.id)}">
          <div class="hyp-list-title">${escapeHtml(h.title)}</div>
          <div class="hyp-list-meta">
            <span class="hyp-mode-chip">${escapeHtml(h.mode)}</span>
            <span>${escapeHtml(sliceText)}</span>
          </div>
        </li>`;
    })
    .join("");
  for (const node of root.querySelectorAll(".hyp-list-item")) {
    node.addEventListener("click", () => {
      if (state.hypothesisSelected === node.dataset.id) return;
      state.hypothesisSelected = node.dataset.id;
      const hyp = state.hypotheses.find((h) => h.id === node.dataset.id);
      if (hyp && hyp.default_scoring) state.hypScoreMode = hyp.default_scoring;
      renderHypothesesList();
      renderHypothesisReport();
    });
  }
}

// Stories matching the hypothesis's slice — the universe of evidence the
// rest of the report operates over. Only stories with at least one label row
// are eligible, because anything else would just render as a hole.
function hypSliceStories(hyp) {
  const slice = hyp.slice || {};
  const wantSources = new Set(slice.sources || []);
  const wantBooks = new Set(slice.books || []);
  const universe = new Map();
  for (const l of state.labels) {
    if (!universe.has(l.story)) universe.set(l.story, l.book);
  }
  const out = [];
  for (const [story, book] of universe) {
    if (wantBooks.size && !wantBooks.has(book)) continue;
    if (wantSources.size) {
      const meta = state.stories[story] || {};
      const srcs = meta.sources || [];
      if (!srcs.some((s) => wantSources.has(s))) continue;
    }
    out.push({ book, story });
  }
  // Canonical narrative order so reading down the report follows the text.
  const ordered = sortStoriesCanonical(out.map((p) => p.story), state.stories);
  const byStory = new Map(out.map((p) => [p.story, p]));
  return ordered.map((s) => byStory.get(s));
}

function renderHypothesisReport() {
  const body = document.getElementById("hyp-report");
  const hyp = state.hypotheses.find((h) => h.id === state.hypothesisSelected);
  if (!hyp) {
    body.innerHTML = `<div class="hyp-empty">No hypothesis selected.</div>`;
    return;
  }

  const slice = hypSliceStories(hyp);
  const isCompare = hyp.mode === "compare";

  const sliceBits = [];
  const sl = hyp.slice || {};
  if (sl.sources && sl.sources.length) sliceBits.push(`sources: ${sl.sources.join(", ")}`);
  if (sl.books && sl.books.length) sliceBits.push(`books: ${sl.books.join(", ")}`);
  sliceBits.push(`${slice.length} stor${slice.length === 1 ? "y" : "ies"}`);

  const engines = sortedUnique(state.labels.map((l) => l.engine));
  const engineOptions = [
    `<option value="">(all engines, mean)</option>`,
    ...engines.map(
      (e) =>
        `<option value="${escapeHtml(e)}"${e === state.hypEngine ? " selected" : ""}>${escapeHtml(e)}</option>`,
    ),
  ].join("");

  const tagsHtml = (hyp.tags || [])
    .map((t) => `<span class="hyp-slice-chip">${escapeHtml(t)}</span>`)
    .join("");

  // Empty-slice case: render the header but skip computation so the user
  // sees *why* there's nothing to score (no stories matched).
  if (!slice.length) {
    body.innerHTML = `
      <section class="hyp-header">
        <h2>${escapeHtml(hyp.title)}</h2>
        <div class="hyp-header-meta">
          <span class="hyp-mode-chip">${escapeHtml(hyp.mode)}</span>
          ${tagsHtml}
          ${sliceBits.map((b) => `<span>${escapeHtml(b)}</span>`).join(" · ")}
        </div>
        <p class="hyp-thesis">${escapeHtml(hyp.thesis || "")}</p>
      </section>
      <div class="hyp-empty">No stories in the labelled corpus match this slice.</div>`;
    return;
  }

  const verdictHtml = isCompare
    ? renderHypVerdictCompare(hyp, slice)
    : renderHypVerdictConfirm(hyp, slice);
  const enginesHtml = renderHypEnginesStrip(hyp, slice, engines);
  const scorecardHtml = renderHypScorecard(hyp, slice);
  const heatmapHtml = renderHypHeatmap(hyp, slice);
  const exemplarsHtml = renderHypExemplars(hyp, slice);

  body.innerHTML = `
    <section class="hyp-header">
      <h2>${escapeHtml(hyp.title)}</h2>
      <div class="hyp-header-meta">
        <span class="hyp-mode-chip">${escapeHtml(hyp.mode)}</span>
        ${tagsHtml}
        ${sliceBits.map((b) => `<span>${escapeHtml(b)}</span>`).join(" · ")}
      </div>
      <p class="hyp-thesis">${escapeHtml(hyp.thesis || "")}</p>
    </section>

    <div class="hyp-toolbar" id="hyp-toolbar">
      <label>Engine
        <select id="hyp-engine">${engineOptions}</select>
      </label>
      <label>Score
        <select id="hyp-score-mode" title="Weighted: hit_rate × avg_certainty (product of two prompt-weighted means: Σw·a/Σw and Σw·c/Σw). Coupled: Σw·a·c/Σw/100 — each yes contributes its own certainty per prompt, so confidently-wrong noes don't inflate the score the way they can under Weighted.">
          <option value="weighted"${state.hypScoreMode === "weighted" ? " selected" : ""}>Weighted score</option>
          <option value="coupled"${state.hypScoreMode === "coupled" ? " selected" : ""}>Coupled weighted</option>
          <option value="hit"${state.hypScoreMode === "hit" ? " selected" : ""}>Hit rate</option>
          <option value="coverage"${state.hypScoreMode === "coverage" ? " selected" : ""}>Coverage</option>
        </select>
      </label>
      <label>Min score
        <input type="number" id="hyp-min-cert" min="0" max="100" step="5" value="${state.hypMinCert}" />
      </label>
      <label>
        <input type="checkbox" id="hyp-counter-first"${state.hypCounterFirst ? " checked" : ""} />
        Counter-evidence first
      </label>
    </div>

    <section class="hyp-section">
      <h3>Verdict</h3>
      ${verdictHtml}
    </section>

    <section class="hyp-section">
      <h3>By engine</h3>
      <div class="hyp-section-sub">One row per engine in the labels file — watch for verdicts that flip between models.</div>
      ${enginesHtml}
    </section>

    <section class="hyp-section">
      <h3>By story</h3>
      <div class="hyp-section-sub">Click a row to open the underlying labels in the Labels tab.</div>
      ${scorecardHtml}
    </section>

    <section class="hyp-section">
      <h3>Heatmap</h3>
      ${heatmapHtml}
    </section>

    <section class="hyp-section">
      <h3>Exemplars</h3>
      ${exemplarsHtml}
    </section>

    ${
      hyp.notes
        ? `<section class="hyp-section">
            <h3>Notes</h3>
            <div class="hyp-notes">${escapeHtml(hyp.notes)}</div>
          </section>`
        : ""
    }
  `;

  // Toolbar handlers — re-render the whole report so every section stays in
  // sync. Cheap because slice + scoring are pure functions over state.labels.
  document.getElementById("hyp-engine").addEventListener("change", (e) => {
    state.hypEngine = e.target.value;
    renderHypothesisReport();
  });
  document.getElementById("hyp-score-mode").addEventListener("change", (e) => {
    state.hypScoreMode = e.target.value;
    renderHypothesisReport();
  });
  document.getElementById("hyp-min-cert").addEventListener("input", (e) => {
    state.hypMinCert = Number(e.target.value) || 0;
    renderHypothesisReport();
  });
  document.getElementById("hyp-counter-first").addEventListener("change", (e) => {
    state.hypCounterFirst = e.target.checked;
    renderHypothesisReport();
  });

  // Scorecard rows → drill into Labels for that story.
  for (const node of body.querySelectorAll(".hyp-scorecard-row")) {
    node.addEventListener("click", () => {
      drillToLabelsStory(node.dataset.book, node.dataset.story, state.hypEngine);
    });
  }
  // Exemplar story names → same drill, but narrowed to the bucket's topics
  // so the user lands on the prompts that drove the exemplar score.
  for (const node of body.querySelectorAll(".hyp-exemplar-story")) {
    node.addEventListener("click", () => {
      const book = node.dataset.book;
      const story = node.dataset.story;
      const topicsCsv = node.dataset.topics;
      const topics = topicsCsv ? topicsCsv.split("|") : [];
      drillToLabelsStoryNarrowedTopics(book, story, topics);
    });
  }
  // Heatmap cell clicks: same drill as the Books heatmap.
  for (const node of body.querySelectorAll(".hyp-heat-cell")) {
    node.addEventListener("click", () => {
      drillToLabelsCell(
        node.dataset.book,
        node.dataset.story,
        node.dataset.category,
        node.dataset.topic,
        state.hypEngine,
      );
    });
  }
}

function renderHypVerdictCompare(hyp, slice) {
  const a = hyp.buckets.A;
  const b = hyp.buckets.B;
  const aMean = meanOver(slice, (s) =>
    hypBucketScore(s.book, s.story, a, state.hypEngine, state.hypScoreMode),
  );
  const bMean = meanOver(slice, (s) =>
    hypBucketScore(s.book, s.story, b, state.hypEngine, state.hypScoreMode),
  );
  const aPct = Math.round(aMean * 100);
  const bPct = Math.round(bMean * 100);
  const delta = aMean - bMean;
  const leader = delta > 0.02 ? a.label : delta < -0.02 ? b.label : null;
  const summary = leader
    ? `<strong>${escapeHtml(leader)}</strong> leads by ${Math.round(Math.abs(delta) * 100)}% across ${slice.length} stor${slice.length === 1 ? "y" : "ies"}.`
    : `<strong>No clear lead</strong> — both buckets within 2% across ${slice.length} stor${slice.length === 1 ? "y" : "ies"}.`;
  return `
    <div class="hyp-verdict">
      <div class="hyp-verdict-bars">
        <div class="hyp-verdict-bucket">${escapeHtml(a.label)}</div>
        <div class="hyp-verdict-track">
          <div class="hyp-verdict-fill bucket-a" style="width:${aPct}%"></div>
        </div>
        <div class="hyp-verdict-pct">${aPct}%</div>

        <div class="hyp-verdict-bucket">${escapeHtml(b.label)}</div>
        <div class="hyp-verdict-track">
          <div class="hyp-verdict-fill bucket-b" style="width:${bPct}%"></div>
        </div>
        <div class="hyp-verdict-pct">${bPct}%</div>
      </div>
      <div class="hyp-verdict-summary">${summary}</div>
    </div>`;
}

function renderHypVerdictConfirm(hyp, slice) {
  const a = hyp.buckets.A;
  const aMean = meanOver(slice, (s) =>
    hypBucketScore(s.book, s.story, a, state.hypEngine, state.hypScoreMode),
  );
  const aPct = Math.round(aMean * 100);
  // Baseline: same buckets, but over every labelled story regardless of
  // slice. Lets the user see "is this slice elevated vs. the whole canon?"
  const baseline = meanOver(allLabeledStories(), (s) =>
    hypBucketScore(s.book, s.story, a, state.hypEngine, state.hypScoreMode),
  );
  const basePct = Math.round(baseline * 100);
  const delta = aPct - basePct;
  const sign = delta >= 0 ? "+" : "";
  const summary = `<strong>${escapeHtml(a.label)}</strong> averages ${aPct}% across the slice
    <span class="muted">(canon baseline: ${basePct}%, <span class="mono">${sign}${delta}pp</span>)</span>.`;
  return `
    <div class="hyp-verdict">
      <div class="hyp-verdict-bars">
        <div class="hyp-verdict-bucket">${escapeHtml(a.label)}</div>
        <div class="hyp-verdict-track">
          <div class="hyp-verdict-fill bucket-a" style="width:${aPct}%"></div>
        </div>
        <div class="hyp-verdict-pct">${aPct}%</div>

        <div class="hyp-verdict-bucket muted">canon</div>
        <div class="hyp-verdict-track">
          <div class="hyp-verdict-fill" style="width:${basePct}%;background:var(--muted)"></div>
        </div>
        <div class="hyp-verdict-pct muted">${basePct}%</div>
      </div>
      <div class="hyp-verdict-summary">${summary}</div>
    </div>`;
}

function renderHypEnginesStrip(hyp, slice, engines) {
  if (!engines.length) return `<div class="muted">No engines in labels.</div>`;
  const isCompare = hyp.mode === "compare";
  const rows = engines
    .map((eng) => {
      const a = meanOver(slice, (s) =>
        hypBucketScore(s.book, s.story, hyp.buckets.A, eng, state.hypScoreMode),
      );
      if (isCompare) {
        const b = meanOver(slice, (s) =>
          hypBucketScore(s.book, s.story, hyp.buckets.B, eng, state.hypScoreMode),
        );
        const aPct = Math.round(a * 100);
        const bPct = Math.round(b * 100);
        // Render two half-bars meeting in the middle. Bucket-A pushes left
        // from center, Bucket-B pushes right — visual rhythm matches the
        // verdict's compare framing.
        return `<div class="hyp-engine-row">
          <span class="hyp-engine-name" title="${escapeHtml(eng)}">${escapeHtml(eng)}</span>
          <div class="hyp-engine-track diverge">
            <div class="hyp-engine-fill-a" style="right:50%;width:${aPct / 2}%"></div>
            <div class="hyp-engine-fill-b" style="left:50%;width:${bPct / 2}%"></div>
          </div>
          <span class="hyp-engine-pct">${aPct} / ${bPct}</span>
        </div>`;
      }
      const aPct = Math.round(a * 100);
      return `<div class="hyp-engine-row">
        <span class="hyp-engine-name" title="${escapeHtml(eng)}">${escapeHtml(eng)}</span>
        <div class="hyp-engine-track">
          <div class="hyp-engine-fill-a" style="left:0;width:${aPct}%"></div>
        </div>
        <span class="hyp-engine-pct">${aPct}%</span>
      </div>`;
    })
    .join("");
  return `<div class="hyp-engines">${rows}</div>`;
}

function renderHypScorecard(hyp, slice) {
  const isCompare = hyp.mode === "compare";
  const items = slice.map(({ book, story }) => {
    const a = hypBucketScore(book, story, hyp.buckets.A, state.hypEngine, state.hypScoreMode);
    const b = isCompare
      ? hypBucketScore(book, story, hyp.buckets.B, state.hypEngine, state.hypScoreMode)
      : 0;
    return { book, story, a, b, delta: a - b };
  });
  // Counter-evidence: compare = B wins; confirm = A is weak.
  const isCounter = isCompare
    ? (r) => r.b > r.a + 0.02
    : (r) => r.a < 0.15;
  if (state.hypCounterFirst) {
    items.sort((x, y) => {
      const xc = isCounter(x) ? 0 : 1;
      const yc = isCounter(y) ? 0 : 1;
      if (xc !== yc) return xc - yc;
      return x.story.localeCompare(y.story);
    });
  }
  const rows = items
    .map((r) => {
      const aPct = Math.round(r.a * 100);
      const bPct = Math.round(r.b * 100);
      const counterCls = isCounter(r) ? " is-counter" : "";
      if (isCompare) {
        return `<div class="hyp-scorecard-row${counterCls}" data-book="${escapeHtml(r.book)}" data-story="${escapeHtml(r.story)}">
          <span class="hyp-scorecard-story" title="${escapeHtml(r.story)}">${escapeHtml(r.story)}</span>
          <div class="hyp-scorecard-track diverge">
            <div class="hyp-scorecard-fill-a" style="right:50%;width:${aPct / 2}%"></div>
            <div class="hyp-scorecard-fill-b" style="left:50%;width:${bPct / 2}%"></div>
          </div>
          <span class="hyp-scorecard-pct">${aPct} / ${bPct}</span>
        </div>`;
      }
      return `<div class="hyp-scorecard-row${counterCls}" data-book="${escapeHtml(r.book)}" data-story="${escapeHtml(r.story)}">
        <span class="hyp-scorecard-story" title="${escapeHtml(r.story)}">${escapeHtml(r.story)}</span>
        <div class="hyp-scorecard-track">
          <div class="hyp-scorecard-fill-a" style="left:0;width:${aPct}%"></div>
        </div>
        <span class="hyp-scorecard-pct">${aPct}%</span>
      </div>`;
    })
    .join("");
  return `<div class="hyp-scorecard">${rows}</div>`;
}

function renderHypHeatmap(hyp, slice) {
  // Columns: every (category, topic) pair across both buckets. Group
  // headers by bucket so the user can read "left half of the row =
  // bucket A; right half = bucket B". Reuse the Books heatmap classes so
  // the cell palette is consistent across the viewer.
  const bucketEntries = Object.entries(hyp.buckets || {});
  // For each topic find its category from the labels file (a topic always
  // belongs to one category in the prompts.tsv — first match wins).
  const topicCategory = new Map();
  for (const l of state.labels) {
    if (!topicCategory.has(l.topic)) topicCategory.set(l.topic, l.category);
  }
  // Build the column list, preserving bucket order.
  const cols = [];
  for (const [bucketKey, bucket] of bucketEntries) {
    for (const topic of bucket.topics || []) {
      cols.push({
        bucketKey,
        bucketLabel: bucket.label,
        topic,
        category: topicCategory.get(topic) || "",
      });
    }
  }
  if (!cols.length || !slice.length) {
    return `<div class="muted">Nothing to plot.</div>`;
  }

  // Cell value: storyScore for the (story, topic) cell, restricted to engine.
  // Same intensity bucketing as the Books heatmap.
  const cellByKey = new Map();
  for (const l of state.labels) {
    if (state.hypEngine && l.engine !== state.hypEngine) continue;
    const key = `${l.story}\t${l.topic}`;
    const score = storyScore(l, state.hypScoreMode);
    const prev = cellByKey.get(key) || 0;
    cellByKey.set(key, Math.max(prev, score));
  }

  // Group header rows: bucket spans, then per-topic columns. Render two
  // header rows so the bucket grouping is visually unmissable.
  const bucketSpans = bucketEntries.map(([, b]) => (b.topics || []).length);
  const groupHeaderCells = bucketEntries
    .map(
      ([key, b], i) =>
        `<th class="books-heat-colhead" colspan="${bucketSpans[i]}" style="text-align:center">
          <div class="books-heat-coltag bucket-${escapeHtml(key)}">${escapeHtml(b.label)}</div>
        </th>`,
    )
    .join("");
  const topicHeaderCells = cols
    .map(
      (c) => `<th class="books-heat-colhead" data-category="${escapeHtml(c.category)}" data-topic="${escapeHtml(c.topic)}">
        <div class="books-heat-coltag" data-category="${escapeHtml(c.category)}">${escapeHtml(c.category)}</div>
        <div class="books-heat-coltopic">${escapeHtml(c.topic)}</div>
      </th>`,
    )
    .join("");

  const bodyRows = slice
    .map(({ book, story }) => {
      const cells = cols
        .map((c) => {
          const score = cellByKey.get(`${story}\t${c.topic}`) || 0;
          const pct = Math.round(score * 100);
          let intensity = "i0";
          if (pct >= 75) intensity = "i4";
          else if (pct >= 50) intensity = "i3";
          else if (pct >= 25) intensity = "i2";
          else if (pct > 0) intensity = "i1";
          const title = pct > 0
            ? `${escapeHtml(story)} — ${escapeHtml(c.topic)}: ${pct}% (click to open the underlying prompts)`
            : `${escapeHtml(story)} — no hit on ${escapeHtml(c.topic)}`;
          return `<td class="books-heat-cell hyp-heat-cell ${intensity}"
            data-book="${escapeHtml(book)}"
            data-story="${escapeHtml(story)}"
            data-category="${escapeHtml(c.category)}"
            data-topic="${escapeHtml(c.topic)}"
            title="${title}"></td>`;
        })
        .join("");
      return `<tr><th class="books-heat-rowhead">${escapeHtml(story)}</th>${cells}</tr>`;
    })
    .join("");

  return `<div class="hyp-heat-wrap"><table class="books-heat">
    <thead>
      <tr><th></th>${groupHeaderCells}</tr>
      <tr><th></th>${topicHeaderCells}</tr>
    </thead>
    <tbody>${bodyRows}</tbody>
  </table></div>`;
}

function renderHypExemplars(hyp, slice) {
  const isCompare = hyp.mode === "compare";
  const cards = [];
  for (const [, bucket] of Object.entries(hyp.buckets)) {
    const ex = hypTopExemplar(slice, bucket, state.hypEngine, state.hypScoreMode);
    const heading = `Top "${bucket.label}"`;
    if (!ex) {
      cards.push(`<div class="hyp-exemplar-card">
        <h4>${escapeHtml(heading)}</h4>
        <div class="muted">No story scored above zero.</div>
      </div>`);
      continue;
    }
    const topicsAttr = (bucket.topics || []).join("|");
    const promptText = ex.prompt
      ? `<div class="hyp-exemplar-prompt">"${escapeHtml(ex.prompt.prompt)}"</div>`
      : "";
    const promptMeta = ex.prompt
      ? `#${escapeHtml(ex.prompt.id)} · cert ${ex.prompt.certainty}`
      : "—";
    cards.push(`<div class="hyp-exemplar-card">
      <h4>${escapeHtml(heading)}</h4>
      <div class="hyp-exemplar-story"
           data-book="${escapeHtml(ex.book)}"
           data-story="${escapeHtml(ex.story)}"
           data-topics="${escapeHtml(topicsAttr)}">${escapeHtml(ex.story)}</div>
      ${promptText}
      <div class="hyp-exemplar-score">score ${(ex.score * 100).toFixed(0)}% · ${promptMeta}</div>
    </div>`);
  }
  // Counter-evidence card — only meaningful in compare mode (the single
  // weakest A story is symmetric with the strongest B story already shown,
  // so the extra card would be redundant noise in confirm).
  if (isCompare) {
    const items = slice
      .map(({ book, story }) => {
        const a = hypBucketScore(book, story, hyp.buckets.A, state.hypEngine, state.hypScoreMode);
        const b = hypBucketScore(book, story, hyp.buckets.B, state.hypEngine, state.hypScoreMode);
        return { book, story, a, b, delta: a - b };
      })
      .filter((r) => r.b > r.a + 0.02)
      .sort((x, y) => y.b - y.a - (x.b - x.a));
    if (items.length) {
      const top = items[0];
      cards.push(`<div class="hyp-exemplar-card">
        <h4>Strongest counter-evidence</h4>
        <div class="hyp-exemplar-story"
             data-book="${escapeHtml(top.book)}"
             data-story="${escapeHtml(top.story)}"
             data-topics="">${escapeHtml(top.story)}</div>
        <div class="hyp-exemplar-prompt">${escapeHtml(hyp.buckets.B.label)} outscores ${escapeHtml(hyp.buckets.A.label)} here.</div>
        <div class="hyp-exemplar-score">A ${(top.a * 100).toFixed(0)}% vs B ${(top.b * 100).toFixed(0)}%</div>
      </div>`);
    }
  }
  return `<div class="hyp-exemplars">${cards.join("")}</div>`;
}

// Same shape as drillToLabelsStory but narrows the topic multi-select to the
// bucket's topic set so the user lands on the prompts behind the exemplar
// score (instead of every label the story carries).
function drillToLabelsStoryNarrowedTopics(book, story, topics) {
  state.labelsBookSelected = book;
  state.labelsStorySelected = story;
  state.labelsBookExpanded.add(book);
  if (state.hypEngine) {
    state.labelsEngine = state.hypEngine;
    document.getElementById("labels-engine").value = state.hypEngine;
  }
  if (topics && topics.length) {
    // Tick exactly the requested topics; untick all categories so the topic
    // narrow isn't double-masked by a category filter.
    setAllChecked("labels-category", true);
    for (const el of document.querySelectorAll(
      `#labels-topic input[type="checkbox"]`,
    )) {
      el.checked = topics.includes(el.value);
    }
    updateDropdownSummary("labels-topic");
  } else {
    setAllChecked("labels-category", true);
    setAllChecked("labels-topic", true);
  }
  switchTab("labels");
  renderLabelsTree();
  renderLabelsPaneBody();
}
