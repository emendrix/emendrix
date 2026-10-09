"""What an email is before a transport sends it, and what the transport answers.

Both are frozen values: an `OutgoingMail` is exactly what gets written to the outbox and sent,
and a `SendResult` is a first-class answer, never an exception, so a refusal is counted rather
than crashed on. No field may carry a line break where a header is built from it, which closes
header injection at the boundary rather than in each transport.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["OutgoingMail", "SendResult"]


def _one_line(value: str) -> str:
    if "\r" in value or "\n" in value:
        raise ValueError("a header value cannot contain a line break")
    return value


class OutgoingMail(BaseModel):
    """One email to one recipient, with both bodies already rendered."""

    model_config = ConfigDict(frozen=True)

    to: str = Field(description="The one recipient address.")
    subject: str = Field(description="The subject line.")
    text: str = Field(description="The plain-text body.")
    html: str = Field(description="The HTML body.")
    headers: tuple[tuple[str, str], ...] = Field(
        default=(),
        description="Extra headers in order, such as `List-Unsubscribe` and "
        "`List-Unsubscribe-Post`.",
    )

    @field_validator("to", "subject")
    @classmethod
    def _single_line(cls, value: str) -> str:
        return _one_line(value)

    @field_validator("headers")
    @classmethod
    def _single_line_headers(
        cls, value: tuple[tuple[str, str], ...]
    ) -> tuple[tuple[str, str], ...]:
        for name, content in value:
            _one_line(name)
            _one_line(content)
        return value


class SendResult(BaseModel):
    """What a transport made of one send."""

    model_config = ConfigDict(frozen=True)

    accepted: bool = Field(description="Whether the relay accepted the message.")
    provider_message_id: str | None = Field(
        default=None, description="The relay's id for the message, when it gave one."
    )
    permanent: bool = Field(
        default=False,
        description="A refusal that retrying cannot fix (a 5xx at SMTP time): suppress, do not "
        "retry.",
    )
    error: str = Field(
        default="", description="The relay's code and text on a refusal; never the address."
    )
