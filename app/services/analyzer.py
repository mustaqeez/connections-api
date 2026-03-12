import json
import logging

from openai import AsyncOpenAI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.connection import Connection
from app.models.scraped_post import ScrapedPost
from app.models.ai_analysis import AIAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert at analyzing LinkedIn professional profiles based on their posts.
Given a collection of LinkedIn posts from one person, extract structured insights.

Return ONLY valid JSON with this exact structure:
{
  "interests": ["list of professional interests and passions"],
  "pain_points": ["list of challenges or problems they discuss"],
  "frustrations": ["list of things that frustrate them professionally"],
  "topics": ["main topics they post about"],
  "tone": "their overall writing tone (e.g., 'Professional & Thought Leadership', 'Casual & Conversational')",
  "posting_frequency": "estimate (e.g., 'Daily', '2-3 times per week', 'Weekly')",
  "engagement_level": "how much engagement they get (e.g., 'High', 'Medium', 'Low')",
  "summary": "A 2-3 sentence professional summary of this person based on their posts",
  "conversation_starters": ["3-5 personalized conversation starters you could use to connect with this person"]
}"""


async def analyze_connection(db: AsyncSession, connection_id: int) -> AIAnalysis | None:
    """Analyze a connection's scraped posts using OpenAI and store results."""
    conn = await db.get(Connection, connection_id)
    if not conn:
        return None

    # Fetch posts
    result = await db.execute(
        select(ScrapedPost)
        .where(ScrapedPost.connection_id == connection_id)
        .order_by(ScrapedPost.posted_at.desc())
        .limit(20)
    )
    posts = result.scalars().all()

    if not posts:
        return None

    # Build the analysis prompt
    posts_text = []
    for p in posts:
        entry = f"Post ({p.posted_at or 'unknown date'}):"
        if p.post_text:
            entry += f"\n{p.post_text[:1000]}"
        entry += f"\nReactions: {p.reactions_total} | Comments: {p.comments_count} | Reposts: {p.reposts_count}"
        if p.is_reshare:
            entry += f"\n[Reshared from {p.reshared_author or 'unknown'}]"
        posts_text.append(entry)

    user_prompt = f"""Analyze these LinkedIn posts from {conn.name} ({conn.headline}):

---
{"---".join(posts_text)}
---

Provide your analysis as JSON."""

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    model = "gpt-4o"

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2000,
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # Upsert analysis
        existing = await db.execute(
            select(AIAnalysis).where(AIAnalysis.connection_id == connection_id)
        )
        analysis = existing.scalars().first()

        if analysis:
            analysis.interests = data.get("interests", [])
            analysis.pain_points = data.get("pain_points", [])
            analysis.frustrations = data.get("frustrations", [])
            analysis.topics = data.get("topics", [])
            analysis.tone = data.get("tone")
            analysis.posting_frequency = data.get("posting_frequency")
            analysis.engagement_level = data.get("engagement_level")
            analysis.summary = data.get("summary")
            analysis.conversation_starters = data.get("conversation_starters", [])
            analysis.model_used = model
            analysis.posts_analyzed = len(posts)
        else:
            analysis = AIAnalysis(
                connection_id=connection_id,
                interests=data.get("interests", []),
                pain_points=data.get("pain_points", []),
                frustrations=data.get("frustrations", []),
                topics=data.get("topics", []),
                tone=data.get("tone"),
                posting_frequency=data.get("posting_frequency"),
                engagement_level=data.get("engagement_level"),
                summary=data.get("summary"),
                conversation_starters=data.get("conversation_starters", []),
                model_used=model,
                posts_analyzed=len(posts),
            )
            db.add(analysis)

        await db.commit()
        await db.refresh(analysis)
        return analysis

    except Exception as e:
        logger.exception(f"AI analysis failed for connection {connection_id}")
        raise
