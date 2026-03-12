import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.csv_importer import import_csv

router = APIRouter(prefix="/api/seed", tags=["seed"])

DEFAULT_CSV = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "linkedin_connections_full.csv"
)


@router.post("/csv")
async def seed_csv(
    db: AsyncSession = Depends(get_db),
    csv_path: str = Query(DEFAULT_CSV, description="Path to CSV file"),
):
    resolved = os.path.abspath(csv_path)
    if not os.path.isfile(resolved):
        raise HTTPException(400, f"CSV file not found: {resolved}")

    count = await import_csv(db, resolved)
    return {"message": f"Imported {count} connections", "count": count}
