"""The account pages' bodies: watched acts, settings sections, cards, rows and first steps.

After `account`, whose frame these sit in, and before the page families the site writes for
itself, which use none of these classes. Like `account`, it is here for the pages an account
service renders into the account shell, so the service carries no sheet of its own.

What the families are:

- **The summary strip** says how the reader hears, in a row of icon, label and value, with one
  link at its end; on a phone it stacks.
- **An act group** is one act's block on the watched list: a head on `--notice`, so it reads as
  the label of the rows under it, holding the act's name and how far the record has read it,
  then one row per watched item. A row is a grid of what is watched, its latest change and the
  remove control, and on a phone the latest change drops under what is watched. The coverage
  dot is drawn, so the sentence beside it says the same thing, and forced colours give it a
  border in `media`.
- **A settings section** puts its description on the left and its controls on the right, one
  column on a phone, and sections after the first are divided by a hairline.
- **A choice card** is a radio in a label. The native radio stays visible, so a browser without
  `:has` still shows which is chosen; where `:has` works the chosen card is ringed twice in the
  link colour on `--mark`. A card is a control, so its boundary is `--edge`.
- **Option rows** are checkboxes stacked inside a panel, a hairline between each.
- **Row lines** are a label, its description and an action, on the account's own tab.
- **The danger zone** is the alert's colour at its border and heading, on the alert's tint.
- **The first steps** are three numbered panels, because they are a sequence; one column on a
  phone. The aside inviting a second list is a dashed `--edge` box, a suggestion and not a
  control.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["ACCOUNT_PAGES"]

ACCOUNT_PAGES: Final = """\
.strip { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3) var(--space-5);
         margin: 0 0 var(--space-5); padding: var(--space-3) 1.25rem; }
.strip-item { display: flex; align-items: center; gap: .75rem; }
.strip-icon { display: inline-grid; place-items: center; flex: none; width: 2.25rem;
              height: 2.25rem; border-radius: var(--radius); background: var(--mark);
              color: var(--link); }
.strip-label { display: block; color: var(--muted); font: 600 var(--text-label)/1.3 var(--sans); }
.strip-value { display: block; font-size: var(--text-meta); line-height: 1.35; }
.strip-more { margin-left: auto; font-weight: 600; font-size: var(--text-meta); }
.section-head { display: flex; flex-wrap: wrap; align-items: flex-end;
                justify-content: space-between; gap: .75rem var(--space-4);
                margin: 0 0 var(--space-3); }
.section-head h2 { margin: 0; }
.section-head p { margin: var(--space-1) 0 0; }
.act-group { margin: 0 0 var(--space-3); overflow: hidden; }
.act-group-head { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem .75rem;
                  padding: .9rem 1.25rem; background: var(--notice);
                  border-bottom: 1px solid var(--rule); }
.act-name { color: var(--fg); font-size: var(--text-explain); font-weight: 600;
            line-height: 1.3; text-decoration: none; }
.act-name:hover { color: var(--link); text-decoration: underline; }
.act-coverage { display: inline-flex; align-items: center; gap: .4rem; margin-left: auto;
                color: var(--muted); font-size: var(--text-label);
                font-variant-numeric: tabular-nums; }
.act-coverage::before { content: ""; flex: none; width: .5rem; height: .5rem;
                        border-radius: 50%; background: var(--kind-inserted); }
.act-coverage--waiting::before { background: var(--kind-deferred); }
.act-coverage-note { flex-basis: 100%; margin: 0; color: var(--muted);
                     font-size: var(--text-meta); line-height: 1.5; }
.item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  grid-template-areas: "what latest remove";
  align-items: center;
  gap: .4rem var(--space-4);
  padding: .9rem 1.25rem;
  border-bottom: 1px solid var(--rule);
}
.item:last-child { border-bottom: 0; }
.item-what { grid-area: what; display: flex; flex-wrap: wrap; align-items: baseline;
             gap: var(--space-1) .75rem; min-width: 0; }
.item-what a { color: var(--fg); text-decoration: none; }
.item-what a:hover { color: var(--link); text-decoration: underline; }
.item-latest { grid-area: latest; color: var(--muted); font-size: var(--text-meta);
               white-space: nowrap; font-variant-numeric: tabular-nums; }
