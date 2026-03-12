from datetime import datetime

from pydantic import BaseModel


class AnalysisOut(BaseModel):
    id: int
    connection_id: int
    interests: list[str] | None = None
    pain_points: list[str] | None = None
    frustrations: list[str] | None = None
    topics: list[str] | None = None
    tone: str | None = None
    posting_frequency: str | None = None
    engagement_level: str | None = None
    summary: str | None = None
    conversation_starters: list[str] | None = None
    model_used: str | None = None
    posts_analyzed: int = 0
    analyzed_at: datetime | None = None

    model_config = {"from_attributes": True}
