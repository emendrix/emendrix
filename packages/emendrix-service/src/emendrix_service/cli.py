"""`emendrix-service`: the root command, and where every feature's commands are mounted.

Each command lives with its feature (`load/cli.py`, `notify/cli.py`, ...) and is registered
here once, so a feature changes its own module and never this one. Logging is configured before
any command runs. A command that cannot run as configured exits 2 with one line on stderr; a
run that started ends with exactly one marker line (see `log.py`).
"""

from __future__ import annotations

import typer

from emendrix_service import DISCLAIMER
from emendrix_service.app import serve
from emendrix_service.db import cli as db_cli
from emendrix_service.leave import cli as leave_cli
from emendrix_service.load import cli as load_cli
from emendrix_service.log import configure_logging
from emendrix_service.mail import cli as mail_cli
from emendrix_service.notify import cli as notify_cli
from emendrix_service.ops import cli as ops_cli
from emendrix_service.settings import load_settings

__all__ = ["app"]

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="The account service beside emendrix: email watchlists over the published change "
    f"record. Configured only through EMENDRIX_SERVICE_* variables. {DISCLAIMER}",
)


@app.callback()
def _root() -> None:
    configure_logging()


@app.command("serve")
def serve_command() -> None:
    """Run the web process until it is stopped."""
    serve(load_settings())


app.command("migrate")(db_cli.migrate)
app.command("load")(load_cli.load)
app.command("notify")(notify_cli.notify)
app.command("digest")(notify_cli.digest)
app.command("tick")(notify_cli.tick)
app.add_typer(mail_cli.app, name="mail")
app.command("retention")(leave_cli.retention)
app.command("status")(ops_cli.status)
app.add_typer(ops_cli.backup_app, name="backup")
