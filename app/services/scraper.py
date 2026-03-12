import asyncio
import datetime
import logging

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.connection import Connection
from app.models.scrape_job import ScrapeJob
from app.models.scraped_post import ScrapedPost
from app.services.apify import apify_service

logger = logging.getLogger(__name__)

# In-memory job progress for SSE streaming
_job_events: dict[str, list[dict]] = {}


def push_event(job_id: str, event: dict):
    _job_events.setdefault(job_id, []).append(event)


def get_events(job_id: str, after: int = 0) -> list[dict]:
    events = _job_events.get(job_id, [])
    return events[after:]


def parse_posted_date(date_str: str | None) -> datetime.datetime | None:
    if not date_str:
        return None
    try:
        return datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def parse_post_item(item: dict, connection_id: int) -> dict:
    """Parse an Apify result item into a scraped_posts row dict."""
    reactions = item.get("reactionsByType", {}) or {}
    return {
        "connection_id": connection_id,
        "post_url": item.get("postUrl", "") or item.get("url", "") or f"unknown-{item.get('id', '')}",
        "post_text": item.get("text", ""),
        "posted_at": parse_posted_date(item.get("postedAt")),
        "reactions_total": item.get("totalReactionCount", 0) or 0,
        "reactions_like": reactions.get("like", 0) or 0,
        "reactions_celebrate": reactions.get("praise", 0) or reactions.get("celebrate", 0) or 0,
        "reactions_support": reactions.get("empathy", 0) or reactions.get("support", 0) or 0,
        "reactions_love": reactions.get("love", 0) or 0,
        "reactions_insightful": reactions.get("interest", 0) or reactions.get("insightful", 0) or 0,
        "reactions_funny": reactions.get("entertainment", 0) or reactions.get("funny", 0) or 0,
        "comments_count": item.get("commentsCount", 0) or 0,
        "reposts_count": item.get("repostsCount", 0) or item.get("sharesCount", 0) or 0,
        "media_type": item.get("mediaType"),
        "media_url": (item.get("images") or [None])[0] if isinstance(item.get("images"), list) else item.get("imageUrl"),
        "is_reshare": bool(item.get("resharedPost")),
        "reshared_author": (item.get("resharedPost") or {}).get("authorName"),
        "reshared_text": (item.get("resharedPost") or {}).get("text"),
        "raw_json": item,
    }


async def run_scrape_individual(job_id: str, connection_id: int):
    """Background task: scrape posts for a single connection."""
    async with async_session() as db:
        try:
            # Get connection
            conn = await db.get(Connection, connection_id)
            if not conn:
                await _fail_job(db, job_id, "Connection not found")
                return

            push_event(job_id, {"type": "started", "message": f"Starting scrape for {conn.name}"})

            # Start Apify run
            run_data = await apify_service.start_run([conn.linkedin_url], posts_limit=10)
            run_id = run_data["id"]

            await db.execute(
                update(ScrapeJob)
                .where(ScrapeJob.id == job_id)
                .values(apify_run_id=run_id, status="running", total_profiles=1)
            )
            await db.commit()

            push_event(job_id, {"type": "progress", "message": "Apify run started", "profiles_done": 0, "total": 1})

            # Poll until done
            dataset_id = await _poll_run(db, job_id, run_id)
            if not dataset_id:
                return

            # Fetch and store results
            results = await apify_service.get_results(dataset_id)
            posts_count = await _store_posts(db, results, connection_id)

            # Update connection last_scraped_at
            await db.execute(
                update(Connection)
                .where(Connection.id == connection_id)
                .values(last_scraped_at=datetime.datetime.utcnow())
            )

            # Mark job succeeded
            await db.execute(
                update(ScrapeJob)
                .where(ScrapeJob.id == job_id)
                .values(
                    status="succeeded",
                    profiles_done=1,
                    posts_scraped=posts_count,
                    apify_dataset_id=dataset_id,
                    completed_at=datetime.datetime.utcnow(),
                )
            )
            await db.commit()

            push_event(job_id, {
                "type": "completed",
                "message": f"Scraped {posts_count} posts for {conn.name}",
                "posts_scraped": posts_count,
                "profiles_done": 1,
                "total": 1,
            })

        except Exception as e:
            logger.exception(f"Scrape job {job_id} failed")
            await _fail_job(db, job_id, str(e))


