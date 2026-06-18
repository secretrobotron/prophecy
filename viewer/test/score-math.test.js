// Unit tests for score-math.js. Run from the viewer/ directory:
//
//   node --test test/
//
// No dependencies — uses the built-in node:test runner (Node ≥ 18).

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";

import { state } from "../state.js";
import {
  SCORE_MODES,
  aggregateBooksLabels,
  allLabeledStories,
  avgCertainty,
  computeEffectiveWeights,
  hitRate,
  hypBucketScore,
  hypTopExemplar,
  meanOver,
  rankingCombine,
  rankingScoreFor,
  storyScore,
} from "../score-math.js";

// Reset the shared singleton between tests so order can't leak state.
function resetState() {
  state.labels = [];
  state.rankingEngine = "";
  state.rankingScoreMode = "weighted";
  state.rankingCombineMode = "position";
  state.hypMinCert = 0;
}

// Convenience constructor — only fields the math functions read. Accepts
// either the new sufficient-stats fields (cert_sum, hit_cert_sum) directly,
// OR the legacy `avg_certainty` shorthand which we expand to cert_sum +
// hit_cert_sum assuming all answers were yes (the common case in older
// tests). Pass cert_sum/hit_cert_sum explicitly when you need the mixed
// yes/no shape.
function label({
  book = "Exodus",
  story = "S1",
  category = "C",
  topic = "T",
  engine = "E",
  hits = 0,
  total = 0,
  cert_sum,
  hit_cert_sum,
  avg_certainty,
  prompts = [],
} = {}) {
  if (cert_sum === undefined) {
    cert_sum = avg_certainty != null ? avg_certainty * total : 0;
  }
  if (hit_cert_sum === undefined) {
    // Default: every yes carries the same per-prompt certainty as the average.
    hit_cert_sum = avg_certainty != null ? avg_certainty * hits : 0;
  }
  return {
    book,
    story,
    category,
    topic,
    engine,
    hits,
    total,
    cert_sum,
    hit_cert_sum,
    prompts,
  };
}

const approx = (a, b, eps = 1e-9) =>
  assert.ok(
    Math.abs(a - b) < eps,
    `expected ${a} ≈ ${b} (within ${eps})`,
  );

describe("computeEffectiveWeights", () => {
  it("returns 1.0 for every prompt in a topic with no explicit weights", () => {
    const w = computeEffectiveWeights([
      { id: "p1", category: "C", topic: "T", weight: "" },
      { id: "p2", category: "C", topic: "T", weight: null },
      { id: "p3", category: "C", topic: "T", weight: undefined },
    ]);
    assert.deepEqual(w, { p1: 1.0, p2: 1.0, p3: 1.0 });
  });

  it("assigns explicit weights and zeros the blanks within a partially-weighted topic", () => {
    const w = computeEffectiveWeights([
      { id: "p1", category: "C", topic: "T", weight: 2 },
      { id: "p2", category: "C", topic: "T", weight: "" },
      { id: "p3", category: "C", topic: "T", weight: 0.5 },
    ]);
    assert.deepEqual(w, { p1: 2, p2: 0.0, p3: 0.5 });
  });

  it("treats topics independently", () => {
    const w = computeEffectiveWeights([
      { id: "a", category: "C", topic: "T1", weight: 3 },
      { id: "b", category: "C", topic: "T1", weight: "" },
      { id: "c", category: "C", topic: "T2", weight: "" }, // unweighted topic → 1.0
      { id: "d", category: "C", topic: "T2", weight: "" },
    ]);
    assert.deepEqual(w, { a: 3, b: 0.0, c: 1.0, d: 1.0 });
  });

  it("coerces string weights to numbers", () => {
    const w = computeEffectiveWeights([{ id: "x", category: "C", topic: "T", weight: "1.5" }]);
    assert.equal(w.x, 1.5);
  });

  it("returns empty object for empty input", () => {
    assert.deepEqual(computeEffectiveWeights([]), {});
  });
});

