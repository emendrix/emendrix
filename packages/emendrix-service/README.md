# emendrix-service

The account service beside emendrix: email alerts for watched acts and provisions, over the
published change record. A reader follows a "Watch this" link on the site, confirms an address,
and receives an email listing exactly the watched provisions the record says changed, instant,
daily or weekly, or follows them in a personal Atom feed. One click stops the email; one button
exports the reader's data and one deletes it.

It filters what the record already states and never re-derives it. It reads the record only
through `emendrix-record`, makes no model call, and the pipeline imports nothing of it and does
not know it exists. [`docs/accounts.md`](../../docs/accounts.md) is what it does, the data it
holds, the operator's duties, the security checklist and the backups; this file is how to run it.

> Not legal advice: this output is machine-computed from published texts, carries no lawyer's
> review, and is engineering assistance only.

## Install

From the repository root, as a workspace member:

```bash
uv sync --all-extras --dev          # installs emendrix-service with the root's dev group
uv run emendrix-service --help
```

or as an image, built from the repository root against the workspace lockfile:

```bash
docker build -f packages/emendrix-service/Dockerfile -t ghcr.io/emendrix/emendrix-service:0.1.0 .
docker run --rm ghcr.io/emendrix/emendrix-service:0.1.0 --help
```

It needs PostgreSQL 17 (the version its tests and the reference deployment run), a changelogs
repository and a site built from it with `emendrix site build --accounts --site-url ...`, and an
SMTP relay to send through.

## Configuration

Every setting is an environment variable, read in `src/emendrix_service/settings.py` and nowhere
else; no file is read. A command that needs an unset setting stops with
`emendrix-service: EMENDRIX_SERVICE_<NAME> is not set` and exit code 2. Passwords and keys are
secret types and never print.

| `EMENDRIX_SERVICE_...` | Needed by | Meaning |
|---|---|---|
| `DATABASE_URL` | everything | `postgresql+psycopg://user:password@host:5432/name`; no other scheme is accepted |
| `SITE_URL` | everything | the public base, `https://...` with no trailing slash; every emailed link is built on it |
| `ALLOWED_HOSTS` | everything | comma-separated `Host` values the web process answers |
| `SECRET_KEY` | everything | base64 of at least 32 bytes; the root of every signed token. Changing it signs everyone out and voids every unsubscribe link |
| `CHANGELOGS` | `load`, `tick` | the changelogs repository's directory, read-only |
| `CATALOGUE` | `load`, `tick` | a built site's `api/v1/catalogue.json` |
| `SHELL` | `serve` | a built site's `account-shell.html`, which every page fills |
| `PRIVACY_NOTICE` | sign-up | the operator's privacy notice as an HTML fragment (`docs/privacy-notice.template.html`); without it sign-up refuses |
| `SIGNUP_OPEN` | | `false` refuses new addresses; sign-in keeps working. Default `true` |
| `SIGNUP_ALLOWLIST` | | comma-separated addresses that may sign up while sign-up is closed |
| `LIVE_SINCE` | `notify`, `tick` | an ISO date; events the record detected before it are never emailed |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | `mail drain`, `tick` | the relay; port 587 and STARTTLS by default. `false` talks to it in the clear |
| `MAIL_FROM` | `mail drain`, `tick` | the `From` of every email, as `Name <address>` |
| `OPERATOR_EMAIL` | `status --email` | where the status block goes |
| `WEBHOOK_SECRET` | the provider hook | the path secret of `/u/hooks/scaleway/<secret>`; unset, the route answers 404 |
| `CLIENT_IP_HEADER` | `serve` | a single-value request header the proxy sets, naming the client address; trusted as given, so only the proxy may reach the service. Unset, the peer address |
| `TIMEZONE`, `DIGEST_HOUR` | `digest`, `tick` | when daily and weekly digests fall due; default `Europe/Brussels` and `7` |
| `BACKUP_TARGET` | `backup ship` | `user@host:directory` or `user@host:port:directory`, reached over SFTP |
| `BACKUP_SSH_KEY` | `backup ship` | the private key file the upload logs in with |
| `BACKUP_KNOWN_HOSTS` | `backup ship` | a known-hosts file listing the storage host's key; for a port other than 22 the host is written `[host]:port` |
| `BACKUP_AGE_RECIPIENT` | `backup ship` | the `age` public key (`age1...`) every backup is encrypted to |
| `BIND`, `PORT` | `serve` | the listener; default `0.0.0.0` and `8000` |

## Commands

Each command ends with one JSON line, `{"emendrix_service":"<command>","status":"complete",...}`
with its counts, or `"failed"` and exit code 1. Logs are JSON lines on stdout and never carry an
address, a token or a request body.

