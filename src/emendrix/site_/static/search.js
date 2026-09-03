// The one script on the site: client-side search over the prebuilt index.
// Without JavaScript this file never runs and the site stays fully navigable;
// the #search container is empty until this fills it. No cookies, no storage,
// no requests except the index fetch, relative to the page.
//
// The control is the combobox with a listbox popup described by the WAI-ARIA
// Authoring Practices: the input keeps focus throughout, owns the list through
// aria-controls, says whether it is open through aria-expanded, and names the
// highlighted row through aria-activedescendant. ArrowDown, ArrowUp, Home and
// End move the highlight; Enter opens it; Escape empties the box and closes the
// list. Enter with nothing highlighted still opens the first row, which is now a
// row the reader has been told about: the status line has already announced how
// many results there are.
//
// Every row is a plain link, so the mouse path never depended on any of the key
// handling above and still does not: middle-click, copy address and open in a new
// tab all work because the row is an anchor before it is an option. The status
// line is the only element on the page with live semantics; it is off-screen,
// announces the count politely, and says nothing at all until a query is long
// enough to be searched.
"use strict";

(function () {
  var container = document.getElementById("search");
  if (!container) return;
  var root = container.dataset.root || "";

  var input = document.createElement("input");
  input.type = "search";
  input.placeholder = "Find an act or provision…";
  input.setAttribute("aria-label", "Find an act or provision");
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-haspopup", "listbox");
  input.setAttribute("aria-controls", "search-results");
  input.setAttribute("aria-expanded", "false");
  var results = document.createElement("ul");
  results.className = "results";
  results.id = "search-results";
  results.setAttribute("role", "listbox");
  results.setAttribute("aria-label", "Search results");
  results.hidden = true;
  var status = document.createElement("div");
  status.className = "visually-hidden";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.setAttribute("aria-atomic", "true");
  container.appendChild(input);
  container.appendChild(results);
  container.appendChild(status);

  // The rendered rows, in the order they are shown, and which of them is highlighted.
  var options = [];
  var active = -1;

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

  function counted(total) {
    if (total === 0) return "No results";
    return total === 1 ? "1 result" : total + " results";
  }

  // `searched` is false where no query was run at all, which is a different thing
  // from a query that found nothing and must not be announced as one.
  function render(matches, searched) {
    results.textContent = "";
    options = [];
    active = -1;
    input.removeAttribute("aria-activedescendant");
    matches.forEach(function (entry, at) {
      var item = document.createElement("li");
      item.id = "search-option-" + at;
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", "false");
      var link = document.createElement("a");
      link.href = root + entry.url;
      link.textContent = entry.label;
      var kind = document.createElement("span");
      kind.className = "kind";
      kind.textContent = entry.kind;
      item.appendChild(link);
      item.appendChild(kind);
      results.appendChild(item);
      options.push(item);
    });
    results.hidden = matches.length === 0;
    input.setAttribute("aria-expanded", results.hidden ? "false" : "true");
    status.textContent = searched ? counted(matches.length) : "";
  }

  function highlight(next) {
    if (options.length === 0) return;
    if (active >= 0) {
      options[active].classList.remove("active");
      options[active].setAttribute("aria-selected", "false");
    }
    active = next;
    var option = options[active];
    option.classList.add("active");
    option.setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", option.id);
    // The list scrolls at 60vh, so a highlight can otherwise move out of sight.
    option.scrollIntoView({ block: "nearest" });
  }

  function follow(option) {
    var link = option.querySelector("a");
    if (link) window.location.href = link.href;
  }

  function search(query) {
    load().then(function (all) {
      var q = query.trim().toLowerCase();
      if (q.length < 2) { render([], false); return; }
      var scored = [];
      all.forEach(function (entry) {
        var s = score(entry, q);
        if (s >= 0) scored.push([s, entry]);
      });
      scored.sort(function (a, b) {
        return a[0] - b[0] || a[1].label.localeCompare(b[1].label);
      });
      render(scored.slice(0, 12).map(function (pair) { return pair[1]; }), true);
    });
  }

  input.addEventListener("input", function () { search(input.value); });
  input.addEventListener("keydown", function (event) {
    var count = options.length;
    if (event.key === "Escape") { input.value = ""; render([], false); return; }
    if (count === 0) return;
    // preventDefault throughout: the caret would otherwise jump to an end of the
    // query on every arrow key, and Enter would submit whatever encloses the box.
    if (event.key === "Enter") {
      event.preventDefault();
      follow(options[active < 0 ? 0 : active]);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      highlight((active + 1) % count);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      highlight((active <= 0 ? count : active) - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      highlight(0);
    } else if (event.key === "End") {
      event.preventDefault();
      highlight(count - 1);
    }
  });
  document.addEventListener("click", function (event) {
    if (!container.contains(event.target)) render([], false);
  });
})();
