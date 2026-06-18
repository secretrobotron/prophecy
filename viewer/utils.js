// Tiny DOM-and-string helpers shared across modules. Pure (no state import).

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

export function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// Render a weighted numeric value (Σwa or Σw). Drop the decimal when the value
// is integer-equivalent (uniform-weight topics, where w=1 collapses Σw to N).
export function formatWeighted(value) {
  if (value == null) return "";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function cssSafe(s) {
  return String(s).replace(/[^a-zA-Z0-9_-]/g, "_");
}

export function sortedUnique(values) {
  return Array.from(new Set(values.filter(Boolean))).sort();
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
// alphabetically so the order is always stable. Takes the storiesMeta map
// explicitly (rather than reading state) so this stays a pure function.
export function sortStoriesCanonical(stories, storiesMeta) {
  return stories.slice().sort((a, b) => {
    const ma = storiesMeta[a];
    const mb = storiesMeta[b];
    const va = ma && Array.isArray(ma.verses) ? ma.verses[0] : null;
    const vb = mb && Array.isArray(mb.verses) ? mb.verses[0] : null;
    const [ca, ra] = firstVersePos(va);
    const [cb, rb] = firstVersePos(vb);
    if (ca !== cb) return ca - cb;
    if (ra !== rb) return ra - rb;
    return a.localeCompare(b);
  });
}
