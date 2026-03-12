import datetime

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(Integer, ForeignKey("connections.id"))
    interests: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pain_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    frustrations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    topics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posting_frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    engagement_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_starters: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    posts_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    analyzed_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    connection = relationship("Connection", back_populates="analyses")
