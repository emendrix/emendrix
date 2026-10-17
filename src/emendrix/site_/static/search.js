// The one script on the site: client-side search over the prebuilt index.
// Without JavaScript this file never runs and the site stays fully navigable;
// the #search container is empty until this fills it. No cookies, no storage,
// no requests except the two index fetches, relative to the page.
//
// The second index holds every CAS, EC and Index number an entry prints, and is
// fetched only when it can answer: for a query that opens with a digit, or from
// the first keystroke on a page whose #search carries data-substances. A number
// typed without hyphens is read here through its check digit, as CAS by placing
// the hyphens before the last digit and the two before it, and with exactly
// seven digits also as EC; every reading that passes is matched exactly. The
// readings are the same rules the pipeline identifies numbers by, and a test
// holds this copy to them over values cut from the committed fixtures.
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
// enough to be searched. A query that finds nothing is also said on screen, as a
// row that is not an option, so the list stays closed to assistive technology
// while a sighted reader is not left looking at nothing.
"use strict";

// The hyphen forms a pasted number may carry, read as the ASCII hyphen.
var HYPHENS = /[\u2010\u2011\u2012\u2013\u2212]/g;

function casValue(text) {
  var parts = /^(\d{2,7})-(\d{2})-(\d)$/.exec(text);
  if (!parts) return null;
  var first = parts[1].replace(/^0+/, "");
  if (first.length < 2) return null;
  var digits = first + parts[2];
  var sum = 0;
  for (var at = 0; at < digits.length; at++) {
    sum += Number(digits.charAt(digits.length - 1 - at)) * (at + 1);
  }
  return sum % 10 === Number(parts[3]) ? first + "-" + parts[2] + "-" + parts[3] : null;
}

function ecValue(text) {
  var parts = /^([2-9]\d{2})-(\d{3})-(\d)$/.exec(text);
  if (!parts) return null;
  var digits = parts[1] + parts[2];
  var sum = 0;
  for (var at = 0; at < 6; at++) sum += Number(digits.charAt(at)) * (at + 1);
  var check = sum % 11 === 10 ? 1 : sum % 11;
  return check === Number(parts[3]) ? text : null;
}

function indexValue(text) {
  var parts = /^(\d{3})-(\d{3})-(\d{2})-([\dX])$/.exec(text);
  if (!parts) return null;
  var digits = parts[1] + parts[2] + parts[3];
  var sum = 0;
  for (var at = 0; at < 8; at++) sum += Number(digits.charAt(at)) * (at + 1);
  var check = sum % 11 === 10 ? "X" : String(sum % 11);
  return check === parts[4] ? digits.slice(0, 3) + "-" + digits.slice(3, 6) +
    "-" + digits.slice(6) + "-" + check : null;
}

// Every identifier a typed value can be read as, as [scheme, value] pairs.
function readIdentifier(text) {
  var value = text.replace(HYPHENS, "-").trim().replace(/\s+/g, " ");
  var found = [];
  function keep(scheme, read) { if (read !== null) found.push([scheme, read]); }
  if (value.indexOf("-") >= 0) {
    keep("cas", casValue(value));
    keep("ec", ecValue(value));
    keep("index", indexValue(value));
  } else if (/^\d{5,10}$/.test(value)) {
    var n = value.length;
    keep("cas", casValue(value.slice(0, n - 3) + "-" + value.slice(n - 3, n - 1) + "-" +
      value.charAt(n - 1)));
    if (n === 7) {
      keep("ec", ecValue(value.slice(0, 3) + "-" + value.slice(3, 6) + "-" + value.charAt(6)));
    }
  }
  return found;
}

