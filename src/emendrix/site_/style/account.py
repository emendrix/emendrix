"""The account frame: the header's account link, the page head, tabs, panels and banners.

After `forms` in the cascade, because these pages are forms first: a rule here may rely on
`button`, `.button`, `.notice` and `.check`, and nothing before it relies on a rule here. No
page this package writes uses a class of this module but the header's account link; the rest
is for the pages an account service renders into the account shell, which link this sheet and
nothing else. The page bodies' own families, the watched acts, the settings sections, the cards
and the first-visit steps, are in `account_pages`, which follows this module.

**The header link** sits after the search mount, so a service can replace it with the reader's
identity without touching the navigation. It is an outlined control in `--edge`, the colour a
control's boundary is held to, and a signed-in reader's version seats a circled initial before
the address. On a phone the search box takes the second row by `order`, so the wordmark, the
navigation and the link share the first, and the address is clipped the way `.visually-hidden`
clips, never removed: the link's accessible name is its `aria-label`, and the initial stays.

**State is never colour alone.** The current tab is the text colour, an underline and the
weight, where the others are muted; the current list is ringed twice as thick as the others;
a banner says what it is in its words as well as by its rule.

`.button.quiet` is only ever the compound: `.quiet` alone names the gathered section of an
event page. `.step` is only ever reached inside `.steps`, because `.chg.step` names a change
on an amending act's page.

Forced colours for these rules live in `media`, which comes last for the reason it gives.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["ACCOUNT"]

ACCOUNT: Final = """\
header.bar .account {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  padding: .45rem .9rem;
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--fg);
  font: 600 var(--text-meta)/1.4 var(--sans);
  text-decoration: none;
  white-space: nowrap;
}
header.bar .account:hover { border-color: var(--link); color: var(--link); }
header.bar .account:focus-visible { outline: 3px solid var(--link); outline-offset: 2px; }
header.bar .account--in { padding: .2rem .75rem .2rem .2rem; border-color: var(--fg); }
.account-initial {
  display: inline-grid;
  place-items: center;
  flex: none;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  background: var(--mark);
  color: var(--link);
  font-size: var(--text-label);
}
.account-email { min-width: 0; max-width: 18ch; overflow: hidden; text-overflow: ellipsis; }
/* A named reader's link is wider than the word, so the search box gives up its width rather
   than push the link onto a row of its own on a wide screen. */
header.bar:has(> .account--in) #search { flex-basis: 12rem; }
.account-head { margin: 0 0 var(--space-4); }
.account-eyebrow { margin: 0 0 var(--space-1); color: var(--muted);
                   font: 600 var(--text-caption)/1.3 var(--sans); }
.account-head h1 { margin-bottom: var(--space-2); }
.account-lede { max-width: var(--measure); margin: 0; color: var(--muted);
                font-size: var(--text-lede); line-height: 1.45; }
.tabs {
  display: flex;
  gap: 0 var(--space-5);
  margin: 0 0 var(--space-5);
  border-bottom: 1px solid var(--rule);
  overflow-x: auto;
  scrollbar-width: none;
}
.tabs a {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: -1px;
  padding: .75rem 0;
  border-bottom: 2px solid transparent;
  color: var(--muted);
  font-weight: 600;
  font-size: var(--text-meta);
  text-decoration: none;
  white-space: nowrap;
}
.tabs a:hover { color: var(--fg); }
.tabs a[aria-current="page"] { color: var(--fg); border-bottom-color: var(--fg); }
.tabs .count {
  padding: .05rem .45rem;
  border-radius: var(--radius);
  background: var(--mark);
  color: var(--link);
  font-size: var(--text-label);
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
}
/* A panel on the page ground is a small step in the dark scheme, so its hairline carries it. */
.panel { background: var(--panel); border: 1px solid var(--rule); border-radius: var(--radius); }
.banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3) var(--space-4);
  margin: 0 0 var(--space-4);
  padding: var(--space-3) 1.25rem;
  border: 1px solid var(--edge);
  border-left-width: 4px;
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--fg);
}
.banner p { flex: 1 1 30rem; margin: 0; font-size: var(--text-meta); line-height: 1.5; }
.banner form { margin: 0; }
.banner--alert { background: var(--alert-tint); border-color: var(--alert); }
.banner--info { border-left-color: var(--link); }
.banner--ok { background: var(--kind-inserted-tint); border-color: var(--kind-inserted); }
.lists { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2);
         margin: 0 0 var(--space-4); padding: 0; list-style: none; }
.lists a {
  display: inline-flex;
  align-items: center;
  gap: .6rem;
  padding: var(--space-2) .9rem;
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--fg);
  font-weight: 600;
  font-size: var(--text-meta);
  text-decoration: none;
}
.lists a:hover { border-color: var(--link); }
.lists a[aria-current="true"] { border-color: var(--fg); box-shadow: inset 0 0 0 1px var(--fg); }
.lists .new { border-style: dashed; border-color: var(--link); background: transparent;
              color: var(--link); }
.state-on, .state-off {
  display: inline-flex;
  align-items: center;
  padding: .12rem .45rem;
  border: 1px solid;
  border-radius: var(--radius);
  font: 600 var(--text-label)/1.25 var(--sans);
  white-space: nowrap;
}
.state-on { color: var(--kind-inserted); background: var(--kind-inserted-tint);
            border-color: var(--kind-inserted); }
.state-off { color: var(--provenance); background: var(--provenance-tint);
             border-color: var(--edge); }
.button.small, button.small { padding: .3rem .75rem; font-size: var(--text-label); }
/* `margin` is reset because the bare `.quiet` of an event page sets one. */
.button.quiet, button.quiet {
  margin: 0;
  padding: .3rem var(--space-2);
  border-color: transparent;
  background: transparent;
  color: var(--muted);
  font-size: var(--text-label);
}
.button.quiet:hover, button.quiet:hover { color: var(--fg); text-decoration: underline; }
textarea {
  display: block;
  width: 100%;
  max-width: var(--measure);
  min-height: 8rem;
  margin-top: var(--space-1);
  padding: .55rem .75rem;
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--fg);
  font: 400 var(--text-body)/1.5 var(--sans);
  resize: vertical;
}
textarea:focus-visible { outline: 3px solid var(--link); outline-offset: 1px; }
/* The arrow is `base`'s `.back::before`, silent to a screen reader like every drawn arrow. */
.back { display: inline-block; margin: 0 0 var(--space-3); font-size: var(--text-meta); }
@media (max-width: 40rem) {
  #search, header.bar:has(> .account--in) #search { order: 1; flex-basis: 100%; }
  header.bar .account { flex: none; position: relative; }
  header.bar:has(> .account) nav { margin-right: 0; }
  header.bar .account--in { padding: .2rem; }
  .account-email {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
    border: 0;
  }
  .tabs { gap: 0 var(--space-4); margin-bottom: var(--space-4); }
  .account-lede { font-size: var(--text-body); }
}
"""
