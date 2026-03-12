import datetime
import uuid

from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(20), default="individual")  # individual / segment
    segment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    connection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    apify_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    apify_dataset_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/succeeded/failed
    total_profiles: Mapped[int] = mapped_column(Integer, default=0)
    profiles_done: Mapped[int] = mapped_column(Integer, default=0)
    posts_scraped: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