describe("storyScore", () => {
  // Inline row builders make the (hits, total, cert_sum, hit_cert_sum)
  // primitives visible per test, since that's what the function actually
  // reads. Use label() above when you only care about the score, not the
  // exact certainty distribution.
  const r = (hits, total, cert_sum = 0, hit_cert_sum = 0) => ({
    hits,
    total,
    cert_sum,
    hit_cert_sum,
  });

  it("returns hit_rate for mode='hit', ignoring certainty", () => {
    // 3 hits / 4 total, cert irrelevant
    approx(storyScore(r(3, 4, 200, 200), "hit"), 0.75);
  });

  it("returns 1 if any hits, 0 otherwise, for mode='coverage'", () => {
    assert.equal(storyScore(r(1, 4, 200, 50), "coverage"), 1);
    assert.equal(storyScore(r(0, 4, 200, 0), "coverage"), 0);
  });

  it("returns hit_rate × avg_certainty/100 for mode='weighted'", () => {
    // hit_rate=0.75, avg_cert=80 → 0.75 × 0.80 = 0.60
    approx(storyScore(r(3, 4, 320, 240), "weighted"), 0.6);
  });

  it("returns Σ wᵢaᵢcᵢ / total / 100 for mode='coupled'", () => {
    // hit_cert_sum=240; total=4 → 240/4/100 = 0.60
    approx(storyScore(r(3, 4, 320, 240), "coupled"), 0.6);
  });

  it("REGRESSION: coupled diverges from weighted when noes are confident", () => {
    // 2 prompts: yes cert=80, no cert=100. Equal weights.
    // hit_rate=0.5, avg_cert=90 → weighted = 0.5 × 0.90 = 0.45
    // hit_cert_sum = 80; total = 2 → coupled = 0.40
    approx(storyScore(r(1, 2, 180, 80), "weighted"), 0.45);
    approx(storyScore(r(1, 2, 180, 80), "coupled"), 0.4);

    // Make the no LESS confident (cert=20). weighted drops; coupled unchanged.
    approx(storyScore(r(1, 2, 100, 80), "weighted"), 0.25);
    approx(storyScore(r(1, 2, 100, 80), "coupled"), 0.4);
  });

  it("defaults to weighted semantics for unknown mode", () => {
    approx(storyScore(r(1, 2, 200, 100), "anything-else"), 0.5);
  });

  it("returns 0 when total is 0, in every mode", () => {
    for (const mode of SCORE_MODES) {
      assert.equal(storyScore(r(0, 0, 0, 0), mode), 0);
    }
  });

  it("treats missing cert_sum / hit_cert_sum as 0 (legacy rows)", () => {
    assert.equal(storyScore({ hits: 1, total: 1 }, "weighted"), 0);
    assert.equal(storyScore({ hits: 1, total: 1 }, "coupled"), 0);
  });
});

describe("hitRate / avgCertainty helpers", () => {
  it("hitRate is Σwa / Σw", () => {
    approx(hitRate({ hits: 3, total: 4 }), 0.75);
    assert.equal(hitRate({ hits: 0, total: 0 }), 0);
  });

  it("avgCertainty is Σwc / Σw on 0..100", () => {
    approx(avgCertainty({ total: 8, cert_sum: 620 }), 77.5);
    assert.equal(avgCertainty({ total: 0, cert_sum: 0 }), 0);
  });
});

describe("aggregateBooksLabels", () => {
  it("groups by (category, topic) and computes coverage + layer_score", () => {
    const rows = [
      label({ story: "S1", category: "C1", topic: "T1", hits: 2, total: 4, avg_certainty: 50 }),
      label({ story: "S2", category: "C1", topic: "T1", hits: 4, total: 4, avg_certainty: 100 }),
      label({ story: "S1", category: "C2", topic: "T2", hits: 0, total: 4, avg_certainty: 0 }),
    ];
    const out = aggregateBooksLabels(rows, 2, "weighted");
    assert.equal(out.length, 2);
    const c1 = out.find((a) => a.category === "C1");
    // S1 weighted = 0.5 * 0.5 = 0.25; S2 weighted = 1.0 * 1.0 = 1.0; mean = 0.625
    approx(c1.layer_score, 0.625);
    approx(c1.coverage, 1.0); // both stories have signal
    assert.equal(c1.story_count, 2);
    assert.equal(c1.total_stories, 2);
    const c2 = out.find((a) => a.category === "C2");
    approx(c2.layer_score, 0); // S1 contributes 0
    approx(c2.coverage, 0); // no stories hit
  });

  it("sorts by primary metric, then by secondary, for stable ordering", () => {
    const rows = [
      label({ story: "S1", topic: "T-A", hits: 4, total: 4, avg_certainty: 100 }),  // weighted=1, cov=1
      label({ story: "S1", topic: "T-B", hits: 4, total: 4, avg_certainty: 50 }),   // weighted=0.5, cov=1
      label({ story: "S1", topic: "T-C", hits: 1, total: 4, avg_certainty: 100 }),  // weighted=0.25, cov=1
    ];
    const weighted = aggregateBooksLabels(rows, 1, "weighted").map((a) => a.topic);
    assert.deepEqual(weighted, ["T-A", "T-B", "T-C"]);

    // Coverage mode: all three tie at 1.0, secondary = layer_score breaks ties
    const coverage = aggregateBooksLabels(rows, 1, "coverage").map((a) => a.topic);
    assert.deepEqual(coverage, ["T-A", "T-B", "T-C"]);
  });

  it("returns empty array for empty input", () => {
    assert.deepEqual(aggregateBooksLabels([], 5, "weighted"), []);
  });

  it("handles totalStories=0 without dividing by zero", () => {
    const out = aggregateBooksLabels(
      [label({ hits: 1, total: 1, avg_certainty: 100 })],
      0,
      "weighted",
    );
    assert.equal(out[0].coverage, 0);
  });
});

