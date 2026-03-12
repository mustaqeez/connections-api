import datetime

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    headline: Mapped[str] = mapped_column(String(1000), default="")
    connected_date: Mapped[str] = mapped_column(String(50), default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), unique=True)
    segment: Mapped[str] = mapped_column(String(50), default="Other")
    seniority: Mapped[str] = mapped_column(String(50), default="Other")
    region: Mapped[str] = mapped_column(String(100), default="Global")
    last_scraped_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    posts = relationship("ScrapedPost", back_populates="connection", lazy="selectin")
    analyses = relationship("AIAnalysis", back_populates="connection", lazy="selectin")
