# The account service: email alerts for watched provisions

An optional service that stands beside the static site. A reader follows a **"Watch this"** link
on an act or provision page, confirms an address, and from then on receives an email listing
exactly the watched provisions the published record says changed, instant, daily or weekly, or
follows the same changes in a personal Atom feed. One click stops the email, one button exports
everything held about the reader, and one button deletes it.

It lives in [`packages/emendrix-service`](../packages/emendrix-service/), a workspace member with
its own image, and [its README](../packages/emendrix-service/README.md) is how to run it: every
setting, every command, and a quick start against a local Postgres. This page is what it does and
why it holds, what it keeps about people, and what an operator owes them. The hosted instance at
<https://emendrix.eu> runs it; a self-hosted deployment may run it or not, and loses nothing the
pipeline does without it.

**Not legal advice.** An email from the service repeats what the published record states, which is
engineering assistance: a machine-computed description of textual differences between published
versions of legal acts. Every page, email, feed and export it produces carries that disclaimer.

## What it is, and what it is not

**It filters the record; it never re-derives it.** A watchlist is a set of natural keys: an act,
or a provision of one by its canonical location. A match is a set intersection between those keys
and the changes a published payload already states. An email line is a stored fact (the change's
heading, its type, its dispute reason, the dates the text added and removed) with the link to the
change on the site. Nothing in the service classifies, summarises, infers a date, reads law text
or decides what changed, and it makes no model call of any kind.

It is not a monitoring product with opinions about your obligations, not a paid service, and not
a second source of the record: what an email says is what the site and the JSON API
([`api.md`](./api.md)) say about the same change, and the site is the authority it links to.

## The account pages

A signed-in reader's account is three tabs, each one job:

| Tab | Route | What it holds |
|---|---|---|
| Watching | `/account/` | what is watched, grouped by act: each act's coverage, and each item with its newest change in the record |
| Delivery | `/account/delivery` | the email choice, the two extras (date flags, the monthly note), pausing, and the personal feed |
| Account | `/account/settings` | the address signed in, signing out here or everywhere, the export, and deleting the account |

- **A list appears only when there are two.** Every account holds its items in watchlists, but a
  reader with one never sees the word, a list's name, a rename box or a switcher: that list is
  their account. Creating a second list from the Watching tab brings in the switcher, each list's
  name, and renaming and deleting a list. Watching and Delivery then show one list at a time,
  chosen by `?list=<id>`; an id that is not the reader's own falls back to their oldest list.
- **The first visit** (no list, or one list that watches nothing) shows three steps and every act
  the catalogue lists, in the catalogue's order, each with a button to the watch landing.