| Command | What it does | Marker counts |
|---|---|---|
| `serve` | the web process: `/account/`, `/u/`, `/healthz`, `/readyz` | |
| `migrate` | creates or upgrades the three schemas to the current revision | `head` |
| `load [--rebuild]` | reads the published record into `content`; `--rebuild` empties it first | `upserted`, `removed`, `skipped`, `unsettled` |
| `notify` | judges each new event once and writes what it owes each watchlist; queues instant email | `announced`, `eligible`, `deferred`, `matches`, `deliveries`, `failed` |
| `digest [--now ISO]` | queues the daily, weekly and monthly emails that are due | `daily`, `weekly`, `heartbeat`, `failed` |
| `mail drain [--limit N]` | sends due outbox rows, retrying transient refusals | `sent`, `retried`, `failed`, `suppressed` |
| `tick` | `load`, `notify`, `digest` and `mail drain` in turn; the job to run every five minutes | `loaded`, `announced`, `eligible`, `matches`, `deliveries`, `sent` |
| `retention` | applies the retention table | `login_tokens`, `sessions`, `bodies`, `deliveries`, `outbox`, `matches`, `mail_events`, `audit_log`, `reminded`, `deleted`, `failed` |
| `status [--email]` | prints one block of aggregate counts; `--email` also queues it to `OPERATOR_EMAIL` | `emailed` |
| `backup ship <dump>` | encrypts a `pg_dump -Fc` file with `age`, uploads it over SFTP, prunes to 7 daily and 4 weekly copies | `bytes`, `kept`, `pruned` |

`tick` needs `CHANGELOGS`, `CATALOGUE`, `LIVE_SINCE` and complete SMTP settings. `/healthz` says
the process is up; `/readyz` says the database answers, the schema is current and the shell
reads. Neither is meant to be proxied.

## Three ways to deploy it

- **The compose profile.** `deploy/compose.yaml` runs a Postgres, the web process and a job
  container under the profile `accounts`, with nginx routing `/account/` and `/u/` to it and the
  cron lines in its header. Without the profile, the deployment runs exactly as it does without
  the service. [`docs/accounts.md`](../../docs/accounts.md) §"Self-hosting with compose" walks it.
- **Any container platform.** One long-running `serve` behind a proxy that routes only
  `/account/` and `/u/` to it and sets the client-address header; `tick` every five minutes,
  `retention` and the backup nightly, and `status --email` daily as scheduled jobs; a
  PostgreSQL 17 the service owns three schemas in. The image holds no state, host or key.
- **None.** The site, the feeds, the JSON API and the MCP server need nothing from it. Build the
  site without `--accounts` and nothing links to it.

## Quick start against a local Postgres

```bash
docker run -d --name svc-db -p 5432:5432 -e POSTGRES_PASSWORD=local postgres:17-alpine
uv run emendrix site build --out /tmp/site --changelogs <changelogs> --site-url https://example.org --accounts

export EMENDRIX_SERVICE_DATABASE_URL=postgresql+psycopg://postgres:local@localhost:5432/postgres
export EMENDRIX_SERVICE_SITE_URL=https://example.org
export EMENDRIX_SERVICE_ALLOWED_HOSTS=localhost:8000
export EMENDRIX_SERVICE_SECRET_KEY="$(openssl rand -base64 32)"
export EMENDRIX_SERVICE_CHANGELOGS=<changelogs>
export EMENDRIX_SERVICE_CATALOGUE=/tmp/site/api/v1/catalogue.json
export EMENDRIX_SERVICE_SHELL=/tmp/site/account-shell.html
export EMENDRIX_SERVICE_PRIVACY_NOTICE=docs/privacy-notice.template.html

uv run emendrix-service migrate
uv run emendrix-service load
uv run emendrix-service status
uv run emendrix-service serve          # then open http://localhost:8000/account/signin
```

Without SMTP settings nothing is sent: every email waits in `app.outbox`, a sign-in link among
them, and its links are built on `SITE_URL`. The session cookie is `__Host-` and `Secure`, which
a browser accepts on `localhost` but on no other plain-http host. The template stands in for a
notice here only; a real deployment fills it in.

## Tests

The member's tests run in the root suite (`uv run pytest`) and start one `postgres:17-alpine`
container per session through Docker; `EMENDRIX_SERVICE_TEST_DATABASE_URL` points them at a server
instead. Without either they fail, naming both. They never send mail or reach the internet: mail
goes to a recording double, and the backup upload is tested against an SFTP server inside the
test process on `127.0.0.1`.
