from datetime import datetime

from pydantic import BaseModel


class ConnectionOut(BaseModel):
    id: int
    name: str
    headline: str
    connected_date: str
    linkedin_url: str
    segment: str
    seniority: str
    region: str
    last_scraped_at: datetime | None = None

    model_config = {"from_attributes": True}


class ConnectionDetail(ConnectionOut):
    posts: list["PostOut"] = []
    analyses: list["AnalysisOut"] = []


class ConnectionList(BaseModel):
    items: list[ConnectionOut]
    total: int
    page: int
    page_size: int


class SegmentCount(BaseModel):
    segment: str
    count: int


# Forward refs
from app.schemas.post import PostOut  # noqa: E402
from app.schemas.analysis import AnalysisOut  # noqa: E402

ConnectionDetail.model_rebuild()
