"""The watch pages' forms, each read from posted fields into a frozen model or a list of errors.

An error is a sentence the page shows back above the form (`web/_form_errors.html`). A checkbox
is on when it posts `yes` and off when it is absent, which is how a browser sends one.
"""

from __future__ import annotations

from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from starlette.datastructures import FormData

from emendrix_service.auth.logic import normalise_email
from emendrix_service.db.enums import Cadence
from emendrix_service.watch.logic import read_location

__all__ = [
    "LOCATION_FORMS",
    "NAME_LIMIT",
    "Errors",
    "SignUp",
    "WatchlistName",
    "WatchlistSettings",
    "parse_id",
    "parse_location_field",
    "parse_name",
    "parse_pick",
    "parse_settings",
    "parse_signup",
]

NAME_LIMIT: Final = 80
LOCATION_FORMS: Final = (
    "Article 6, Art. 6, Article 6a, Article 6(1), Annex IV, Annex 4, or a canonical form such "
    "as AR 6 PA 1"
)

Errors = tuple[str, ...]

_NAME_ERROR: Final = f"A watchlist's name is 1 to {NAME_LIMIT} characters."
_CADENCE_ERROR: Final = "Choose one of the four email choices."

Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=NAME_LIMIT, pattern=r"^[^\x00-\x1f]*$"
    ),
]


class WatchlistName(BaseModel):
    """A name for a new watchlist."""

    model_config = ConfigDict(frozen=True)

    name: Name = Field(description="The watchlist's name, trimmed.")


class WatchlistSettings(WatchlistName):
    """Everything the settings form of one watchlist sets."""

    cadence: Cadence = Field(description="How often matches are mailed.")
    date_alerts: bool = Field(description="Flag changes that add or remove a date.")
    heartbeat: bool = Field(description="Send a monthly note when nothing changed.")
    paused: bool = Field(description="Hold every email.")


class SignUp(BaseModel):
    """An address typed on the watch landing, with the consent given."""

    model_config = ConfigDict(frozen=True)

    email: str = Field(description="The normalised address.")


def _text(form: FormData, field: str) -> str:
    value = form.get(field)
    return value if isinstance(value, str) else ""


def _checked(form: FormData, field: str) -> bool:
    return _text(form, field) == "yes"


def _errors(error: ValidationError) -> Errors:
    fields = {str(problem["loc"][0]) for problem in error.errors() if problem["loc"]}
    found = []
    if "name" in fields:
        found.append(_NAME_ERROR)
    if "cadence" in fields:
        found.append(_CADENCE_ERROR)
    return tuple(found) or ("The form could not be read.",)


def parse_name(form: FormData) -> WatchlistName | Errors:
    """The new watchlist's name."""
    try:
        return WatchlistName(name=_text(form, "name"))
    except ValidationError as error:
        return _errors(error)


def parse_settings(form: FormData) -> WatchlistSettings | Errors:
    """One watchlist's settings."""
    try:
        return WatchlistSettings.model_validate(
            {
                "name": _text(form, "name"),
                "cadence": _text(form, "cadence"),
                "date_alerts": _checked(form, "date_alerts"),
                "heartbeat": _checked(form, "heartbeat"),
                "paused": _checked(form, "paused"),
            }
        )
    except ValidationError as error:
        return _errors(error)


def parse_signup(form: FormData) -> SignUp | Errors:
    """The address and the consent tick of the signed-out landing."""
    errors: list[str] = []
    address = normalise_email(_text(form, "email"))
    if address is None:
        errors.append("That is not an email address this service can send to.")
    if not _checked(form, "consent"):
        errors.append("Tick the box to agree to the service's email and its privacy notice.")
    if errors or address is None:
        return tuple(errors)
    return SignUp(email=address)


def parse_id(text: str) -> UUID | None:
    """A watchlist or item id from a path or a field; None when it is not one."""
    try:
        return UUID(text)
    except ValueError:
        return None


def parse_location_field(text: str) -> str | Errors:
    """One typed location in canonical form, or the error that shows it back."""
    canonical = read_location(text)
    if canonical is None:
        shown = " ".join(text.split())[:NAME_LIMIT] or "(nothing)"
        return (f"“{shown}” is not a location this page can read. Type {LOCATION_FORMS}.",)
    return canonical


def parse_pick(form: FormData) -> list[str | None] | Errors:
    """The ticked boxes of the provision picker: None for the whole act, else locations."""
    picked: list[str | None] = [None] if _checked(form, "whole") else []
    for value in form.getlist("location"):
        canonical = read_location(value) if isinstance(value, str) else None
        if canonical is None:
            return ("The form could not be read.",)
        picked.append(canonical)
    if not picked:
        return ("Tick the whole act or at least one provision.",)
    return picked
