from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from urllib.parse import urlparse

app = FastAPI()

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

        if "youtube.com" in hostname or "youtu.be" in hostname:
            return "YouTube"

        if "twitter.com" in hostname or "x.com" in hostname:
            return "X"

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

    if platform == "X":
        return parts[0]

    if platform == "YouTube":
        first_part = parts[0]

        if first_part.startswith("@"):
            return first_part[1:]

        if first_part in ["channel", "user", "c"] and len(parts) > 1:
            return parts[1]

        return first_part

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

    platform = detect_platform(request.url)

    if not platform:
        return {
            "success": False,
            "message": "Invalid or unsupported social media URL"
        }

    identifier = extract_identifier(request.url, platform)

    return {
        "success": True,
        "platform": platform,
        "identifier": identifier,
        "url": request.url
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