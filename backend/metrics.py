"""Step 2: engagement data provider.

Sample data is clearly labeled and deterministic (same profile URL always
returns the same numbers), so the UI works end-to-end without API keys.
"""

import hashlib
from datetime import datetime, timezone

from pydantic import BaseModel


class MetricsRequest(BaseModel):
    platform: str
    identifier: str


class ProfileMetrics(BaseModel):
    platform: str
    identifier: str
    followers: int
    following: int
    post_count: int
    avg_likes: int
    avg_comments: int
    engagement_rate: float
    source: str  # "sample"
    fetched_at: str


def _seed(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest(), 16)


def sample_metrics(platform: str, identifier: str) -> ProfileMetrics:
    """Deterministic sample metrics, labeled as sample data."""
    seed = _seed(f"{platform}:{identifier.lower()}")
    followers = 1_000 + seed % 490_000
    following = 100 + (seed >> 8) % 4_900
    post_count = 10 + (seed >> 16) % 990
    avg_likes = int(followers * (0.01 + (seed >> 24) % 400 / 10_000))
    avg_comments = int(avg_likes * (0.02 + (seed >> 32) % 80 / 1_000))
    engagement_rate = round((avg_likes + avg_comments) / followers * 100, 2)

    return ProfileMetrics(
        platform=platform,
        identifier=identifier,
        followers=followers,
        following=following,
        post_count=post_count,
        avg_likes=avg_likes,
        avg_comments=avg_comments,
        engagement_rate=engagement_rate,
        source="sample",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def fetch_metrics(platform: str, identifier: str) -> ProfileMetrics:
    return sample_metrics(platform, identifier)
