"""The film canon (core/canon) and MDBList's extra scores for a film."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import canon, mdb_scores
from db import get_db
from dependencies import get_current_user
from models.base import MediaType
from models.events import WatchEvent
from models.media import Media
from models.users import User, UserSettings
from routers.media import get_user_tmdb_key

router = APIRouter()


async def mdblist_key(db: AsyncSession, user_id: int) -> str | None:
    """The user's MDBList key, else anyone's on this server (the lists and
    scores are the same for everybody)."""
    own = (await db.execute(select(UserSettings.mdblist_api_key).where(UserSettings.user_id == user_id))).scalar_one_or_none()
    if own:
        return own
    return (await db.execute(
        select(UserSettings.mdblist_api_key).where(UserSettings.mdblist_api_key.isnot(None)).limit(1)
    )).scalar_one_or_none()


async def _watched(db: AsyncSession, user_id: int) -> set[int]:
    return set((await db.execute(
        select(Media.tmdb_id).join(WatchEvent, WatchEvent.media_id == Media.id)
        .where(WatchEvent.user_id == user_id, Media.media_type == MediaType.movie, WatchEvent.watched_at.isnot(None))
    )).scalars().all())


async def _load(db: AsyncSession, user: User, wait: bool = False) -> None:
    await canon.ensure_loaded(await mdblist_key(db, user.id), await get_user_tmdb_key(db, user.id), wait=wait)


@router.get("")
async def canon_lists(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Each list with how many of its films you've seen."""
    await _load(db, current_user, wait=True)
    watched = await _watched(db, current_user.id)
    out = []
    for c in canon.LISTS:
        items = canon.items(c["slug"])
        out.append({
            "slug": c["slug"], "name": c["name"], "blurb": c["blurb"],
            "total": len(items), "seen": sum(1 for i in items if i["tmdb_id"] in watched),
            "posters": [i.get("poster_path") for i in items[:4] if i.get("poster_path")],
        })
    return out


@router.get("/film/{tmdb_id}")
async def film_canon(tmdb_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The canon lists a film is on, for its page."""
    await _load(db, current_user)
    return canon.badges(tmdb_id)


@router.get("/scores/{tmdb_id}")
async def film_scores(tmdb_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Rotten Tomatoes, Metacritic, Letterboxd and Roger Ebert, when MDBList has them."""
    key = await mdblist_key(db, current_user.id)
    if not key:
        return {"scores": {}}
    return await mdb_scores.film_scores(tmdb_id, key) or {"scores": {}}


@router.get("/{slug}")
async def canon_list(slug: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """One list's films in order, each marked seen or not."""
    c = canon.BY_SLUG.get(slug)
    if not c:
        raise HTTPException(status_code=404, detail="No such list")
    await _load(db, current_user, wait=True)
    watched = await _watched(db, current_user.id)
    items = [{**i, "watched": i["tmdb_id"] in watched} for i in canon.items(slug)]
    return {
        "slug": slug, "name": c["name"], "blurb": c["blurb"], "ranked": c["ranked"],
        "total": len(items), "seen": sum(1 for i in items if i["watched"]), "items": items,
    }
