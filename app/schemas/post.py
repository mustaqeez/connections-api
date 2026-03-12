from datetime import datetime

from pydantic import BaseModel


class PostOut(BaseModel):
    id: int
    connection_id: int
    post_url: str
    post_text: str | None = None
    posted_at: datetime | None = None
    reactions_total: int = 0
    reactions_like: int = 0
    reactions_celebrate: int = 0
    reactions_support: int = 0
    reactions_love: int = 0
    reactions_insightful: int = 0
    reactions_funny: int = 0
    comments_count: int = 0
    reposts_count: int = 0
    media_type: str | None = None
    media_url: str | None = None
    is_reshare: bool = False
    reshared_author: str | None = None
    reshared_text: str | None = None
    scraped_at: datetime | None = None

    model_config = {"from_attributes": True}


class PostList(BaseModel):
    items: list[PostOut]
    total: int
    page: int
    page_size: int
