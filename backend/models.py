from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    followers = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utc_now)


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(Integer, primary_key=True, index=True)
    instagram_user_id = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=False)
    encrypted_token = Column(String(1024), nullable=False)
    created_at = Column(DateTime, default=utc_now)


class MediaCheck(Base):
    __tablename__ = "media_checks"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    media_url = Column(String(1024), nullable=False)
    has_audio = Column(Boolean, nullable=True)  # Nullable in case a scan fails
    scan_status = Column(String(50), default="completed")
    scanned_at = Column(DateTime, default=utc_now)

    profile = relationship("Profile", backref="media_checks")


class LinkCheck(Base):
    __tablename__ = "link_checks"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    url = Column(String(1024), nullable=False)
    status_code = Column(Integer, nullable=True)
    is_broken = Column(Boolean, default=False)
    status_detail = Column(String(255), nullable=True)  # e.g., "ok", "broken", "inaccessible/timeout"
    checked_at = Column(DateTime, default=utc_now)

    profile = relationship("Profile", backref="link_checks")