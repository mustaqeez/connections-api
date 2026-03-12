from datetime import datetime

from pydantic import BaseModel


class ScrapeJobOut(BaseModel):
    id: str
    scope: str
    segment: str | None = None
    connection_id: int | None = None
    apify_run_id: str | None = None
    status: str
    total_profiles: int = 0
    profiles_done: int = 0
    posts_scraped: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScrapeStart(BaseModel):
    job_id: str
    status: str
    message: str
