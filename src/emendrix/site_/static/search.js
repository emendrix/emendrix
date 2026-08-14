// The one script on the site: client-side search over the prebuilt index.
// Without JavaScript this file never runs and the site stays fully navigable;
// the #search container is empty until this fills it. No cookies, no storage,
// no requests except the index fetch, relative to the page.
"use strict";

(function () {
  var container = document.getElementById("search");
  if (!container) return;
  var root = container.dataset.root || "";

  var input = document.createElement("input");
  input.type = "search";
  input.placeholder = "Find an act or provision…";
  input.setAttribute("aria-label", "Find an act or provision");
  var results = document.createElement("ul");
  results.className = "results";
  results.hidden = true;
  container.appendChild(input);
  container.appendChild(results);

  var entries = null;
  function load() {
    if (entries !== null) return Promise.resolve(entries);
    return fetch(root + "search-index.json")
      .then(function (response) { return response.json(); })
      .then(function (payload) { entries = payload.entries; return entries; });
  }

  function score(entry, query) {
    var label = entry.label.toLowerCase();
    if (label === query) return 0;
    if (label.startsWith(query)) return 1;
    var at = label.indexOf(query);
    return at < 0 ? -1 : 2 + at / label.length;
  }

  function render(matches) {
    results.textContent = "";
    matches.forEach(function (entry) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = root + entry.url;
      link.textContent = entry.label;
      var kind = document.createElement("span");
      kind.className = "kind";
      kind.textContent = entry.kind;
      item.appendChild(link);
      item.appendChild(kind);
      results.appendChild(item);
    });
    results.hidden = matches.length === 0;
  }

  function search(query) {
    load().then(function (all) {
      var q = query.trim().toLowerCase();
      if (q.length < 2) { render([]); return; }
      var scored = [];
      all.forEach(function (entry) {
        var s = score(entry, q);
        if (s >= 0) scored.push([s, entry]);
      });
      scored.sort(function (a, b) {
        return a[0] - b[0] || a[1].label.localeCompare(b[1].label);
      });
      render(scored.slice(0, 12).map(function (pair) { return pair[1]; }));
    });
  }

  input.addEventListener("input", function () { search(input.value); });
  input.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { input.value = ""; render([]); }
    if (event.key === "Enter") {
      var first = results.querySelector("a");
      if (first) window.location.href = first.href;
    }
  });
  document.addEventListener("click", function (event) {
    if (!container.contains(event.target)) render([]);
  });
})();
