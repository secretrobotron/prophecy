// Tab routing + URL-hash sync. Stateless helpers; emits a "tab:switch"
// CustomEvent so tabs that need lazy work (the Responses tab loads shards
// on activation) can listen without nav.js importing them.

export function switchTab(name, opts = {}) {
  for (const btn of document.querySelectorAll(".tab-button")) {
    btn.classList.toggle("active", btn.dataset.tab === name);
  }
  for (const panel of document.querySelectorAll(".tab-panel")) {
    panel.classList.toggle("active", panel.id === `tab-${name}`);
  }
  // A nav-menu group lights up when one of its children is the active tab,
  // so the top bar shows which group the current view lives under.
  for (const menu of document.querySelectorAll(".nav-menu")) {
    menu.classList.toggle(
      "active",
      Boolean(menu.querySelector(`.tab-button[data-tab="${name}"]`)),
    );
  }
  document.dispatchEvent(new CustomEvent("tab:switch", { detail: { name } }));
  // Sync the URL hash so each tab change pushes a history entry — back
  // button then walks the user through the tabs they visited. Skip when
  // we're already responding to a hash change to avoid a feedback loop.
  if (!opts.fromHash) {
    const target = `#${name}`;
    if (window.location.hash !== target) {
      window.location.hash = name;
    }
  }
}

// The set of tab names backed by an actual panel — used to filter hash
// values so a stray `#anything` doesn't blank the UI.
export function validTabName(name) {
  return Boolean(
    name && document.querySelector(`.tab-button[data-tab="${name}"]`),
  );
}
