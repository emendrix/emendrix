"""Everything the service is told about its deployment, read from `EMENDRIX_SERVICE_*` only.

This is the one module that reads the environment. Every setting is declared here, each optional
where a deployment may leave it unset; a command that needs an optional one calls `require`,
which stops with the variable's name. `load_settings` is the only place the environment is read;
tests build `ServiceSettings` from keyword arguments through `model_validate`, which reads
nothing. No `.env` file is read: the process environment is the only source.

No address has a default, because an address written into the code would be one deployment's
served by every other. Keys and passwords are secret types, so no `repr`, log line or error
message prints them.
"""

from __future__ import annotations

import base64
import binascii
from datetime import date
from pathlib import Path
from typing import Annotated, Final
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretBytes, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from emendrix_service.stop import stop

__all__ = ["ENV_PREFIX", "MIN_KEY_BYTES", "ServiceSettings", "load_settings", "require", "variable"]

ENV_PREFIX: Final = "EMENDRIX_SERVICE_"

MIN_KEY_BYTES: Final = 32
"""The shortest secret key accepted: the output length of the HMAC it keys."""

DATABASE_SCHEME: Final = "postgresql+psycopg"
"""The only scheme accepted. A bare `postgresql` would make SQLAlchemy load psycopg2, which the
image does not carry, and the failure would show only at the first query."""

Hosts = Annotated[tuple[str, ...], NoDecode]
"""A comma-separated list in the environment rather than JSON."""


def variable(name: str) -> str:
    """The environment variable behind the setting `name`."""
    return f"{ENV_PREFIX}{name.upper()}"


