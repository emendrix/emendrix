"""A citation: a pointer from a sentence to a provision in a specific version.

A `Citation` is *data*. It says which provision is being cited, where a reader can click
to see it, and how to print it. Rendering the URL is the adapter's job (only the corpus
knows what resolves, and provision-level ELI does not, verified 2026-08-05), and checking that
a generated sentence only cites provisions it was actually shown is the gate's job.

This module deliberately performs neither.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core.identifiers import ProvisionRef

__all__ = ["Citation"]


class Citation(BaseModel):
    """A resolvable reference to one provision of one version of one act."""

    model_config = ConfigDict(frozen=True)

    ref: ProvisionRef
    url: str = Field(min_length=1, description="Where a reader sees the provision.")
    label: str = Field(min_length=1, description="Display form, e.g. 'Art. 5(1)(bb), v2'.")

    def __str__(self) -> str:
        return f"[{self.label}]({self.url})"
