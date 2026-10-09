"""The whole schema of the first release: `app`, `content` and `notify`. Revision ID: 0001.

The schemas, the `citext` extension and every enum type are created before any table names them.
Every name and value is written out rather than imported from the models, because a revision
describes the schema as it stood when it ran; the database tests hold it and the models equal.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("app", "content", "notify")

ENUMS = {
    "user_status": "active suspended",
    "consent_kind": "service_email privacy_notice",
    "token_purpose": "signup signin",
    "cadence": "instant daily weekly none",
    "item_kind": "act provision",
    "delivery_kind": "instant daily weekly heartbeat",
    "outbox_purpose": "signin signup instant daily weekly heartbeat inactivity operator",
    "outbox_status": "queued sent failed suppressed",
    "suppression_reason": "hard_bounce complaint soft_bounces",
    "mail_event_kind": "hard_bounce soft_bounce complaint delivered",
    "audit_action": "export delete feed_rotate signout_all unsubscribe",
}

TEXT = sa.Text()
STAMP = sa.DateTime(timezone=True)
JSON = postgresql.JSONB(astext_type=sa.Text())
CITEXT = postgresql.CITEXT()
ITEM_KEY = ("watchlist_id", "kind", "corpus", "act_key", "location")


def col(name: str, type_: sa.types.TypeEngine[Any], *, null: bool = False) -> sa.Column[Any]:
    return sa.Column(name, type_, nullable=null)


def cols(type_: sa.types.TypeEngine[Any], *names: str) -> list[sa.Column[Any]]:
    return [col(name, type_) for name in names]


def nulls(type_: sa.types.TypeEngine[Any], *names: str) -> list[sa.Column[Any]]:
    return [col(name, type_, null=True) for name in names]


def identity(table: str) -> tuple[sa.Column[Any], sa.PrimaryKeyConstraint]:
    column = sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False)
    return column, pk(table, "id")


def enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name].split(), name=name, schema="app", create_type=False)


def counters(*names: str) -> list[sa.Column[Any]]:
    return [
        sa.Column(name, sa.Integer(), server_default=sa.text("0"), nullable=False) for name in names
    ]


def fk(column: str, target: str, name: str, ondelete: str | None) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=name, ondelete=ondelete)


def pk(table: str, *columns: str) -> sa.PrimaryKeyConstraint:
    return sa.PrimaryKeyConstraint(*columns, name=f"pk_{table}")


def uq(table: str, *columns: str, nulls_not_distinct: bool = False) -> sa.UniqueConstraint:
    name = f"uq_{table}_{'_'.join(columns)}"
    if nulls_not_distinct:
        return sa.UniqueConstraint(*columns, name=name, postgresql_nulls_not_distinct=True)
    return sa.UniqueConstraint(*columns, name=name)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for name, values in ENUMS.items():
        postgresql.ENUM(*values.split(), name=name, schema="app").create(op.get_bind())
    _app()
    _content()
    op.create_table(
        "announced",
        col("event_key", TEXT),
        col("first_seen_at", STAMP),
        col("eligible", sa.Boolean()),
        col("reason", TEXT),
        pk("announced", "event_key"),
        schema="notify",
    )


def _app() -> None:
    users = "app.users.id"
    watchlists = "app.watchlists.id"
    op.create_table(
        "users",
        col("id", sa.Uuid()),
        col("email", CITEXT),
        col("status", enum("user_status")),
        *cols(STAMP, "created_at", "verified_at", "last_signin_at", "last_seen_at"),
        col("inactivity_notice_at", STAMP, null=True),
        pk("users", "id"),
        uq("users", "email"),
        schema="app",
    )
    op.create_table(
        "consents",
        *identity("consents"),
        col("user_id", sa.Uuid()),
        col("kind", enum("consent_kind")),
        col("version", TEXT),
        col("granted_at", STAMP),
        col("withdrawn_at", STAMP, null=True),
        fk("user_id", users, "fk_consents_user_id_users", "CASCADE"),
        schema="app",
    )
    op.create_table(
        "login_tokens",
        col("token_hash", sa.LargeBinary()),
        col("email", CITEXT),
        col("purpose", enum("token_purpose")),
        col("intent", JSON, null=True),
        *cols(STAMP, "created_at", "expires_at"),
        col("used_at", STAMP, null=True),
        pk("login_tokens", "token_hash"),
        schema="app",
    )
    op.create_table(
        "sessions",
        col("id_hash", sa.LargeBinary()),
        col("user_id", sa.Uuid()),
        *cols(STAMP, "created_at", "expires_at", "last_used_at"),
        fk("user_id", users, "fk_sessions_user_id_users", "CASCADE"),
        pk("sessions", "id_hash"),
        schema="app",
    )
    op.create_table(
        "watchlists",
        *cols(sa.Uuid(), "id", "user_id"),
        col("name", TEXT),
        col("cadence", enum("cadence")),
        col("date_alerts", sa.Boolean()),
        sa.Column("heartbeat", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        col("feed_token_hash", sa.LargeBinary(), null=True),
        col("created_at", STAMP),
        fk("user_id", users, "fk_watchlists_user_id_users", "CASCADE"),
        pk("watchlists", "id"),
        uq("watchlists", "feed_token_hash"),
        schema="app",
    )
    op.create_table(
        "watch_items",
        *cols(sa.Uuid(), "id", "watchlist_id"),
        col("kind", enum("item_kind")),
        *cols(TEXT, "corpus", "act_key"),
        col("location", TEXT, null=True),
        col("created_at", STAMP),
        fk("watchlist_id", watchlists, "fk_watch_items_watchlist_id_watchlists", "CASCADE"),
        pk("watch_items", "id"),
        uq("watch_items", *ITEM_KEY, nulls_not_distinct=True),
        schema="app",
    )
    op.create_table(
        "outbox",
        col("id", sa.Uuid()),
        col("user_id", sa.Uuid(), null=True),
        col("purpose", enum("outbox_purpose")),
        *cols(TEXT, "to_email", "subject", "text_body", "html_body"),
        col("headers", JSON),
        col("status", enum("outbox_status")),
        *counters("attempts"),
        col("next_attempt_at", STAMP),
        *nulls(TEXT, "last_error", "provider_message_id"),
        col("created_at", STAMP),
        col("sent_at", STAMP, null=True),
        fk("user_id", users, "fk_outbox_user_id_users", "CASCADE"),
        pk("outbox", "id"),
        schema="app",
    )
    op.create_table(
        "deliveries",
        *cols(sa.Uuid(), "id", "watchlist_id"),
        col("kind", enum("delivery_kind")),
        col("period_key", TEXT),
        col("outbox_id", sa.Uuid(), null=True),
        col("created_at", STAMP),
        fk("outbox_id", "app.outbox.id", "fk_deliveries_outbox_id_outbox", "SET NULL"),
        fk("watchlist_id", watchlists, "fk_deliveries_watchlist_id_watchlists", "CASCADE"),
        pk("deliveries", "id"),
        uq("deliveries", "watchlist_id", "kind", "period_key"),
        schema="app",
    )
    op.create_table(
        "matches",
        col("watchlist_id", sa.Uuid()),
        *cols(TEXT, "event_key", "location"),
        col("occurrence", sa.Integer()),
        col("date_alert", sa.Boolean()),
        col("matched_at", STAMP),
        col("delivery_id", sa.Uuid(), null=True),
        fk("delivery_id", "app.deliveries.id", "fk_matches_delivery_id_deliveries", None),
        fk("watchlist_id", watchlists, "fk_matches_watchlist_id_watchlists", "CASCADE"),
        pk("matches", "watchlist_id", "event_key", "location", "occurrence"),
        schema="app",
    )
    op.create_table(
        "suppressions",
        col("email_sha256", sa.LargeBinary()),
        col("reason", enum("suppression_reason")),
        col("created_at", STAMP),
        pk("suppressions", "email_sha256"),
        schema="app",
    )
    op.create_table(
        "mail_events",
        *identity("mail_events"),
        col("email_sha256", sa.LargeBinary()),
        col("kind", enum("mail_event_kind")),
        col("provider_message_id", TEXT, null=True),
        col("at", STAMP),
        schema="app",
    )
    op.create_table(
        "audit_log",
        *identity("audit_log"),
        col("user_id", sa.Uuid()),
        col("action", enum("audit_action")),
        col("at", STAMP),
        schema="app",
    )
    ix = op.create_index
    where = sa.text("delivery_id IS NULL")
    ix("ix_login_tokens_email_created_at", "login_tokens", ["email", "created_at"], schema="app")
    ix("ix_sessions_user_id", "sessions", ["user_id"], schema="app")
    ix("ix_outbox_status_next_attempt_at", "outbox", ["status", "next_attempt_at"], schema="app")
    ix("ix_matches_delivery_id", "matches", ["delivery_id"], schema="app", postgresql_where=where)
    ix("ix_mail_events_email_sha256_at", "mail_events", ["email_sha256", "at"], schema="app")


def _content() -> None:
    op.create_table(
        "acts",
        *cols(TEXT, "corpus", "act_key", "label", "long_name", "domain"),
        col("aliases", sa.ARRAY(sa.Text())),
        col("url", TEXT),
        col("feed", TEXT, null=True),
        col("title", TEXT),
        col("index_sha256", TEXT, null=True),
        col("checked_through", sa.Date(), null=True),
        col("waiting", JSON),
        pk("acts", "corpus", "act_key"),
        schema="content",
    )
    op.create_table(
        "events",
        *cols(TEXT, "event_key", "corpus", "act_key", "entry_key", "from_version", "to_version"),
        col("detected_on", sa.Date()),
        col("in_force", sa.ARRAY(sa.Date())),
        col("updated_on", sa.Date()),
        *cols(TEXT, "path", "sha256"),
        col("url", TEXT, null=True),
        pk("events", "event_key"),
        schema="content",
    )
    op.create_table(
        "changes",
        *cols(TEXT, "event_key", "location"),
        col("occurrence", sa.Integer()),
        *cols(TEXT, "unit", "change_type"),
        *nulls(TEXT, "heading", "previous_location"),
        col("disputed", sa.Boolean()),
        col("dispute_reason", TEXT, null=True),
        col("signals", JSON),
        col("in_force", sa.Date(), null=True),
        col("applies_from", TEXT),
        *cols(sa.ARRAY(sa.Date()), "dates_added", "dates_removed"),
        *cols(sa.ARRAY(sa.Text()), "amending_acts", "changed_within"),
        *cols(TEXT, "outcome", "unexplained_kind", "unexplained"),
        col("sentences", JSON),
        col("anchor", TEXT),
        fk("event_key", "content.events.event_key", "fk_changes_event_key_events", "CASCADE"),
        pk("changes", "event_key", "location", "occurrence"),
        schema="content",
    )
    op.create_table(
        "provisions",
        *cols(TEXT, "corpus", "act_key", "unit"),
        col("heading", TEXT, null=True),
        col("newest_version", TEXT),
        col("changes", sa.Integer()),
        pk("provisions", "corpus", "act_key", "unit"),
        schema="content",
    )
    op.create_table(
        "loads",
        *identity("loads"),
        col("root_sha256", TEXT),
        col("started_at", STAMP),
        col("finished_at", STAMP, null=True),
        *counters("events_upserted", "events_removed", "events_skipped"),
        schema="content",
    )
    op.create_index("ix_events_corpus_act_key", "events", ["corpus", "act_key"], schema="content")
    op.create_index("ix_changes_unit", "changes", ["unit"], schema="content")


def downgrade() -> None:
    raise NotImplementedError("forward only")