describe("rankingScoreFor", () => {
  beforeEach(resetState);

  it("returns null when no labels row matches", () => {
    state.labels = [label({ book: "Exodus", story: "S1", category: "C", topic: "T" })];
    assert.equal(rankingScoreFor("Genesis", "S1", { category: "C", topic: "T" }), null);
    assert.equal(rankingScoreFor("Exodus", "S2", { category: "C", topic: "T" }), null);
    assert.equal(rankingScoreFor("Exodus", "S1", { category: "C", topic: "Other" }), null);
  });

  it("respects the rankingEngine filter", () => {
    state.labels = [
      label({ engine: "qwen", hits: 4, total: 4, avg_certainty: 100 }),
      label({ engine: "gpt", hits: 1, total: 4, avg_certainty: 50 }),
    ];
    state.rankingEngine = "qwen";
    approx(rankingScoreFor("Exodus", "S1", { category: "C", topic: "T" }), 100);
    state.rankingEngine = "gpt";
    approx(rankingScoreFor("Exodus", "S1", { category: "C", topic: "T" }), 12.5);
  });

  it("returns 0 when total is 0", () => {
    state.labels = [label({ hits: 0, total: 0, avg_certainty: 0 })];
    assert.equal(rankingScoreFor("Exodus", "S1", { category: "C", topic: "T" }), 0);
  });

  it("REGRESSION: equals storyScore(row, mode) * 100 for every mode", () => {
    // The whole point of the score-math.js extraction was unifying these.
    // Sweep a grid of inputs and assert the invariant holds.
    const cases = [
      { hits: 0, total: 0, avg_certainty: 0 },
      { hits: 0, total: 4, avg_certainty: 80 },
      { hits: 1, total: 4, avg_certainty: 80 },
      { hits: 4, total: 4, avg_certainty: 100 },
      { hits: 3, total: 7, avg_certainty: 33 },
    ];
    for (const fields of cases) {
      state.labels = [label(fields)];

      state.rankingScoreMode = "weighted";
      const wRanking = rankingScoreFor("Exodus", "S1", { category: "C", topic: "T" });
      const wExpected = storyScore(state.labels[0], "weighted") * 100;
      approx(wRanking, wExpected);

      state.rankingScoreMode = "straight";
      const sRanking = rankingScoreFor("Exodus", "S1", { category: "C", topic: "T" });
      const sExpected = storyScore(state.labels[0], "hit") * 100;
      approx(sRanking, sExpected);
    }
  });
});

describe("rankingCombine", () => {
  beforeEach(resetState);

  it("returns 0 for empty input", () => {
    assert.equal(rankingCombine([]), 0);
  });

  it("returns the single value when given one score", () => {
    state.rankingCombineMode = "position";
    approx(rankingCombine([42]), 42);
    state.rankingCombineMode = "equal";
    approx(rankingCombine([42]), 42);
  });

  it("computes a simple mean in equal mode", () => {
    state.rankingCombineMode = "equal";
    approx(rankingCombine([10, 20, 30]), 20);
  });

  it("uses N-i weights normalized in position mode", () => {
    state.rankingCombineMode = "position";
    // weights = [3, 2, 1], sum = 6 → (3·10 + 2·20 + 1·30) / 6 = 100/6
    approx(rankingCombine([10, 20, 30]), 100 / 6);
  });

  it("equal mode is permutation-invariant; position mode is not", () => {
    state.rankingCombineMode = "equal";
    approx(rankingCombine([10, 20, 30]), rankingCombine([30, 20, 10]));

    state.rankingCombineMode = "position";
    assert.notEqual(rankingCombine([10, 20, 30]), rankingCombine([30, 20, 10]));
  });
});

