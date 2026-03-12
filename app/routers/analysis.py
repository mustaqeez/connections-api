from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.connection import Connection
from app.models.ai_analysis import AIAnalysis
from app.schemas.analysis import AnalysisOut
from app.services.analyzer import analyze_connection

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/connection/{connection_id}", response_model=AnalysisOut)
async def trigger_analysis(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
):
    conn = await db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(404, "Connection not found")

    analysis = await analyze_connection(db, connection_id)
    if not analysis:
        raise HTTPException(400, "No posts found for this connection. Scrape first.")

    return AnalysisOut.model_validate(analysis)


@router.get("/connection/{connection_id}", response_model=AnalysisOut | None)
async def get_analysis(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.connection_id == connection_id)
        .order_by(AIAnalysis.analyzed_at.desc())
        .limit(1)
    )
    analysis = result.scalars().first()
    if not analysis:
        return None
    return AnalysisOut.model_validate(analysis)