.item-remove { grid-area: remove; }
.item-remove form { margin: 0; }
.settings { display: grid; grid-template-columns: minmax(0, 18rem) minmax(0, 1fr);
            gap: var(--space-3) var(--space-5); padding: var(--space-4) 0; }
.settings + .settings { padding-top: var(--space-5); border-top: 1px solid var(--rule); }
.settings-intro h2 { margin: 0; font-size: var(--text-h3); }
.settings-intro p { margin: var(--space-2) 0 0; color: var(--muted); font-size: var(--text-meta);
                    line-height: 1.5; }
.choice-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem;
                margin: 0; padding: 0; border: 0; }
.choice {
  position: relative;
  display: block;
  padding: var(--space-3) var(--space-3) var(--space-3) 3rem;
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  background: var(--panel);
  font-weight: 400;
  cursor: pointer;
}
.choice input { position: absolute; left: 1.1rem; top: 1.3rem; width: 1.1rem; height: 1.1rem;
                margin: 0; accent-color: var(--link); }
.choice strong { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2);
                 font-size: var(--text-body); line-height: 1.35; }
.choice:hover { border-color: var(--link); }
.choice:has(input:checked) { border-color: var(--link); box-shadow: inset 0 0 0 1px var(--link);
                             background: var(--mark); }
.option-rows { overflow: hidden; }
.option {
  display: flex;
  align-items: flex-start;
  gap: .9rem;
  margin: 0;
  padding: var(--space-3) 1.1rem;
  border-bottom: 1px solid var(--rule);
  font-weight: 400;
  cursor: pointer;
}
.option:last-child { border-bottom: 0; }
.option input { flex: none; width: 1.1rem; height: 1.1rem; margin: .2rem 0 0;
                accent-color: var(--link); }
.option strong { display: block; font-size: var(--text-body); line-height: 1.4; }
.rows { overflow: hidden; }
.row-line { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
            gap: .75rem var(--space-4); padding: 1.1rem 1.25rem;
            border-bottom: 1px solid var(--rule); }
.row-line:last-child { border-bottom: 0; }
.row-line > * { margin: 0; }
.row-line p { color: var(--muted); font-size: var(--text-meta); line-height: 1.5; }
.danger-zone { padding: 1.25rem; border: 1px solid var(--alert); border-radius: var(--radius);
               background: var(--alert-tint); color: var(--fg); }
.danger-zone h2, .danger-zone h3 { margin: 0 0 var(--space-2); color: var(--alert); }
.danger-zone p { max-width: var(--measure); }
.danger-zone form { margin: 0; }
.steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3);
         margin: 0 0 var(--space-5); padding: 0; list-style: none; }
.steps > .step { padding: 1.4rem 1.4rem var(--space-4); }
.steps > .step h3 { margin: 0; }
.steps > .step p { margin: var(--space-2) 0 0; color: var(--muted); font-size: var(--text-meta);
                   line-height: 1.5; }
.step-number { display: grid; place-items: center; width: 2rem; height: 2rem;
               margin: 0 0 .9rem; border: 2px solid var(--link); border-radius: 50%;
               color: var(--link); font-weight: 600; font-size: var(--text-meta); }
.aside { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
         gap: .75rem var(--space-4); margin-top: var(--space-5); padding: 1.1rem 1.25rem;
         border: 1px dashed var(--edge); border-radius: var(--radius); }
.aside > * { margin: 0; }
@media (max-width: 40rem) {
  .strip { flex-direction: column; align-items: flex-start; }
  .strip-more { margin-left: 0; }
  .act-group-head { padding: .75rem var(--space-3); }
  .act-coverage { margin-left: 0; flex-basis: 100%; }
  .item { grid-template-columns: minmax(0, 1fr) auto;
          grid-template-areas: "what remove" "latest remove"; padding: .75rem var(--space-3); }
  .item-latest { white-space: normal; }
  .settings { grid-template-columns: minmax(0, 1fr); }
  .choice-cards { grid-template-columns: minmax(0, 1fr); }
  .steps { grid-template-columns: minmax(0, 1fr); }
  .row-line { padding: var(--space-3); }
}
"""
