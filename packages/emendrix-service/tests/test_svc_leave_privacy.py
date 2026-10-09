"""The privacy page: the operator's fragment inside the shell, read again on every request."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from emendrix_service import DISCLAIMER
from emendrix_service.settings import ServiceSettings
from tests.conftest import settings_values

pytestmark = pytest.mark.anyio

FRAGMENT = (
    '<h1>Privacy notice</h1>\n<p>The operator of <a href="/">this site</a> is named here.</p>'
)


@pytest.fixture
def notice(tmp_path: Path) -> Path:
    path = tmp_path / "privacy-notice.html"
    path.write_text(FRAGMENT, encoding="utf-8")
    return path


@pytest.fixture
def settings(shell_file: Path, notice: Path) -> ServiceSettings:
    return ServiceSettings.model_validate(
        {**settings_values(), "shell": shell_file, "privacy_notice": notice}
    )


async def test_svc_leave_the_privacy_page_renders_the_fragment_in_the_shell(
    client: AsyncClient, notice: Path
) -> None:
    page = await client.get("/account/privacy")
    assert page.status_code == 200
    assert FRAGMENT in page.text, "the operator's HTML is inserted as written"
    assert "<title>Privacy notice" in page.text
    assert '<link rel="stylesheet" href="/style.test.css">' in page.text
    assert DISCLAIMER.split("'")[0] in page.text
    notice.write_text("<p>Revised.</p>", encoding="utf-8")
    assert "<p>Revised.</p>" in (await client.get("/account/privacy")).text
    notice.unlink()
    assert (await client.get("/account/privacy")).status_code == 404
