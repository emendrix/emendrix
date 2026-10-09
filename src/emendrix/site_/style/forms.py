"""Forms: fields, buttons, checkbox rows, a notice box and a list table.

After `pages` in the cascade and relied on by nothing before it. No page this package writes
holds a form; these rules are here for the pages an account service renders into the account
shell, which link this stylesheet and nothing else, so the service's pages and the site share
one look without the service carrying a sheet of its own. Every colour is a token, so both
schemes are answered by the palette.

Three decisions follow the palette's own rules. A field's border is `--edge`, not `--rule`,
because the extent of a form control is the information and `--edge` is the line colour held
to 3:1. A primary button is the link colour with the page ground as its text, a pair checked
in both schemes, and a destructive one is the alert colour in the same way. A notice is a
panel with an `--edge` border and a coloured rule at its start, because `--notice` belongs to
the not-legal-advice block alone; an alert notice takes the alert's tint and colour, and says
what it is in words as well, since colour is never the only carrier of meaning.

The bordered button is `.secondary` rather than `.quiet`, because `.quiet` already names the
gathered section of an event page and its margin would reach a button of that name.

On a phone, under the breakpoint every other module uses, a form's buttons fill the width.

This text is minted, not escaped, like every module of the package.
"""

from __future__ import annotations

from typing import Final

__all__ = ["FORMS"]

FORMS: Final = """\
form.stack { display: grid; gap: var(--space-3); max-width: var(--measure);
             margin: 0 0 var(--space-4); }
form.stack > * { margin: 0; }
label { display: block; font-weight: 600; font-size: var(--text-meta); }
label .hint { display: block; font-weight: 400; color: var(--muted); }
input[type="email"], input[type="text"], select {
  display: block;
  width: 100%;
  max-width: var(--measure);
  margin-top: var(--space-1);
  padding: .55rem .75rem;
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--fg);
  font: 400 var(--text-body)/1.4 var(--sans);
}
input[type="email"]:focus-visible, input[type="text"]:focus-visible, select:focus-visible
  { outline: 3px solid var(--link); outline-offset: 1px; }
button, .button {
  display: inline-block;
  padding: .55rem 1.1rem;
  border: 1px solid transparent;
  border-radius: var(--radius);
  background: var(--link);
  color: var(--bg);
  font: 600 var(--text-meta)/1.4 var(--sans);
  text-decoration: none;
  cursor: pointer;
}
button:hover, .button:hover { text-decoration: underline; }
button:focus-visible, .button:focus-visible
  { outline: 3px solid var(--link); outline-offset: 2px; }
button.secondary, .button.secondary { background: transparent; color: var(--link);
                                      border-color: var(--edge); }
button.danger, .button.danger { background: var(--alert); color: var(--bg); }
.check { display: flex; align-items: baseline; gap: var(--space-2); font-weight: 400; }
.check input { flex: none; width: 1.1rem; height: 1.1rem; margin: 0; accent-color: var(--link); }
.notice {
  max-width: var(--measure);
  margin: 0 0 var(--space-4);
  padding: var(--space-3);
  background: var(--panel);
  color: var(--fg);
  border: 1px solid var(--edge);
  border-left: 4px solid var(--link);
  border-radius: var(--radius);
}
.notice.alert { background: var(--alert-tint); border-left-color: var(--alert); }
.notice > :last-child { margin-bottom: 0; }
table.list { width: 100%; max-width: var(--measure); border-collapse: collapse;
             margin: 0 0 var(--space-4); font-size: var(--text-meta); }
table.list th, table.list td { padding: var(--space-2); text-align: left; vertical-align: top;
                               border-bottom: 1px solid var(--rule); }
table.list th { color: var(--muted); font-weight: 600; }
table.list td:last-child { text-align: right; }
@media (max-width: 40rem) {
  form.stack button, form.stack .button { width: 100%; text-align: center; }
}
"""