async def run_scrape_segment(job_id: str, segment: str):
    """Background task: scrape posts for all connections in a segment."""
    async with async_session() as db:
        try:
            result = await db.execute(
                select(Connection).where(Connection.segment == segment)
            )
            connections = result.scalars().all()

            if not connections:
                await _fail_job(db, job_id, f"No connections in segment {segment}")
                return

            total = len(connections)
            await db.execute(
                update(ScrapeJob)
                .where(ScrapeJob.id == job_id)
                .values(status="running", total_profiles=total)
            )
            await db.commit()

            push_event(job_id, {"type": "started", "message": f"Scraping {total} profiles in {segment}"})

            # Batch in chunks of 25
            chunk_size = 25
            all_posts = 0
            profiles_done = 0

            for i in range(0, total, chunk_size):
                chunk = connections[i:i + chunk_size]
                urls = [c.linkedin_url for c in chunk]

                run_data = await apify_service.start_run(urls, posts_limit=10)
                run_id = run_data["id"]

                push_event(job_id, {
                    "type": "progress",
                    "message": f"Batch {i // chunk_size + 1}: scraping {len(chunk)} profiles",
                    "profiles_done": profiles_done,
                    "total": total,
                })

                dataset_id = await _poll_run(db, job_id, run_id)
                if not dataset_id:
                    continue

                results = await apify_service.get_results(dataset_id)

                # Map results to connections by matching profile URL
                url_to_conn = {c.linkedin_url: c for c in chunk}
                for item in results:
                    author_url = item.get("authorProfileUrl", "") or item.get("profileUrl", "")
                    matched_conn = None
                    for url, conn in url_to_conn.items():
                        if url.rstrip("/") in author_url or author_url in url:
                            matched_conn = conn
                            break
                    if matched_conn:
                        await _store_posts(db, [item], matched_conn.id)
                        all_posts += 1

                # Update last_scraped_at for chunk
                for c in chunk:
                    await db.execute(
                        update(Connection)
                        .where(Connection.id == c.id)
                        .values(last_scraped_at=datetime.datetime.utcnow())
                    )

                profiles_done += len(chunk)
                await db.execute(
                    update(ScrapeJob)
                    .where(ScrapeJob.id == job_id)
                    .values(profiles_done=profiles_done, posts_scraped=all_posts)
                )
                await db.commit()

                push_event(job_id, {
                    "type": "progress",
                    "message": f"Completed batch: {profiles_done}/{total} profiles",
                    "profiles_done": profiles_done,
                    "total": total,
                    "posts_scraped": all_posts,
                })

            # Mark completed
            await db.execute(
                update(ScrapeJob)
                .where(ScrapeJob.id == job_id)
                .values(
                    status="succeeded",
                    completed_at=datetime.datetime.utcnow(),
                )
            )
            await db.commit()

            push_event(job_id, {
                "type": "completed",
                "message": f"Scraped {all_posts} posts from {profiles_done} profiles in {segment}",
                "posts_scraped": all_posts,
                "profiles_done": profiles_done,
                "total": total,
            })

        except Exception as e:
            logger.exception(f"Segment scrape job {job_id} failed")
            await _fail_job(db, job_id, str(e))


async def _poll_run(db: AsyncSession, job_id: str, run_id: str) -> str | None:
    """Poll Apify run until completion. Returns dataset_id or None on failure."""
    for _ in range(120):  # 10 minutes max
        await asyncio.sleep(5)
        status_data = await apify_service.get_run_status(run_id)
        status = status_data.get("status", "")

        if status == "SUCCEEDED":
            return status_data.get("defaultDatasetId")
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            await _fail_job(db, job_id, f"Apify run {status}: {status_data.get('statusMessage', '')}")
            push_event(job_id, {"type": "error", "message": f"Apify run {status}"})
            return None

        push_event(job_id, {"type": "polling", "message": f"Apify run status: {status}"})

    await _fail_job(db, job_id, "Apify run timed out after 10 minutes")
    return None


async def _store_posts(db: AsyncSession, items: list[dict], connection_id: int) -> int:
    """Upsert parsed post items into scraped_posts. Returns count."""
    if not items:
        return 0

    rows = []
    for item in items:
        parsed = parse_post_item(item, connection_id)
        if parsed["post_url"] and parsed["post_url"] != "":
            rows.append(parsed)

    if not rows:
        return 0

    stmt = insert(ScrapedPost).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["post_url"],
        set_={
            "post_text": stmt.excluded.post_text,
            "reactions_total": stmt.excluded.reactions_total,
            "reactions_like": stmt.excluded.reactions_like,
            "reactions_celebrate": stmt.excluded.reactions_celebrate,
            "reactions_support": stmt.excluded.reactions_support,
            "reactions_love": stmt.excluded.reactions_love,
            "reactions_insightful": stmt.excluded.reactions_insightful,
            "reactions_funny": stmt.excluded.reactions_funny,
            "comments_count": stmt.excluded.comments_count,
            "reposts_count": stmt.excluded.reposts_count,
            "raw_json": stmt.excluded.raw_json,
        },
    )
    await db.execute(stmt)
    await db.commit()
    return len(rows)


async def _fail_job(db: AsyncSession, job_id: str, error: str):
    await db.execute(
        update(ScrapeJob)
        .where(ScrapeJob.id == job_id)
        .values(status="failed", error_message=error, completed_at=datetime.datetime.utcnow())
    )
    await db.commit()
    push_event(job_id, {"type": "error", "message": error})
