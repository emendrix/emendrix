"""Pasting CAS and EC numbers into a watchlist: `POST /account/watchlists/{id}/substances`.

Every value of the paste is named on the page that answers it: added, already watched, read
two ways and so added as neither, or not a number and why. The page carries the values that were
not added back into the form, so the reader corrects them there rather than pasting all again.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from emendrix_service.auth.ratelimit import post_limit
from emendrix_service.db import Db
from emendrix_service.db.enums import ItemKind
from emendrix_service.db.watchlists import add_item, watchlists_for
from emendrix_service.notify.matching import substance_label
from emendrix_service.watch.forms import parse_id, parse_identifiers_field
from emendrix_service.watch.pages import copy, not_found
from emendrix_service.web.csrf import csrf_protect
from emendrix_service.web.session import SignedIn, require_user
from emendrix_service.web.templating import render_page

__all__ = ["router"]

router = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])

User = Annotated[SignedIn, Depends(require_user)]


@router.post("/watchlists/{watchlist_id}/substances", dependencies=[Depends(post_limit)])
async def add_numbers(request: Request, user: User, watchlist_id: str) -> Response:
    wanted = parse_id(watchlist_id)
    if wanted is None:
        return not_found(request)
    raw = (await request.form()).get("numbers")
    pasted = parse_identifiers_field(raw if isinstance(raw, str) else "")
    added: list[str] = []
    already: list[str] = []
    db: Db = request.app.state.db
    now = request.app.state.clock.now()
    async with db.transaction() as tx:
        lists = await watchlists_for(tx, user.user_id)
        mine = next((wl for wl in lists if wl.id == wanted), None)
        if mine is None:
            return not_found(request)
        for identifier in () if isinstance(pasted, tuple) else pasted.valid:
            fresh = await add_item(
                tx,
                user.user_id,
                wanted,
                ItemKind.SUBSTANCE,
                None,
                None,
                None,
                now,
                identifier=identifier,
            )
            (added if fresh else already).append(substance_label(identifier))
    errors = pasted if isinstance(pasted, tuple) else ()
    ambiguous = () if isinstance(pasted, tuple) else pasted.ambiguous
    invalid = () if isinstance(pasted, tuple) else pasted.invalid
    heading = f"Add to {mine.name}" if len(lists) > 1 else "Watch CAS and EC numbers"
    return render_page(
        request,
        "watch/numbers_added.html",
        title=heading,
        status=400 if errors else 200,
        heading=heading,
        back=f"/account/?list={mine.id}",
        watchlist=mine,
        errors=errors,
        added=added,
        already=already,
        ambiguous=ambiguous,
        invalid=invalid,
        numbers="\n".join(value for value, _ in (*ambiguous, *invalid)),
        **copy(),
    )
