from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from metrics import MetricsRequest, fetch_metrics
from database import get_db, init_db
from models import ConnectedAccount
from vault import encrypt_token
import instagram_oauth
import media_scan


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


@app.get("/api/instagram/oauth-start")
def instagram_oauth_start():
    """Step 1 of Instagram Login: returns the Meta authorization URL.
    The frontend redirects the admin there; Meta redirects back to
    /api/instagram/oauth-callback with a code."""
    try:
        state = instagram_oauth.new_state()
        url = instagram_oauth.build_authorize_url(state)
    except RuntimeError as exc:
        return {"success": False, "message": str(exc)}
    return {"success": True, "authorize_url": url}


@app.get("/api/instagram/oauth-callback")
def instagram_oauth_callback(code: str = "", state: str = "", db: Session = Depends(get_db)):
    """Step 2 of Instagram Login: Meta redirects here with ?code=...&state=...
    Exchanges the code for a long-lived token and stores it encrypted."""
    if not code:
        return {
            "success": False,
            "message": "Instagram authorization was cancelled or failed (no code returned).",
        }
    if not instagram_oauth.consume_state(state):
        return {
            "success": False,
            "message": "Invalid or expired login session. Please try connecting again.",
        }

    try:
        short = instagram_oauth.exchange_code(code)
        long_lived = instagram_oauth.get_long_lived_token(short["access_token"])
        profile = instagram_oauth.get_profile(long_lived["access_token"])
    except RuntimeError as exc:
        return {"success": False, "message": str(exc)}
    except Exception:
        return {"success": False, "message": "Instagram login failed. Please try again."}

    user_id = str(profile.get("id", ""))
    username = profile.get("username", "")

    try:
        encrypted = encrypt_token(long_lived["access_token"])
    except RuntimeError as exc:
        return {"success": False, "message": str(exc)}

    account = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.platform == "Instagram",
            ConnectedAccount.account_id == user_id,
        )
        .first()
    )
    if account:
        account.username = username
        account.access_token_encrypted = encrypted
    else:
        account = ConnectedAccount(
            platform="Instagram",
            account_id=user_id,
            username=username,
            access_token_encrypted=encrypted,
        )
        db.add(account)
    db.commit()

    return {"success": True, "username": username}


class ScanRequest(BaseModel):
    account_id: int | None = None
    demo: bool = False


@app.post("/api/instagram/scan")
def instagram_scan(req: ScanRequest, db: Session = Depends(get_db)):
    """Scan an account's reels for missing audio.

    demo=True runs a deterministic sample scan with no network access
    (for development and viva demos). demo=False uses the connected
    account's stored token against the live Instagram API.
    """
    if req.demo:
        return {"success": True, **media_scan.scan_demo(db)}

    account = None
    if req.account_id:
        account = (
            db.query(ConnectedAccount)
            .filter(ConnectedAccount.id == req.account_id)
            .first()
        )
    else:
        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.platform == "Instagram",
                ConnectedAccount.account_id != media_scan.DEMO_ACCOUNT_ID,
            )
            .order_by(ConnectedAccount.id.desc())
            .first()
        )

    if not account:
        return {
            "success": False,
            "message": "No Instagram account connected. Connect one first, or run a demo scan.",
        }

    try:
        result = media_scan.scan_live(db, account)
    except RuntimeError as exc:
        return {"success": False, "message": str(exc)}
    except Exception:
        return {"success": False, "message": "Scan failed. Please try again."}
    return {"success": True, **result}


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
