import csv
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.connection import Connection


def classify_segment(headline: str) -> str:
    h = headline.lower()
    if any(kw in h for kw in [
        "general manager", "gm ", "hotel manager", "cluster general",
        "group general manager", "area general manager", "dual general",
    ]):
        return "Hotel GM"
    if any(kw in h for kw in [
        "ceo", "chief executive", "president", "owner", "founder",
        "managing director", "coo", "chief operating",
        "executive director", "executive vice president",
    ]):
        return "Hospitality C-Suite"
    if any(kw in h for kw in [
        "consultant", "advisor", "advisory", "consulting",
        "hvs", "strategist", "valuation", "coach",
    ]):
        return "Consultant/Advisor"
    if any(kw in h for kw in [
        "revenue", "sales", "commercial", "business development",
        "booking", "reservations", "distribution",
    ]):
        return "Revenue/Sales"
    if any(kw in h for kw in [
        "marketing", "brand", "digital", "content", "social media", "pr ",
    ]):
        return "Marketing"
    if any(kw in h for kw in [
        "f&b", "food", "beverage", "restaurant", "culinary", "chef", "catering",
    ]):
        return "F&B"
    if any(kw in h for kw in [
        "tech", "software", "developer", "engineer", "it ",
        "data", "ai ", "saas", "aws", "cloud",
    ]):
        return "Tech/IT"
    if any(kw in h for kw in [
        "cfo", "finance", "financial", "accounting", "investment",
        "asset management", "private equity", "fintech",
    ]):
        return "Finance"
    if any(kw in h for kw in [
        "real estate", "property", "asset", "reit", "development",
    ]):
        return "Real Estate"
    return "Other"


def classify_seniority(headline: str) -> str:
    h = headline.lower()
    if any(kw in h for kw in [
        "ceo", "coo", "cfo", "president", "chief", "founder",
        "owner", "managing director", "partner",
    ]):
        return "C-Suite"
    if any(kw in h for kw in [
        "general manager", "director", "vice president", "vp ",
        "head of", "executive director", "area manager", "cluster",
    ]):
        return "VP/Director"
    if any(kw in h for kw in ["manager", "lead", "supervisor"]):
        return "Manager"
    if any(kw in h for kw in [
        "associate", "analyst", "agent", "coordinator", "assistant",
    ]):
        return "Associate"
    return "Other"


def infer_region(headline: str, name: str) -> str:
    h = (headline + " " + name).lower()
    checks = [
        ("Middle East", ["dubai", "uae", "abu dhabi", "middle east", "mea", "riyadh", "saudi", "doha", "qatar", "kuwait", "oman", "bahrain", "muscat", "jeddah"]),
        ("India", ["india", "mumbai", "delhi", "bangalore", "chennai", "hyderabad"]),
        ("Pakistan", ["pakistan", "lahore", "karachi"]),
        ("Africa", ["africa", "nigeria", "kenya", "zambia", "south africa", "ghana", "egypt", "cairo"]),
        ("UK", ["uk", "london", "britain", "england", "wales", "scotland"]),
        ("Europe", ["europe", "italy", "france", "germany", "spain", "swiss", "austria", "cortina"]),
        ("USA", ["usa", "new york", "chicago", "miami", "los angeles", "united states", "american"]),
        ("Asia", ["asia", "singapore", "hong kong", "thailand", "vietnam", "china", "japan", "sri lanka", "indonesia", "tashkent"]),
        ("Central Asia", ["azerbaijan", "baku", "uzbekistan", "kazakhstan"]),
        ("Caribbean", ["caribbean", "jamaica", "barbados", "bahamas"]),
        ("Oceania", ["australia", "new zealand"]),
        ("Canada", ["canada", "toronto", "vancouver"]),
        ("Latin America", ["latin", "mexico", "colombia", "brazil", "chile", "argentina"]),
    ]
    for region, keywords in checks:
        if any(kw in h for kw in keywords):
            return region
    return "Global"


async def import_csv(db: AsyncSession, csv_path: str) -> int:
    """Import LinkedIn connections CSV into database. Returns count of upserted rows."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header
        for row in reader:
            if len(row) < 5:
                continue
            _no, name, headline, connected_date, linkedin_url = (
                row[0].strip(),
                row[1].strip(),
                row[2].strip(),
                row[3].strip(),
                row[4].strip(),
            )
            if not name or not linkedin_url:
                continue
            # Clean emoji from name
            name = re.sub(r"[^\w\s\-'.,()/&|]", "", name).strip()
            rows.append({
                "name": name,
                "headline": headline,
                "connected_date": connected_date,
                "linkedin_url": linkedin_url,
                "segment": classify_segment(headline),
                "seniority": classify_seniority(headline),
                "region": infer_region(headline, name),
            })

    if not rows:
        return 0

    # Upsert - update on conflict with linkedin_url
    stmt = insert(Connection).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["linkedin_url"],
        set_={
            "name": stmt.excluded.name,
            "headline": stmt.excluded.headline,
            "connected_date": stmt.excluded.connected_date,
            "segment": stmt.excluded.segment,
            "seniority": stmt.excluded.seniority,
            "region": stmt.excluded.region,
        },
    )
    await db.execute(stmt)
    await db.commit()
    return len(rows)
