// Singleton viewer state. Every module imports the same object — ES modules
// cache the binding, so writes from any module are visible to all others.

// Allow the module to be imported under Node (for unit tests) where `window`
// doesn't exist. In the browser this preserves the ?data=… override.
const params =
  typeof window !== "undefined"
    ? new URLSearchParams(window.location.search)
    : new URLSearchParams();
export const DATA_ROOT = (params.get("data") || "data").replace(/\/$/, "");

export const state = {
  manifest: null,
  prompts: [],
  promptWeights: {},     // id -> effective numeric weight (mirrors Prompts.get_effective_weights)
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

  // Hypotheses tab UI state
  hypotheses: [],                   // bundled pre-baked hypotheses (raw payloads)
  hypothesisSelected: null,         // id of the currently-rendered hypothesis
  hypEngine: "",                    // engine filter ("" = mean across engines)
  hypScoreMode: "weighted",         // weighted | hit | coverage (matches storyScore())
  hypMinCert: 0,                    // 0..100 — filter weak prompt contributions
  hypCounterFirst: false,           // sort scorecard so counter-evidence comes first
};
