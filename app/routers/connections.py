from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.connection import Connection
from app.models.scraped_post import ScrapedPost
from app.models.ai_analysis import AIAnalysis
from app.schemas.connection import ConnectionOut, ConnectionDetail, ConnectionList, SegmentCount
from app.schemas.post import PostOut, PostList

router = APIRouter(prefix="/api/connections", tags=["connections"])


@router.get("", response_model=ConnectionList)
async def list_connections(
    db: AsyncSession = Depends(get_db),
    search: str = Query("", description="Search name or headline"),
    segment: str = Query("", description="Filter by segment"),
    seniority: str = Query("", description="Filter by seniority"),
    sort: str = Query("id", description="Sort column"),
    order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    query = select(Connection)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            Connection.name.ilike(pattern) | Connection.headline.ilike(pattern)
        )
    if segment:
        query = query.where(Connection.segment == segment)
    if seniority:
        query = query.where(Connection.seniority == seniority)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    sort_col = getattr(Connection, sort, Connection.id)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return ConnectionList(
        items=[ConnectionOut.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/segments", response_model=list[SegmentCount])
async def get_segments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Connection.segment, func.count(Connection.id).label("count"))
        .group_by(Connection.segment)
        .order_by(func.count(Connection.id).desc())
    )
    return [SegmentCount(segment=row[0], count=row[1]) for row in result.all()]


@router.get("/{connection_id}", response_model=ConnectionDetail)
async def get_connection(connection_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Connection)
        .options(selectinload(Connection.posts), selectinload(Connection.analyses))
        .where(Connection.id == connection_id)
    )
    conn = result.scalars().first()
    if not conn:
        from fastapi import HTTPException
        raise HTTPException(404, "Connection not found")
    return ConnectionDetail.model_validate(conn)


@router.get("/{connection_id}/posts", response_model=PostList)
async def get_connection_posts(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    count_q = select(func.count()).where(ScrapedPost.connection_id == connection_id)
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        select(ScrapedPost)
        .where(ScrapedPost.connection_id == connection_id)
        .order_by(ScrapedPost.posted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = result.scalars().all()

    return PostList(
        items=[PostOut.model_validate(p) for p in posts],
        total=total,
        page=page,
        page_size=page_size,
    )