class ServiceSettings(BaseSettings):
    """One deployment's configuration, checked before anything is read, bound or sent."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX, extra="ignore", frozen=True, env_ignore_empty=True
    )

    database_url: SecretStr = Field(
        description="The database, as `postgresql+psycopg://user:password@host:5432/name`."
    )
    site_url: str = Field(
        description="The public base every emailed link is built on: https, no trailing slash."
    )
    allowed_hosts: Hosts = Field(
        min_length=1, description="The `Host` values the web process answers, lower-cased."
    )
    secret_key: SecretBytes = Field(
        description="The root of every HMAC, given as base64 of at least 32 bytes."
    )
    changelogs: Path | None = Field(
        default=None, description="The changelogs repository's directory, read-only."
    )
    catalogue: Path | None = Field(
        default=None, description="A built site's `api/v1/catalogue.json`."
    )
    shell: Path | None = Field(
        default=None, description="A built site's `account-shell.html`, which every page fills."
    )
    privacy_notice: Path | None = Field(
        default=None,
        description="The operator's privacy notice as an HTML fragment; without it sign-up "
        "refuses.",
    )
    signup_open: bool = Field(
        default=True, description="Whether a new address may sign up; sign-in works either way."
    )
    signup_allowlist: Hosts = Field(
        default=(),
        description="Addresses that may sign up while sign-up is closed, lower-cased.",
    )
    live_since: date | None = Field(
        default=None, description="Events detected before this date are never announced."
    )
    smtp_host: str | None = Field(default=None, description="The SMTP relay's host name.")
    smtp_port: int = Field(default=587, ge=1, le=65535, description="The SMTP relay's port.")
    smtp_username: str | None = Field(default=None, description="The SMTP login, if any.")
    smtp_password: SecretStr | None = Field(default=None, description="The SMTP password.")
    smtp_starttls: bool = Field(default=True, description="Whether to upgrade with STARTTLS.")
    mail_from: str | None = Field(
        default=None, description="The `From` of every email, as `Name <address>`."
    )
    operator_email: str | None = Field(
        default=None, description="Where the daily status email goes; unset sends none."
    )
    webhook_secret: SecretStr | None = Field(
        default=None,
        description="The path secret of the mail provider's webhook; unset answers 404.",
    )
    client_ip_header: str | None = Field(
        default=None,
        description="A request header naming the client address, trusted as-is because only "
        "the proxy reaches the service; unset uses the peer address.",
    )
    timezone: str = Field(
        default="Europe/Brussels", description="The IANA zone digests fall due in."
    )
    digest_hour: int = Field(
        default=7, ge=0, le=23, description="The local hour a daily or weekly digest falls due."
    )
    backup_target: str | None = Field(
        default=None, description="Where `backup ship` uploads, as `user@host:directory`."
    )
    backup_ssh_key: Path | None = Field(
        default=None, description="The private key `backup ship` logs in with."
    )
    backup_known_hosts: Path | None = Field(
        default=None, description="The known-hosts file that pins the backup host's key."
    )
    backup_age_recipient: str | None = Field(
        default=None, description="The `age` public key every backup is encrypted to."
    )
    bind: str = Field(default="0.0.0.0", description="The address the web process listens on.")
    port: int = Field(default=8000, ge=1, le=65535, description="The port it listens on.")

    @field_validator("allowed_hosts", "signup_allowlist", mode="before")
    @classmethod
    def _split_lists(cls, value: object) -> object:
        parts = value.split(",") if isinstance(value, str) else value
        if isinstance(parts, list | tuple):
            return tuple(str(part).strip().lower() for part in parts if str(part).strip())
        return value

    @field_validator("database_url")
    @classmethod
    def _database_scheme(cls, value: SecretStr) -> SecretStr:
        if urlsplit(value.get_secret_value()).scheme != DATABASE_SCHEME:
            raise ValueError(f"the scheme must be {DATABASE_SCHEME}")
        return value

    @field_validator("site_url")
    @classmethod
    def _site_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("must be an absolute address with the https scheme")
        if value.endswith("/") or parts.query or parts.fragment:
            raise ValueError("must end in the host or a path, with no trailing slash")
        return value

    @field_validator("secret_key", mode="before")
    @classmethod
    def _decode_key(cls, value: object) -> bytes:
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if not isinstance(value, str):
            raise ValueError("must be given as base64 text")
        text = "".join(value.split()).replace("-", "+").replace("_", "/")
        try:
            key = base64.b64decode(text + "=" * (-len(text) % 4), validate=True)
        except binascii.Error:
            raise ValueError("is not base64") from None
        if len(key) < MIN_KEY_BYTES:
            raise ValueError(f"must decode to at least {MIN_KEY_BYTES} bytes")
        return key

    @field_validator("port", "smtp_port", mode="before")
    @classmethod
    def _port(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().isdigit():
            raise ValueError(
                f"must be a port number, not {value!r}; a value like 'tcp://10.0.0.1:8000' is "
                "the link a Kubernetes Service named emendrix-service injects, which "
                "`enableServiceLinks: false` on the pod turns off"
            )
        return value

    @field_validator("timezone")
    @classmethod
    def _zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"{value!r} is not an IANA time zone") from None
        return value

    def zone(self) -> ZoneInfo:
        """The zone digests fall due in."""
        return ZoneInfo(self.timezone)


def require(settings: ServiceSettings, *names: str) -> None:
    """Stop with exit code 2, naming the variable, unless every setting in `names` is set."""
    for name in names:
        if name not in ServiceSettings.model_fields:
            raise ValueError(f"{name!r} is not a setting")
        if getattr(settings, name) in (None, ()):
            stop(f"{variable(name)} is not set")


def load_settings() -> ServiceSettings:
    """The settings the process environment gives, or a stop naming what is missing or wrong."""
    try:
        # Every value comes from the environment, which the type checker cannot see.
        return ServiceSettings()  # type: ignore[call-arg]
    except ValidationError as error:
        problem = error.errors(include_input=False)[0]
        name = variable(str(problem["loc"][0]))
        if problem["type"] == "missing":
            stop(f"{name} is not set")
        stop(f"{name} is not valid: {problem['msg']}")