(function () {
  var container = document.getElementById("search");
  if (!container) return;
  var root = container.dataset.root || "";
  var numbers = container.dataset.substances !== undefined;

  var input = document.createElement("input");
  input.type = "search";
  var asked = numbers ? "Find an act, provision or CAS or EC number" : "Find an act or provision";
  input.placeholder = asked + "…";
  input.setAttribute("aria-label", asked);
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

  // Each index is fetched once, the first time it is asked for, and kept.
  var loaded = {};
  function fetched(name) {
    if (!loaded[name]) {
      loaded[name] = fetch(root + name)
        .then(function (response) { return response.json(); })
        .then(function (payload) { return payload.entries; })
        // A file that fails to load is asked for again next time, and searches without it.
        .catch(function () { delete loaded[name]; return []; });
    }
    return loaded[name];
  }
  function load(digits) {
    var second = digits || numbers ? fetched("substance-index.json") : Promise.resolve([]);
    return Promise.all([fetched("search-index.json"), second]);
  }

  // A label match scores below 3 and a title match from 4 up, so every row found
  // by its name ranks above every row found only by its provision's title.
  function score(entry, query) {
    var label = entry.label.toLowerCase();
    if (label === query) return 0;
    if (label.startsWith(query)) return 1;
    var at = label.indexOf(query);
    if (at >= 0) return 2 + at / label.length;
    var title = (entry.title || "").toLowerCase();
    at = title.indexOf(query);
    return at < 0 ? -1 : 4 + at / title.length;
  }

  // A number matches exactly, by any reading of it, or by its leading digits from
  // four on and never in the middle; a name matches the title from three letters.
  function numberScore(entry, query, readings) {
    var label = entry.label.toLowerCase();
    if (label === query || readings.indexOf(label) >= 0) return 0;
    if (/^\d/.test(query)) return query.length >= 4 && label.startsWith(query) ? 1 : -1;
    if (query.length < 3) return -1;
    var title = (entry.title || "").toLowerCase();
    var at = title.indexOf(query);
    return at < 0 ? -1 : 4 + at / title.length;
  }

  // What each kind of entry in the index is called on screen. An alias leads to
  // an act, so it is called one. An identifier is an act's or an amending act's,
  // and which one is read off where it leads.
  var KIND = {
    act: "Act",
    alias: "Act",
    celex: "Act",
    provision: "Provision",
    amending: "Amending act",
    substance: "Substance"
  };

  function kindWord(entry) {
    if (entry.kind === "celex" && entry.url.indexOf("amendments/") === 0) return KIND.amending;
    return KIND[entry.kind] || entry.kind;
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
      link.textContent = entry.label + " ";
      if (entry.title) {
        // The law's own words, so text and never markup. A title with no lower-case
        // letter is set in small capitals, the rule the pages use.
        var title = document.createElement("span");
        title.className = entry.title === entry.title.toUpperCase() ? "ttl ttl--caps" : "ttl";
        title.textContent = entry.title;
        link.appendChild(title);
        link.appendChild(document.createTextNode(" "));
      }
      var kind = document.createElement("span");
      kind.className = "kind";
      kind.textContent = kindWord(entry);
      link.appendChild(kind);
      item.appendChild(link);
      results.appendChild(item);
      options.push(item);
    });
    if (searched && matches.length === 0) {
      var empty = document.createElement("li");
      empty.className = "empty";
      empty.setAttribute("role", "presentation");
      empty.textContent = counted(0);
      results.appendChild(empty);
    }
    results.hidden = !searched && matches.length === 0;
    input.setAttribute("aria-expanded", matches.length === 0 ? "false" : "true");
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

  // Only the newest query renders: an older one still waiting on the second
  // file must not overwrite the answer to a query typed after it.
  var asking = 0;
  function search(query) {
    var q = query.trim().toLowerCase().replace(/\s+/g, " ");
    var mine = ++asking;
    if (q.length < 2) { render([], false); return; }
    var digits = /^\d/.test(q);
    load(digits).then(function (both) {
      if (mine !== asking) return;
      var readings = readIdentifier(q.toUpperCase()).map(function (pair) {
        return pair[1].toLowerCase();
      });
      var scored = [];
      both[0].forEach(function (entry) {
        var s = score(entry, q);
        if (s >= 0) scored.push([s, entry]);
      });
      both[1].forEach(function (entry) {
        var s = numberScore(entry, q, readings);
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
    if (event.key === "Escape") { input.value = ""; asking++; render([], false); return; }
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