- **An item's newest change** is the newest stored change the item would be emailed about, by the
  rules of [Matching](#matching), ordered by the change's in-force date or else the day its event
  was detected. It links the change on its event page; an item with none reads "No change recorded
  yet". All of it comes from one read of the watched acts' changes per page.
- **The header names the reader.** On the account pages the shell's account slot holds the
  reader's address and initial; every page the site writes says `Account` there instead, because a
  cached page cannot know who reads it.
- **Every post returns to its tab** with a notice code, never a value the reader typed:
  `/account/?list=<id>&notice=added`.
- **No script and no inline style.** The pages are links, forms and `<details>`, styled only by the
  site's stylesheet in both its colour schemes, which the content-security policy
  (`style-src 'self'`) enforces.
- **A suspended account** (mail to it refused or reported) still reaches all three tabs, read-only
  but for signing out, the export and deleting the account.

## Architecture

```
changelogs repository ─┐
site build: catalogue ─┴─► load ──► Postgres (content, app, notify)
                                       │
       tick: load ─► notify ─► digest ─► outbox ─► mail drain ─► SMTP relay
                                       │
serve: /account/ (session cookie), /u/ (token addresses) ◄── nginx ◄── reader
```

- **Three Postgres schemas.** `content` is the published record loaded for querying: acts,
  events, changes and provisions. It is derived, and `load --rebuild` empties and refills it at
  any time. `app` is user data: accounts, consents, sessions, watchlists, watch items, matches,
  deliveries, the outbox, suppressions, provider events and the audit log. `notify` is the
  notifier's own ledger: one row per event it has judged, so reloading `content` never alerts
  anyone twice. No foreign key runs from `app` into `content`; a user's rows name changes by
  natural key only (`corpus`, `act_key`, `event_key`, `location`, occurrence), so a reload never
  cascades into anyone's watchlist.
- **The loader** (`load`) reads only published artifacts: the changelogs repository's root index,
  act indexes and payloads, and the catalogue the site build writes at
  `api/v1/catalogue.json`. It skips every act whose index digest has not moved since the last
  load, and every event whose payload digest has not moved.
- **`tick`**, run every five minutes, is load, then notify, then digest, then the mail drain, each
  step logged and allowed to fail without stopping the next. It notices a new record by its root
  index digest, so the pipeline never learns that users exist: the pipeline commits and builds
  the site as it always does, and at most five minutes later the service picks it up.
- **The web process** (`serve`) answers `/account/` (pages that use the session cookie) and `/u/`
  (token-addressed endpoints that never read it: one-click unsubscribe, the personal feed, the
  mail provider's event hook). Its pages are the site's own chrome: a site built with
  `--accounts` writes `account-shell.html`, and the service fills its title, the account slot at
  the end of the header (the reader's address when signed in, `Account` otherwise), the content
  and the footer note ([`site.md`](./site.md) §"`--accounts`"); a shell without the slot, from a
  site build that predates it, still serves with its own header link. No JavaScript; every action is a plain form.
- **The boundary is checked, not promised.** The service never imports the pipeline; it reads
  the record through `emendrix-record`, the same reader the MCP server uses. The clock is read in
  one module, the environment in one, SQL only under `db/`, outbound connections only in the SMTP
  transport and the backup upload. Its architecture test fails the moment any of these appears
  anywhere else.

## Matching

A watch item is a whole act or one provision of it. An **act** item matches every change of that
act. A **provision** item at location `L` matches a change by the first rule that holds:

1. **at**: the change is at `L` or beneath it;
2. **inside**: a coordinate the record lists as changed within the unit lies inside `L`, or `L`
   inside it;
3. **container**: the change lists no coordinate within the unit, and `L` lies inside the
   changed unit; the record says the unit moved and not which part of it.

Containment is token-prefix containment on canonical strings: `AR 6 PA 1` is within `AR 6`, and
`AR 60` is not within `AR 6`. Every email line says which item matched and how: "you watch
Article 6", or for the third rule "you watch Article 6(1); this change is to Article 6, and the
record does not say which part of it moved".

A location is typed as a canonical string (`AR 6`, `AN IV`, `AR 6 PA 1`) or in a few plain forms:
`Article 6`, `Art. 6`, `Article 6(1)`, `Article 6a`, `Annex I`, `Annex 4`. A point
(`Article 6(1)(a)`) is refused, because below a paragraph the record spells coordinates in more
than one order and choosing one would be a guess; name its paragraph, or type the canonical
string. A location the record has never named is accepted and shown as "no change recorded yet".
The canonical form of an annex is its Roman numeral: `Annex 4` is read as `AN IV`, but the
canonical string `AN 4` typed as is stays `AN 4`, which matches nothing the record stores.

Matching happens once, when an event is announced. A watch item added later is not emailed older
changes; the personal feed matches live and shows them.

## Which events are announced

Each event is judged once, by its key, and the judgement never changes. The first rule that holds
decides:

1. **bootstrap**: the notifier has judged nothing yet. Everything already in the record when the
   service goes live is history, and no email is sent about it.
2. **before live**: the event was detected before `EMENDRIX_SERVICE_LIVE_SINCE`.
3. **stale**: its newest in-force date lies more than 60 days before it was detected, which is
   what a backfill of an old consolidation looks like. The consolidation lag behind entry into
   force is 10 to 17 days, so a real poll always passes.
4. **fresh**: otherwise, including an event with no in-force date.

An eligible event whose page the catalogue does not name yet waits for the next site build, so no
email links a page that does not exist. **A repair never re-alerts**: a corrected payload changes
the event's digest, `content` follows it, and the announcement stands.

## Email

- **Cadence, per watchlist.** `instant` sends one email per announced event; `daily` and `weekly`
  send one digest per day or ISO week, at `EMENDRIX_SERVICE_DIGEST_HOUR` (7 by default) in
  `EMENDRIX_SERVICE_TIMEZONE` (`Europe/Brussels` by default), the weekly one on Monday. A run that
  missed the hour sends the period's one email later the same day or week. `none` sends nothing
  and keeps the matches for the feed. A watchlist can also be paused, on the Delivery tab. New
  watchlists are weekly.
- **The monthly note.** On the first Monday of a month, a watchlist that was owed nothing in the
  month before gets one "still watching" email listing what it watches, so silence is never
  mistaken for a broken service. It is on by default and can be turned off per watchlist.
- **Date changes.** A change that adds or removes a date in the text, or a deferral, is flagged in
  the email as "a date in the text changed", and an instant email carrying one says so in its
  subject. A date
  is called an application date only when the record read one; the email never says "your
  deadline moved".
- **What an email never says.** It carries no provision text and no prose of its own about what a
  change means. Each line is a stored heading and stored facts with the link to the change, its
  dispute reason when the record marks it disputed, and why the reader received it.
- **Every email** carries `List-Unsubscribe` with a one-click address and
  `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058), and a footer with the
  disclaimer, why it was sent and how to stop it.
- **Delivery.** Every email is first a row in the outbox, written in the same transaction as the
  fact it reports. The drain sends due rows through the configured SMTP relay, retries a
  transient refusal after 1, 10 and 60 minutes, and then marks the row failed. A permanent
  refusal of the recipient, a hard bounce, a complaint, or a third soft bounce within seven days
  suppresses the address (kept as its sha256 only) and suspends the account. A suspended reader
  can still sign in, export and delete.

## The data held, and why

| Data | Purpose | Lawful basis |
|---|---|---|
| The email address | sending the alerts the reader configured; signing in | Art. 6(1)(b) GDPR, performing the service the reader asked for |
| Watchlists and watch items | deciding which changes to send | Art. 6(1)(b) |
| Consents: the double opt-in and the version (a digest) of the privacy notice accepted | proving the address belongs to the reader and which notice they saw | Art. 6(1)(b) |
| Sessions and login links, stored only as sha256 digests | keeping a reader signed in; signing in | Art. 6(1)(b) |
| Matches, deliveries and sent emails | sending each change once and retrying a failed send exactly | Art. 6(1)(b) |
| Provider events, suppressions and the audit log of account actions | keeping mail deliverable, stopping mail to an address that refused it, security | Art. 6(1)(f), legitimate interest in a secure and deliverable service |

Double opt-in proves that the address is the reader's; it is not the lawful basis. There is no
marketing email, so no consent flow exists for one. A watchlist can reveal what a company works
on, so the notice says so.

**Retention.** Every row but the last is one declaration in the code (`leave/logic.py`), applied
each night by `retention`; the last is `backup ship`'s pruning. The deleted-account page and the
privacy notice state them:

| Rows | Kept |
|---|---|
| Login links | deleted 24 hours after they expire (they live 30 minutes) |
| Sessions | deleted once expired, 30 days after last use |
| Email bodies | blanked 30 days after the email was sent, or written when it was never sent |
| Emails and deliveries | deleted 180 days after they were written |
| Matches | deleted with the delivery that carried them; never carried, after 180 days |
| Mail provider events | deleted after 30 days |
| The audit log | deleted after 12 months |
| Inactive accounts | unseen for 24 months: warned by email; deleted 30 days later unless seen again |
| Backups | each copy is pruned within 35 days |

An account is "seen" by a sign-in, a page, a feed fetch or an unsubscribe click.

**Export and delete.** `/account/export` is a JSON file of every row naming the reader: account,
consents, sessions (without digests), watchlists, items, matches, deliveries, the emails sent
(without bodies or headers, which carry the unsubscribe token) and the audit log. Deleting an
account removes every row that names it, by cascade or by address, at once. The one exception is a
complaint: the address's sha256 stays in `suppressions`, so deleting an account never reopens
mail to someone who said the mail was unwanted. Copies in the backups age out within 35 days.

## What the operator owes

Whoever runs a deployment of the service is the **controller** of the personal data it holds,
and these duties are theirs, not this project's:

- **Publish a privacy notice.** Fill in
  [`privacy-notice.template.html`](./privacy-notice.template.html) and point
  `EMENDRIX_SERVICE_PRIVACY_NOTICE` at the result. Without one, sign-up refuses. The service
  shows it at `/account/privacy` and records which version each reader accepted. A filled notice
  is the operator's own document and is never committed to this repository.
- **Sign the processor agreements** of the mail provider, the hosting provider, any CDN or proxy
  in front of the site, and the backup storage host.
- **Keep a record of processing** (Art. 30): what is held, why, for how long, and with which
  processors. The two tables above are its substance.
- **Answer requests.** Export and delete are self-service; a request by email is answered with the
  same code path, by signing in as the reader would.
- **Run the backups and the retention job**, and keep the `age` private key offline.

## Security checklist

Each item is held by a test in `packages/emendrix-service/tests/`.

| Property | Test |
|---|---|
| A login link is consumed only by a POST from its page, so a mail scanner's GET does nothing | `test_svc_auth_signin_sends_a_link_only_the_post_consumes` |
| Login links and sessions are random and stored only as sha256 digests | `test_svc_auth_tokens_are_random_and_stored_by_hash` |
| The session cookie is `__Host-`, `Secure`, `HttpOnly` and `SameSite=Lax`, sliding over 30 days | `test_svc_auth_signin_sends_a_link_only_the_post_consumes`, `test_svc_auth_a_session_slides_and_expires` |
| Every account POST carries a CSRF token bound to the browser | `test_svc_web_every_account_post_is_csrf_checked`, `test_svc_web_a_token_from_another_browser_is_403` |
| Login links are rate-limited per address (3 an hour) and per client address (20 an hour) | `test_svc_auth_the_fourth_link_for_one_address_is_not_sent`, `test_svc_auth_the_twenty_first_link_from_one_address_is_not_sent` |
| An unknown address gets the same page as a known one and no email, so sign-in does not reveal who has an account | `test_svc_auth_an_unknown_address_gets_the_same_page_and_nothing` |
| One account cannot read or change another's watchlists or feed | `test_svc_watch_editor_one_account_cannot_touch_another`, `test_svc_feed_another_readers_watchlist_cannot_be_given_a_feed` |
| Every page sends a CSP that allows its own forms and no script | `test_svc_web_the_policy_allows_own_forms_and_no_script` |
| No log line carries an address or a token | `test_svc_auth_every_email_carries_the_disclaimer_and_no_log_line_a_secret`, `test_svc_web_token_paths_are_not_logged`, `test_svc_leave_the_token_never_reaches_the_log` |
| One-click unsubscribe works with no cookie and no CSRF token, as RFC 8058 requires | `test_svc_leave_a_one_click_post_with_no_cookie_stops_the_email_once` |
| The mail provider's hook answers 404 without its path secret | `test_svc_mail_hooks_a_wrong_or_missing_secret_is_not_found` |
| The status block names no one | `test_svc_ops_status_counts_everything_and_names_no_one` |
| A backup is encrypted to a key the service does not hold, and a storage host with an unknown key is refused | `test_svc_ops_ship_encrypts_so_only_the_offline_key_decrypts`, `test_svc_ops_ship_refuses_a_host_key_the_file_does_not_list` |

The rate limits are counted in the web process's memory, so they reset when it restarts and are
per process; one process is the deployment this is built for. The client address is read from
`EMENDRIX_SERVICE_CLIENT_IP_HEADER`, which the service trusts as given, so only the proxy that
sets that header may reach the service.

## Operating it

Every command ends with one JSON marker line,
`{"emendrix_service":"<command>","status":"complete",...}`, or `"failed"` with exit code 1; a command that cannot run as configured exits 2 with one line
naming the missing setting. Alert on the absence of `tick` complete for 30 minutes and of `backup`
complete for 26 hours.

- **`status`** prints one block of counts: the last load and its root index digest, events
  judged in 24 hours, deliveries in 24 hours by kind, the outbox queue and its oldest row, failed
  sends, provider events over seven days, suppressions, accounts, watchlists, and watch items per
  act. Counts only: it names no address and no account. `status --email` also queues the block to
  `EMENDRIX_SERVICE_OPERATOR_EMAIL`, and the next `tick` sends it. Run daily, it is the canary for
  the mail transport: a morning without it means the relay or the scheduler stopped.
- **The mail provider's events.** The hook at `/u/hooks/scaleway/<secret>` reads the provider's
  bounce, complaint and delivery events. Without it hard bounces are recorded only when the relay
  refuses a recipient while sending, and soft bounces and complaints not at all. Its subscription
  confirmation is logged once, as a warning carrying the confirmation address, for the operator
  to open by hand; the service makes no outbound request for it.
- **One-click unsubscribe works only while the service is up.** The address in every email is the
  service's; a reader whose click fails during an outage can use the account page later, and the
  email stops either way.

## Backups

`app` holds every account and watchlist, and **it is not rebuildable**: a deployment that runs the
service without backups loses its readers' watchlists with its disk. `notify` is backed up too: it
holds which events were announced and the schema's migration version, so a restored deployment
picks up where it stopped. `content` is not: it is rebuilt from the changelogs by
`load --rebuild`.

Each night:

1. `pg_dump -Fc -n app -n notify` runs in the database's own image, because a `pg_dump` of
   another major version than the server's refuses to run.
2. `pg_restore --list` reads the dump whole. A dump it cannot list is never shipped.
3. `emendrix-service backup ship <dump>` checks the file opens as a custom-format archive,
   encrypts it to the `age` public key in `EMENDRIX_SERVICE_BACKUP_AGE_RECIPIENT`, uploads it over
   SFTP to `EMENDRIX_SERVICE_BACKUP_TARGET` as `emendrix-app-YYYYMMDD.dump.age` (written under a
   temporary name and renamed when complete), and prunes. The host's key must be listed in
   `EMENDRIX_SERVICE_BACKUP_KNOWN_HOSTS`; a host presenting any other key is refused before a byte
   is sent. Its marker carries `bytes` (the encrypted copy's size), `kept` and `pruned`.
4. **Pruning** keeps every copy dated within the last seven days and, for each of the four ISO
   weeks before the current one, the earliest copy of that week (the Monday's when the Monday's
   job ran). The oldest copy kept is at most 34 days old, which is what lets the notice promise
   35. An upload interrupted on an earlier day leaves `<name>.part`, which is pruned too; any other
   file is never touched.

**The service cannot decrypt a backup.** The `age` private key stays offline with the operator,
so no automated drill can restore one, and a stolen copy discloses nothing. The restore drill is
manual, quarterly, with the offline key, into a throwaway database:

```bash
age --decrypt -i offline.key emendrix-app-YYYYMMDD.dump.age > app.dump
docker network create drill
docker run -d --name drill-db --network drill -e POSTGRES_PASSWORD=drill postgres:17-alpine
docker run --rm --network drill \
  -e EMENDRIX_SERVICE_DATABASE_URL=postgresql+psycopg://postgres:drill@drill-db:5432/postgres \
  -e EMENDRIX_SERVICE_SITE_URL=https://example.org -e EMENDRIX_SERVICE_ALLOWED_HOSTS=example.org \
  -e EMENDRIX_SERVICE_SECRET_KEY="$(openssl rand -base64 32)" \
  ghcr.io/emendrix/emendrix-service:0.1.0 migrate
docker cp app.dump drill-db:/tmp/app.dump
docker exec drill-db pg_restore -U postgres -d postgres --clean --if-exists --exit-on-error /tmp/app.dump
docker exec drill-db psql -U postgres -c 'SELECT count(*) FROM app.users' -c 'SELECT count(*) FROM app.watch_items'
docker rm -f drill-db && docker network rm drill
```

`migrate` comes first because the dump holds `app` and `notify` only: it creates the `citext`
extension and the `content` schema the dump does not carry, and `--clean` then replaces the two
schemas it does. Restoring a deployment is the same three moves against its own database:
`migrate`, `pg_restore --clean --if-exists`, then `load --rebuild` to refill `content`.

## Self-hosting with compose

The reference deployment ([`../deploy/compose.yaml`](../deploy/compose.yaml)) runs the service
under the compose profile `accounts`: a Postgres (`db`), the web process (`account`) and a
one-shot container for its commands (`account-job`). Without the profile none of it starts and
the deployment behaves as it does without the service; nginx resolves the service's address per
request, so `/account/` and `/u/` answer 502 and every other path is served as before.

1. In `deploy/.env` (see `deploy/.env.example`), set `POSTGRES_PASSWORD`,
   `EMENDRIX_SERVICE_SECRET_KEY` (`openssl rand -base64 32`), `EMENDRIX_SERVICE_LIVE_SINCE`, the
   `EMENDRIX_SERVICE_SMTP_*` settings and `EMENDRIX_SERVICE_MAIL_FROM` for any SMTP relay, and
   `EMENDRIX_ACCOUNTS_FLAG=--accounts`.
2. Fill in the privacy notice and save it as `deploy/account/privacy-notice.html`. That directory
   keeps every file in it out of git; the backup job's SSH key (`backup_ed25519`) and known-hosts
   file (`known_hosts`) go there too, readable by the image's user (uid 10001).
3. Start it: `docker compose --profile accounts up -d db account`, then
   `docker compose --profile accounts run --rm account-job migrate`, then the next `page` run
   adds the links and the shell, and `run --rm account-job load` fills `content`.
4. Add the cron lines in `compose.yaml`'s header: `tick` every five minutes, `retention` and the
   backup nightly, `status --email` each morning.

The nginx locations for `/account/` and `/u/` in [`../deploy/default.conf`](../deploy/default.conf)
set `X-Emendrix-Client-IP` from `$remote_addr` (the service reads it through
`EMENDRIX_SERVICE_CLIENT_IP_HEADER`). Behind a TLS-terminating proxy or tunnel that sends a
client-address header of its own, put that header's variable there instead. Both locations send
their own headers and no Content-Security-Policy, because the service sends one that allows its
own forms, and a second policy inherited from an enclosing level would also be enforced. `/u/`
paths carry secrets and are not written to the access log.

Any other container platform runs the same image the same way: `serve` as a long-running process
behind a proxy that routes only `/account/` and `/u/` to it, and `tick`, `retention`,
`status --email` and the backup as scheduled jobs. The service needs no state on disk of its own.

## What it does not do, and known gaps

- **No alerting on its own silence.** The status email and the markers are what an operator
  watches; nothing in the service pages anyone.
- **Provider events depend on the provider's webhook.** The hook reads Scaleway Transactional
  Email's events, whose webhooks were a beta needing a quota request when read on 2026-10-09.
  Without them, hard bounces come only from refusals at sending time.
- **Provider events are not deduplicated.** A redelivered event is counted again, so a redelivered
  soft bounce counts twice toward the three that suppress an address.
- **A watchlist switched from daily or weekly to instant or none never emails the matches it was
  still owed.** They stay in the feed.
- **No cap** on watchlists per account or items per watchlist.
- **`AN 4` typed as a canonical string is not read as `AN IV`**, so it matches nothing the record
  stores; `Annex 4` is.
- **The loader trusts an act index's digest.** If an act index on disk is older than the one the
  root index names and its counts agree, the loader cannot tell.
- **No presets, amending-act watch items, webhooks or bots.** A watch item is an act or a
  provision.
