// DOM helpers for the toolbar dropdowns and multi-selects. Every tab that
// reads a filter checkbox list or syncs an "(all)" dropdown goes through
// these so we never have one tab forgetting to refresh the summary chip.

import { state } from "./state.js";
import { cssSafe, escapeHtml, sortedUnique } from "./utils.js";

export function fillCheckboxList(containerId, options, defaultChecked) {
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

export function fillSelect(id, options) {
  const el = document.getElementById(id);
  // Preserve the existing "(all)" placeholder.
  for (const opt of options) {
    const o = document.createElement("option");
    o.value = opt;
    o.textContent = opt;
    el.appendChild(o);
  }
}

export function updateDropdownSummary(containerId) {
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

export function readCheckedValues(containerId) {
  return Array.from(
    document.querySelectorAll(`#${containerId} input[type="checkbox"]:checked`),
  ).map((el) => el.value);
}

export function readAllValues(containerId) {
  return Array.from(
    document.querySelectorAll(`#${containerId} input[type="checkbox"]`),
  ).map((el) => el.value);
}

export function setAllChecked(containerId, checked) {
  for (const el of document.querySelectorAll(`#${containerId} input[type="checkbox"]`)) {
    el.checked = checked;
  }
  updateDropdownSummary(containerId);
}

// Tick exactly one checkbox in a multi-select list, untick all others. If the
// target value isn't present (shouldn't happen, but be safe), leave everything
// checked rather than leaving the user stranded with nothing.
export function setSingleChecked(containerId, value) {
  let matched = false;
  for (const el of document.querySelectorAll(`#${containerId} input[type="checkbox"]`)) {
    const should = el.value === value;
    el.checked = should;
    if (should) matched = true;
  }
  if (!matched) {
    setAllChecked(containerId, true);
  }
  updateDropdownSummary(containerId);
}

export function populateFilterOptions() {
  const m = state.manifest;

  // Prompts tab: filters reflect the prompts.tsv content (all defined prompts),
  // since the tab is a browser for prompt definitions, not for cached results.
  const allPromptCategorys = sortedUnique(state.prompts.map((p) => p.category));
  const allPromptTopics = sortedUnique(state.prompts.map((p) => p.topic));
  fillSelect("prompts-category", allPromptCategorys);
  fillSelect("prompts-topic", allPromptTopics);

  // Query/Responses tabs reflect the cached data only (manifest facets).
  const stories = m.stories || [];
  fillSelect("responses-book", m.books);
  fillSelect("responses-story", stories);
  fillSelect("responses-category", m.categories);
  fillSelect("responses-topic", m.topics);
  fillSelect("responses-engine", m.engines);

  fillSelect("query-book", m.books);
  fillSelect("query-story", stories);

  // Multi-select checkbox lists on the Query tab. Default to all-checked so
  // an unconfigured query returns everything.
  fillCheckboxList("query-category", m.categories, true);
  fillCheckboxList("query-topic", m.topics, true);
  fillCheckboxList("query-engine", m.engines, true);
}

export function closeAllDropdowns() {
  for (const dropdown of document.querySelectorAll(".multi-dropdown")) {
    const panel = dropdown.querySelector(".multi-panel");
    const toggle = dropdown.querySelector(".multi-toggle");
    if (!panel.hasAttribute("hidden")) {
      panel.setAttribute("hidden", "");
      toggle.setAttribute("aria-expanded", "false");
    }
  }
}

export function closeAllNavMenus() {
  for (const menu of document.querySelectorAll(".nav-menu")) {
    const panel = menu.querySelector(".nav-menu-panel");
    const toggle = menu.querySelector(".nav-menu-toggle");
    if (!panel.hasAttribute("hidden")) {
      panel.setAttribute("hidden", "");
      toggle.setAttribute("aria-expanded", "false");
    }
  }
}
