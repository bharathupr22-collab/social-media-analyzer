from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from urllib.parse import urlparse
from contextlib import asynccontextmanager

from metrics import MetricsRequest, fetch_metrics
from database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables on startup (no-op if they exist)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class URLRequest(BaseModel):
    url: str


def detect_platform(url: str):
    try:
        hostname = urlparse(url).hostname

        if not hostname:
            return None

        hostname = hostname.lower()

        if "instagram.com" in hostname:
            return "Instagram"

        return None

    except Exception:
        return None


def extract_identifier(url: str, platform: str):
    parsed_url = urlparse(url)
    path = parsed_url.path.strip("/")

    if not path:
        return None

    parts = path.split("/")

    if platform == "Instagram":
        return parts[0]

    return None


class EngagementRequest(BaseModel):
    followers: int
    likes: int
    comments: int
    shares: int


@app.get("/")
def home():
    return {
        "message": "Social Media Engagement Analyzer API is running"
    }


@app.get("/health")
def health():
    return {"status": "OK"}


@app.post("/analyze")
def analyze_url(request: URLRequest):

    url = request.url.strip()

    # Tolerate URLs pasted without a scheme, e.g. "instagram.com/username"
    if "://" not in url:
        url = "https://" + url

    platform = detect_platform(url)

    if not platform:
        return {
            "success": False,
            "message": "Invalid or unsupported social media URL"
        }

    identifier = extract_identifier(url, platform)

    if not identifier:
        return {
            "success": False,
            "message": "Could not find a profile identifier in the URL"
        }

    return {
        "success": True,
        "platform": platform,
        "identifier": identifier,
        "url": url
    }


@app.post("/metrics")
def get_metrics(request: MetricsRequest):
    if request.platform != "Instagram":
        return {
            "success": False,
            "message": "Unsupported platform",
        }

    if not request.identifier.strip():
        return {
            "success": False,
            "message": "Profile identifier is required",
        }

    metrics = fetch_metrics(request.platform, request.identifier.strip())

    return {
        "success": True,
        "metrics": metrics.model_dump(),
    }


@app.post("/calculate-engagement")
def calculate_engagement(data: EngagementRequest):

    if data.followers <= 0:
        return {
            "success": False,
            "message": "Followers must be greater than 0"
        }

    total_engagement = data.likes + data.comments + data.shares

    engagement_rate = (
        total_engagement / data.followers
    ) * 100

    return {
        "success": True,
        "followers": data.followers,
        "likes": data.likes,
        "comments": data.comments,
        "shares": data.shares,
        "total_engagement": total_engagement,
        "engagement_rate": round(engagement_rate, 2)
    }
