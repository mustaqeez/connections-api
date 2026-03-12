import datetime

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScrapedPost(Base):
    __tablename__ = "scraped_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(Integer, ForeignKey("connections.id"))
    post_url: Mapped[str] = mapped_column(String(500), unique=True)
    post_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    reactions_total: Mapped[int] = mapped_column(Integer, default=0)
    reactions_like: Mapped[int] = mapped_column(Integer, default=0)
    reactions_celebrate: Mapped[int] = mapped_column(Integer, default=0)
    reactions_support: Mapped[int] = mapped_column(Integer, default=0)
    reactions_love: Mapped[int] = mapped_column(Integer, default=0)
    reactions_insightful: Mapped[int] = mapped_column(Integer, default=0)
    reactions_funny: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    reposts_count: Mapped[int] = mapped_column(Integer, default=0)
    media_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_reshare: Mapped[bool] = mapped_column(default=False)
    reshared_author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reshared_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scraped_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    connection = relationship("Connection", back_populates="posts")