describe("hypBucketScore", () => {
  beforeEach(resetState);

  it("returns mean of storyScore values across matching topic rows", () => {
    state.labels = [
      label({ topic: "T1", hits: 2, total: 4, avg_certainty: 100 }), // weighted 0.5
      label({ topic: "T2", hits: 4, total: 4, avg_certainty: 100 }), // weighted 1.0
      label({ topic: "T3", hits: 0, total: 4, avg_certainty: 100 }), // ignored — not in bucket
    ];
    const bucket = { topics: ["T1", "T2"] };
    approx(hypBucketScore("Exodus", "S1", bucket, "", "weighted"), 0.75);
  });

  it("returns 0 when no rows match", () => {
    state.labels = [label({ topic: "T-other" })];
    approx(hypBucketScore("Exodus", "S1", { topics: ["T1"] }, "", "weighted"), 0);
  });

  it("filters by engine when one is given", () => {
    state.labels = [
      label({ engine: "qwen", topic: "T1", hits: 4, total: 4, avg_certainty: 100 }),
      label({ engine: "gpt", topic: "T1", hits: 0, total: 4, avg_certainty: 0 }),
    ];
    approx(hypBucketScore("Exodus", "S1", { topics: ["T1"] }, "qwen", "weighted"), 1.0);
    approx(hypBucketScore("Exodus", "S1", { topics: ["T1"] }, "gpt", "weighted"), 0);
    // No engine filter → mean of both = 0.5
    approx(hypBucketScore("Exodus", "S1", { topics: ["T1"] }, "", "weighted"), 0.5);
  });

  it("skips rows below state.hypMinCert (interpreted as 0..100)", () => {
    state.labels = [
      label({ topic: "T1", hits: 1, total: 4, avg_certainty: 50 }), // weighted 0.125
      label({ topic: "T2", hits: 4, total: 4, avg_certainty: 100 }), // weighted 1.0
    ];
    state.hypMinCert = 50; // threshold = 0.50
    approx(hypBucketScore("Exodus", "S1", { topics: ["T1", "T2"] }, "", "weighted"), 1.0);
  });
});

describe("hypTopExemplar", () => {
  beforeEach(resetState);

  it("returns null when no story scores above zero", () => {
    state.labels = [label({ topic: "T1", hits: 0, total: 4 })];
    const slice = [{ book: "Exodus", story: "S1" }];
    assert.equal(hypTopExemplar(slice, { topics: ["T1"] }, "", "weighted"), null);
  });

  it("picks the highest-scoring story and its top-certainty true prompt", () => {
    state.labels = [
      label({
        story: "S1",
        topic: "T1",
        hits: 1,
        total: 1,
        avg_certainty: 50,
        prompts: [
          { id: "p1", answer: true, certainty: 40 },
          { id: "p2", answer: true, certainty: 70 },
          { id: "p3", answer: false, certainty: 100 }, // false — ignored
        ],
      }),
      label({
        story: "S2",
        topic: "T1",
        hits: 1,
        total: 1,
        avg_certainty: 100,
        prompts: [{ id: "q1", answer: true, certainty: 60 }],
      }),
    ];
    const slice = [
      { book: "Exodus", story: "S1" },
      { book: "Exodus", story: "S2" },
    ];
    const ex = hypTopExemplar(slice, { topics: ["T1"] }, "", "weighted");
    assert.equal(ex.story, "S2"); // higher weighted score
    assert.equal(ex.prompt.id, "q1");
    approx(ex.score, 1.0);
  });
});

describe("meanOver", () => {
  it("returns 0 for empty input", () => {
    assert.equal(meanOver([], () => 1), 0);
  });

  it("returns the mean of fn(item) across items", () => {
    approx(meanOver([1, 2, 3, 4], (x) => x * 2), 5);
  });
});

describe("allLabeledStories", () => {
  beforeEach(resetState);

  it("dedupes by story, keeping the first book encountered", () => {
    state.labels = [
      label({ book: "Exodus", story: "S1" }),
      label({ book: "Exodus", story: "S1" }), // dup
      label({ book: "Genesis", story: "S2" }),
    ];
    const out = allLabeledStories();
    assert.equal(out.length, 2);
    assert.deepEqual(out[0], { book: "Exodus", story: "S1" });
    assert.deepEqual(out[1], { book: "Genesis", story: "S2" });
  });

  it("returns empty array when no labels", () => {
    state.labels = [];
    assert.deepEqual(allLabeledStories(), []);
  });
});
