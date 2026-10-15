"""Content-health scan: reels -> audio check -> media_checks rows.

Two modes:
  demo=True  - deterministic sample reels, simulated checks, no network.
               Stored under a demo account so the dashboard works with
               zero setup (same pattern as Step 2's sample data).
  demo=False - uses the connected account's token: pages through the media
               edge, downloads each media_url, runs ffprobe, writes results.
               Reels with no media_url (licensed audio) are recorded as
               unverifiable (has_audio=None) -- never flagged as no-audio.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime

from sqlalchemy.orm import Session

from models import ConnectedAccount, MediaCheck

DEMO_ACCOUNT_ID = "demo"
DEMO_USERNAME = "demo_account"

FIELDS = "id,caption,media_type,media_url,permalink,timestamp"
MAX_PAGES = 10  # safety cap: 10 pages x 25 reels


def _ffprobe_has_audio(path: str) -> bool:
    """True if the video file contains at least one audio stream."""
    if not shutil.which("ffprobe"):
        raise RuntimeError(
            "ffprobe is not installed. Install ffmpeg to scan real videos."
        )
    out = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return bool(out.stdout.strip())


# ---------------------------------------------------------------- demo mode

def demo_reels() -> list[dict]:
    """8 sample reels: 2 silent, 1 licensed-audio (unverifiable), 5 fine."""
    reels = []
    for i in range(1, 9):
        reels.append(
            {
                "id": f"demo_reel_{i:03d}",
                "media_type": "VIDEO",
                "caption": f"Demo reel #{i}",
                "media_url": f"https://example.com/demo_reel_{i:03d}.mp4",
                "permalink": f"https://www.instagram.com/reel/demo{i:03d}/",
                "timestamp": "2026-10-01T12:00:00+00:00",
            }
        )
    return reels


def _demo_audio_map() -> dict[str, bool | None]:
    return {
        "demo_reel_003": False,  # silent
        "demo_reel_005": None,   # licensed audio -> unverifiable
        "demo_reel_006": False,  # silent
    }


def _get_or_create_demo_account(db: Session) -> ConnectedAccount:
    acc = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.platform == "Instagram",
            ConnectedAccount.account_id == DEMO_ACCOUNT_ID,
        )
        .first()
    )
    if not acc:
        acc = ConnectedAccount(
            platform="Instagram",
            account_id=DEMO_ACCOUNT_ID,
            username=DEMO_USERNAME,
            access_token_encrypted="demo",  # placeholder; never used for API calls
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)
    return acc


def _clear_previous_checks(db: Session, account_pk: int) -> None:
    db.query(MediaCheck).filter(MediaCheck.account_id == account_pk).delete()
    db.commit()


def _record(db: Session, account_pk: int, media: dict, has_audio: bool | None) -> None:
    db.add(
        MediaCheck(
            account_id=account_pk,
            media_id=media["id"],
            media_type=media.get("media_type"),
            caption=(media.get("caption") or "")[:500],
            has_audio=has_audio,
        )
    )


def scan_demo(db: Session) -> dict:
    acc = _get_or_create_demo_account(db)
    _clear_previous_checks(db, acc.id)

    audio_map = _demo_audio_map()
    results = []
    for reel in demo_reels():
        has_audio = audio_map.get(reel["id"], True)
        _record(db, acc.id, reel, has_audio)
        results.append({**reel, "has_audio": has_audio})
    db.commit()

    return {
        "demo": True,
        "account": DEMO_USERNAME,
        "total": len(results),
        "flagged": [r for r in results if r["has_audio"] is False],
        "unverifiable": [r for r in results if r["has_audio"] is None],
        "results": results,
    }


# ---------------------------------------------------------------- live mode

def _graph_media_page(user_id: str, token: str, url: str | None) -> dict:
    if url is None:
        params = urllib.parse.urlencode(
            {"fields": FIELDS, "limit": 25, "access_token": token}
        )
        url = f"https://graph.instagram.com/{user_id}/media?{params}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)


def _download(url: str, dest: str) -> None:
    req = urllib.request.Request(
        url, headers={"User-Agent": "SocialMediaAnalyzer/1.0"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def scan_live(db: Session, account: ConnectedAccount) -> dict:
    from vault import decrypt_token

    token = decrypt_token(account.access_token_encrypted)
    user_id = account.account_id

    _clear_previous_checks(db, account.id)

    results, flagged, unverifiable = [], [], []
    url, pages = None, 0
    with tempfile.TemporaryDirectory() as tmp:
        while pages < MAX_PAGES:
            page = _graph_media_page(user_id, token, url)
            for media in page.get("data", []):
                media_url = media.get("media_url")
                if not media_url:
                    # Licensed audio (or otherwise withheld): unverifiable,
                    # never flagged.
                    _record(db, account.id, media, None)
                    unverifiable.append(media["id"])
                    results.append({**media, "has_audio": None})
                    continue
                dest = os.path.join(tmp, f"{media['id']}.mp4")
                try:
                    _download(media_url, dest)
                    has_audio = _ffprobe_has_audio(dest)
                except Exception:
                    has_audio = None  # download/check failed -> unverifiable
                finally:
                    if os.path.exists(dest):
                        os.remove(dest)
                _record(db, account.id, media, has_audio)
                results.append({**media, "has_audio": has_audio})
                if has_audio is False:
                    flagged.append(media["id"])
                elif has_audio is None:
                    unverifiable.append(media["id"])
            pages += 1
            url = (page.get("paging") or {}).get("next")
            if not url:
                break
            time.sleep(1)  # be polite to the API
    db.commit()

    account.last_scan_at = datetime.utcnow()
    db.commit()

    return {
        "demo": False,
        "account": account.username,
        "total": len(results),
        "flagged": [r for r in results if r["has_audio"] is False],
        "unverifiable": [r for r in results if r["has_audio"] is None],
        "results": results,
    }
