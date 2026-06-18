// Pure scoring/aggregation helpers shared across every tab that reads labels.
// One canonical implementation per metric, so the same (story, label) tuple
// scores the same number wherever it surfaces — Books, Ranking, and Hypotheses
// all funnel through storyScore() below.

import { state } from "./state.js";

// Mirror of prophecy.prompts.Prompts.get_effective_weights() in JS so client-side
// aggregations (Query tab, anywhere we recompute from raw shards) use the same
// per-topic policy as the server-side label/query commands:
//   * topic with zero explicit weights → uniform 1.0 (fully-unweighted fallback)
//   * topic with any explicit weights → blanks → 0.0 (don't contribute)
export function computeEffectiveWeights(prompts) {
  const byTopic = new Map();
  for (const p of prompts) {
    const key = `${p.category}\t${p.topic}`;
    if (!byTopic.has(key)) byTopic.set(key, []);
    byTopic.get(key).push(p);
  }
  const out = {};
  for (const group of byTopic.values()) {
    const anyWeighted = group.some(
      (p) => p.weight !== null && p.weight !== undefined && p.weight !== "",
    );
    for (const p of group) {
      const hasWeight = p.weight !== null && p.weight !== undefined && p.weight !== "";
      out[p.id] = hasWeight ? Number(p.weight) : anyWeighted ? 0.0 : 1.0;
    }
  }
  return out;
}

// Score-mode identifiers — mirrors prophecy.scoring.SCORE_MODES on the
// Python side. Adding a new mode means a new branch in storyScore() here,
// a new branch in scoring.story_score() in Python, and a new option in the
// score-mode dropdowns. The shipped labels.json carries sufficient statistics
// (hits, total, cert_sum, hit_cert_sum) so any mode is purely derivable.
export const SCORE_MODES = ["weighted", "hit", "coverage", "coupled"];

// hit_rate = Σ wᵢ·aᵢ / Σ wᵢ — fraction of weighted prompts that answered yes.
export function hitRate(row) {
  return row.total > 0 ? row.hits / row.total : 0;
}

// Weighted mean certainty in 0..100. Derived from cert_sum / total so display
// code can show "avg cert 85" without persisting that computed value.
export function avgCertainty(row) {
  return row.total > 0 ? row.cert_sum / row.total : 0;
}

// Per-story score for one label row, in [0, 1].
//
//   "hit"      → hit_rate (ignores certainty)
//   "coverage" → 1 if any yes, else 0
//   "weighted" → hit_rate × avg_certainty/100 (product of two means;
//                 default, preserves the original viewer behavior)
//   "coupled"  → Σ wᵢ·aᵢ·cᵢ / Σ wᵢ / 100 (each yes contributes its own
//                 certainty; noes contribute 0 but pull the denominator)
//
// A confidently-wrong "no" raises the "weighted" score (it pulls avg_certainty
// up without pulling hit_rate down) but leaves "coupled" unchanged.
export function storyScore(row, mode) {
  if (!row.total) return 0;
  const rate = row.hits / row.total;
  if (mode === "hit") return rate;
  if (mode === "coverage") return row.hits > 0 ? 1 : 0;
  if (mode === "coupled") return (row.hit_cert_sum || 0) / row.total / 100;
  // "weighted" (default): hit_rate × avg_certainty/100
  return rate * ((row.cert_sum || 0) / row.total) / 100;
}

// Aggregate by (category, topic) across the given (already book-filtered)
// label rows. Computes both layer strength (mean per-story score under the
// chosen mode) and coverage (share of stories with any signal). The chosen
// score mode selects the sort key — both numbers stay displayed so the
// user can read "widespread-but-weak" vs "narrow-but-strong" by eye.
export function aggregateBooksLabels(rows, totalStories, mode) {
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

// Score a single (story, book, label) tuple under the Ranking tab's score
// mode. Returns null if there's no matching labels.json row (so the caller
// can decide whether to treat as 0 or skip). Scores are on a 0-100 scale to
// match the Ranking tab's threshold UI and bar widths — internally routed
// through storyScore() and multiplied by 100, so Books / Hypotheses /
// Ranking can never disagree on what the same (story, label) is worth.
export function rankingScoreFor(book, story, label) {
  const mode = state.rankingScoreMode === "weighted" ? "weighted" : "hit";
  for (const l of state.labels) {
    if (l.book !== book || l.story !== story) continue;
    if (l.category !== label.category || l.topic !== label.topic) continue;
    if (state.rankingEngine && l.engine !== state.rankingEngine) continue;
    return storyScore(l, mode) * 100;
  }
  return null;
}

export function rankingCombine(scores) {
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

// Score a single (book, story, bucket) tuple under the current scoring mode,
// optionally restricted to one engine. Returns 0..1, mean of per-topic
// storyScore values across all matching label rows (treats absence as 0).
export function hypBucketScore(book, story, bucket, engine, scoreMode) {
  const topics = new Set(bucket.topics || []);
  const minCert = state.hypMinCert / 100;
  let sum = 0;
  let count = 0;
  for (const l of state.labels) {
    if (l.book !== book || l.story !== story) continue;
    if (engine && l.engine !== engine) continue;
    if (!topics.has(l.topic)) continue;
    const score = storyScore(l, scoreMode);
    if (score < minCert) continue;
    sum += score;
    count += 1;
  }
  return count > 0 ? sum / count : 0;
}

// Strongest supporting (story, prompt) pair for one bucket under the slice.
// We pick the story with the highest bucket score, then surface its single
// true prompt with the highest certainty. Returns null if nothing scored > 0.
export function hypTopExemplar(slice, bucket, engine, scoreMode) {
  let best = { score: -1, story: null, book: null, prompt: null };
  const topics = new Set(bucket.topics || []);
  for (const { book, story } of slice) {
    const score = hypBucketScore(book, story, bucket, engine, scoreMode);
    if (score <= best.score) continue;
    let bestPrompt = null;
    let bestCert = -1;
    for (const l of state.labels) {
      if (l.book !== book || l.story !== story) continue;
      if (engine && l.engine !== engine) continue;
      if (!topics.has(l.topic)) continue;
      for (const p of l.prompts) {
        if (!p.answer) continue;
        const cert = Number(p.certainty) || 0;
        if (cert > bestCert) {
          bestCert = cert;
          bestPrompt = p;
        }
      }
    }
    best = { score, story, book, prompt: bestPrompt };
  }
  return best.score > 0 ? best : null;
}

export function meanOver(items, fn) {
  if (!items.length) return 0;
  let sum = 0;
  for (const it of items) sum += fn(it);
  return sum / items.length;
}

export function allLabeledStories() {
  const seen = new Map();
  for (const l of state.labels) {
    if (!seen.has(l.story)) seen.set(l.story, { book: l.book, story: l.story });
  }
  return Array.from(seen.values());
}
