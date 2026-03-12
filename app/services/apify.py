import httpx

from app.config import settings

ACTOR_ID = "LQQIXN9Othf8f7R5n"
BASE_URL = "https://api.apify.com/v2"


class ApifyService:
    def __init__(self):
        self.token = settings.APIFY_TOKEN

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    async def start_run(self, profile_urls: list[str], posts_limit: int = 10) -> dict:
        """Start an Apify actor run for LinkedIn profile posts."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE_URL}/acts/{ACTOR_ID}/runs",
                headers=self._headers(),
                json={
                    "profileUrls": profile_urls,
                    "resultsLimit": posts_limit,
                },
            )
            resp.raise_for_status()
            return resp.json()["data"]

    async def get_run_status(self, run_id: str) -> dict:
        """Poll an Apify run for its current status."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/actor-runs/{run_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()["data"]

    async def get_results(self, dataset_id: str) -> list[dict]:
        """Fetch results from a completed Apify dataset."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{BASE_URL}/datasets/{dataset_id}/items",
                headers=self._headers(),
                params={"format": "json"},
            )
            resp.raise_for_status()
            return resp.json()


apify_service = ApifyService()
