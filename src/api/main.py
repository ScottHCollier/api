import base64
import hashlib
import hmac
import html
import io
import json
import secrets
import time
from binascii import Error as Base64Error
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Security,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from PIL import Image, UnidentifiedImageError
from sqlalchemy import or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.config import get_settings
from api.database import get_session
from api.models import (
    AccountToken,
    Article,
    AuditEvent,
    Availability,
    Club,
    ClubDocument,
    ClubDomain,
    ClubImage,
    ClubMembership,
    Fixture,
    FixtureAttendance,
    FixtureImportRun,
    FixtureSelection,
    HeroSlide,
    ImageAsset,
    ImageFolder,
    LeagueStanding,
    NewsletterBroadcast,
    NewsletterSubscriber,
    Notification,
    Payment,
    Player,
    PlayerGuardian,
    PlayerRegistration,
    RegistrationInvite,
    Season,
    Team,
    User,
)
from api.schemas import (
    ArticleCreate,
    ArticleRead,
    ArticleUpdate,
    AvailabilityRead,
    AvailabilityUpsert,
    ClubContactUpdate,
    ClubCreate,
    ClubRead,
    ClubThemeUpdate,
    Credentials,
    DocumentRead,
    EmailVerification,
    FixtureAttendanceRead,
    FixtureAttendanceUpsert,
    FixtureCreate,
    FixtureImportRunRead,
    FixtureRead,
    FixtureSelectionRead,
    FixtureSelectionUpsert,
    HealthRead,
    HeroModeUpdate,
    HeroSlidesUpdate,
    ImageFolderCreate,
    ImageFolderUpdate,
    ImageUpdate,
    LeagueStandingRead,
    MembershipRead,
    NewsletterBroadcastCreate,
    NewsletterBroadcastRead,
    NewsletterSegmentRead,
    NewsletterSegmentUpdate,
    NewsletterSubscribe,
    NotificationRead,
    PasswordResetConfirm,
    PasswordResetRequest,
    PaymentCreate,
    PaymentRead,
    PaymentUpdate,
    PlayerCreate,
    PlayerRead,
    PublicContactRead,
    PublicDocumentRead,
    PublicSafeguardingRead,
    RegistrationInviteAccept,
    RegistrationInviteCreate,
    RegistrationInviteRead,
    RegistrationInviteStatusRead,
    SafeguardingContactUpdate,
    TeamCreate,
    TeamRead,
    TeamUpdate,
    TokenRead,
    UserRead,
)

app = FastAPI(title="Final Third API", version="0.1.0")
THEME_TOKENS = {
    "background", "surface", "surface-muted", "foreground", "muted", "line",
    "primary", "primary-foreground", "secondary", "secondary-foreground", "accent",
    "accent-soft", "button", "button-hover", "button-foreground", "success",
    "success-foreground", "warning", "warning-foreground", "danger", "danger-foreground",
    "overlay", "shadow",
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)
DatabaseSession = Annotated[Session, Depends(get_session)]
bearer = HTTPBearer(auto_error=False)


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except TypeError, ValueError:
        return False


def _token(user: User) -> tuple[str, int]:
    expires_in = get_settings().access_token_expire_minutes * 60
    payload = {
        "sub": str(user.user_id),
        "ver": user.token_version,
        "exp": int(time.time()) + expires_in,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signature = hmac.new(
        get_settings().auth_secret.get_secret_value().encode(), encoded, hashlib.sha256
    ).digest()
    return (
        f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}",
        expires_in,
    )


def _account_token(session: Session, user: User, kind: str) -> str:
    raw = secrets.token_urlsafe(48)
    session.add(
        AccountToken(
            user_id=user.user_id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            kind=kind,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )
    return raw


def _send_account_email(user: User, kind: str, raw_token: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key or not settings.email_from:
        return
    path = "verify-email" if kind == "email_verification" else "reset-password"
    subject = "Verify your Final Third account" if kind == "email_verification" else "Reset your Final Third password"
    link = f"{settings.app_base_url.rstrip('/')}/{path}?token={raw_token}"
    payload = json.dumps({
        "from": settings.email_from,
        "to": [user.email],
        "subject": subject,
        "html": f'<p>Use this link to continue: <a href="{link}">{link}</a></p><p>This link expires in 24 hours.</p>',
    }).encode()
    request = UrlRequest(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10):
            pass
    except (OSError, URLError) as exc:
            raise HTTPException(503, "Email delivery is unavailable") from exc


def _resend_contact(segment_id: str, email: str, unsubscribe: bool = False) -> None:
    settings = get_settings()
    if not settings.resend_api_key or not settings.resend_audience_id:
        return
    auth = {
        "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    encoded_email = quote(email, safe="")
    try:
        if unsubscribe:
            request = UrlRequest(
                f"https://api.resend.com/contacts/{encoded_email}/segments/{segment_id}",
                headers=auth,
                method="DELETE",
            )
            with urlopen(request, timeout=10):
                pass
            return
        endpoint = f"https://api.resend.com/audiences/{settings.resend_audience_id}/contacts"
        payload = json.dumps(
            {
                "email": email,
                "unsubscribed": False,
                "segments": [{"id": segment_id}],
            }
        ).encode()
        request = UrlRequest(endpoint, data=payload, headers=auth, method="POST")
        with urlopen(request, timeout=10):
            pass
    except HTTPError as exc:
        if unsubscribe or exc.code != 409:
            raise HTTPException(503, "Newsletter service is unavailable") from exc
        update = UrlRequest(
            f"https://api.resend.com/audiences/{settings.resend_audience_id}/contacts/{encoded_email}",
            data=json.dumps({"unsubscribed": False}).encode(),
            headers=auth,
            method="PATCH",
        )
        try:
            with urlopen(update, timeout=10):
                pass
            add = UrlRequest(
                f"https://api.resend.com/contacts/{encoded_email}/segments/{segment_id}",
                data=b"{}",
                headers=auth,
                method="POST",
            )
            with urlopen(add, timeout=10):
                pass
        except (OSError, URLError) as retry_exc:
            raise HTTPException(503, "Newsletter service is unavailable") from retry_exc
    except (OSError, URLError) as exc:
        raise HTTPException(503, "Newsletter service is unavailable") from exc


def _resend_broadcast(
    segment_id: str,
    subject: str,
    content: str,
    scheduled_at: datetime | None,
) -> str:
    settings = get_settings()
    if not settings.resend_api_key or not settings.email_from:
        raise HTTPException(503, "Newsletter email is not configured")
    payload: dict[str, object] = {
        "segment_id": segment_id,
        "from": settings.email_from,
        "subject": subject,
        "html": content,
        "send": True,
    }
    if scheduled_at is not None:
        payload["scheduled_at"] = scheduled_at.isoformat()
    request = UrlRequest(
        "https://api.resend.com/broadcasts",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read())
    except (OSError, URLError) as exc:
        raise HTTPException(503, "Newsletter service is unavailable") from exc
    resend_id = result.get("id")
    if not isinstance(resend_id, str):
        raise HTTPException(503, "Newsletter service returned an invalid response")
    return resend_id


def _user_read(user: User, session: Session) -> UserRead:
    memberships = session.execute(
        select(ClubMembership, Club.slug)
        .join(Club, Club.club_id == ClubMembership.club_id)
        .where(ClubMembership.user_id == user.user_id)
        .order_by(Club.slug)
    ).all()
    return UserRead(
        user_id=user.user_id,
        email=user.email,
        is_verified=user.is_verified,
        is_active=user.is_active,
        created_at=user.created_at,
        memberships=[
            MembershipRead(
                club_id=membership.club_id, club_slug=slug, role=membership.role
            )
            for membership, slug in memberships
        ],
    )


def _current_user(
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        encoded, encoded_signature = credentials.credentials.split(".", 1)
        padded = encoded_signature + "=" * (-len(encoded_signature) % 4)
        expected = hmac.new(
            get_settings().auth_secret.get_secret_value().encode(),
            encoded.encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(base64.urlsafe_b64decode(padded), expected):
            raise ValueError
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        if int(payload["exp"]) <= int(time.time()):
            raise ValueError
        user_id = UUID(payload["sub"])
    except Base64Error, ValueError, KeyError, TypeError, json.JSONDecodeError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token"
        ) from None
    user = session.get(User, user_id)
    if (
        user is None
        or not user.is_active
        or not user.is_verified
        or int(payload.get("ver", -1)) != user.token_version
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or inactive user")
    return user


CurrentUser = Annotated[User, Depends(_current_user)]
UploadedImage = Annotated[UploadFile, File(...)]


def _audit(
    session: Session,
    user: User | None,
    club_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_user_id=user.user_id if user else None,
            club_id=club_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )


def _enforce_rate_limit(session: Session, request: Request, scope: str, limit: int) -> None:
    """Apply a shared PostgreSQL-backed fixed-window limit."""
    client = request.client.host if request.client else "unknown"
    key = f"{scope}:{client}"[:200]
    now = datetime.now(UTC)
    result = session.execute(
        text(
            """
            INSERT INTO rate_limit_buckets (bucket_key, window_started_at, request_count)
            VALUES (:key, :now, 1)
            ON CONFLICT (bucket_key) DO UPDATE SET
              window_started_at = CASE
                WHEN rate_limit_buckets.window_started_at < :cutoff THEN :now
                ELSE rate_limit_buckets.window_started_at
              END,
              request_count = CASE
                WHEN rate_limit_buckets.window_started_at < :cutoff THEN 1
                ELSE rate_limit_buckets.request_count + 1
              END
            RETURNING request_count
            """
        ),
        {"key": key, "now": now, "cutoff": now - timedelta(minutes=1)},
    )
    if result.scalar_one() > limit:
        raise HTTPException(429, "Too many requests; try again shortly", headers={"Retry-After": "60"})


def _document_content_matches(mime_type: str | None, source: bytes) -> bool:
    if mime_type == "application/pdf":
        return source.startswith(b"%PDF-")
    if mime_type == "image/jpeg":
        return source.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return source.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "text/plain":
        return b"\x00" not in source
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            with ZipFile(io.BytesIO(source)) as archive:
                return "[Content_Types].xml" in archive.namelist()
        except BadZipFile:
            return False
    return False


def _notify(
    session: Session,
    user_id: UUID,
    club_id: UUID,
    kind: str,
    title: str,
    body: str,
    href: str | None = None,
) -> None:
    session.add(
        Notification(
            user_id=user_id,
            club_id=club_id,
            kind=kind,
            title=title,
            body=body,
            href=href,
        )
    )


def _notify_roles(
    session: Session,
    club_id: UUID,
    roles: set[str],
    kind: str,
    title: str,
    body: str,
    href: str | None = None,
    exclude_user_id: UUID | None = None,
) -> None:
    users = session.scalars(
        select(ClubMembership.user_id).where(
            ClubMembership.club_id == club_id,
            ClubMembership.role.in_(roles),
        )
    )
    for user_id in users:
        if user_id != exclude_user_id:
            _notify(session, user_id, club_id, kind, title, body, href)


@app.get("/health", response_model=HealthRead, tags=["health"])
def health() -> HealthRead:
    return HealthRead(status="ok")


@app.post(
    "/api/v1/auth/register",
    response_model=TokenRead,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
def register(request: Request, credentials: Credentials, session: DatabaseSession) -> TokenRead:
    _enforce_rate_limit(session, request, "auth-register", 10)
    if session.scalar(select(User).where(User.email == credentials.email)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists"
        )
    user = User(
        email=credentials.email,
        password_hash=_password_hash(credentials.password),
        is_verified=False,
    )
    session.add(user)
    session.flush()
    access_token, expires_in = _token(user)
    verification_token = _account_token(session, user, "email_verification")
    _send_account_email(user, "email_verification", verification_token)
    session.commit()
    return TokenRead(
        access_token=access_token, expires_in=expires_in, user=_user_read(user, session)
    )


@app.post("/api/v1/auth/login", response_model=TokenRead, tags=["auth"])
def login(request: Request, credentials: Credentials, session: DatabaseSession) -> TokenRead:
    _enforce_rate_limit(session, request, "auth-login", 10)
    user = session.scalar(select(User).where(User.email == credentials.email))
    if user is None or not _password_matches(credentials.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verify your email before signing in")
    access_token, expires_in = _token(user)
    return TokenRead(
        access_token=access_token, expires_in=expires_in, user=_user_read(user, session)
    )


@app.post("/api/v1/auth/verification-email", status_code=202, tags=["auth"])
def request_verification_email(
    request: Request, credentials: PasswordResetRequest, session: DatabaseSession
) -> dict[str, str]:
    _enforce_rate_limit(session, request, "auth-verify-email", 5)
    user = session.scalar(select(User).where(User.email == credentials.email))
    if user is not None:
        raw = _account_token(session, user, "email_verification")
        session.commit()
        _send_account_email(user, "email_verification", raw)
    return {"detail": "If the account exists, a verification email has been sent"}


@app.post("/api/v1/auth/verify-email", status_code=204, tags=["auth"])
def verify_email(details: EmailVerification, session: DatabaseSession) -> None:
    token = session.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == hashlib.sha256(details.token.encode()).hexdigest(),
            AccountToken.kind == "email_verification",
            AccountToken.used_at.is_(None),
        )
    )
    if token is None or token.expires_at <= datetime.now(UTC):
        raise HTTPException(400, "This verification link is invalid or expired")
    user = session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(400, "This verification link is invalid or expired")
    token.used_at = datetime.now(UTC)
    user.is_verified = True
    user.token_version += 1
    session.commit()


@app.post("/api/v1/auth/password-reset/request", status_code=202, tags=["auth"])
def request_password_reset(
    request: Request, details: PasswordResetRequest, session: DatabaseSession
) -> dict[str, str]:
    _enforce_rate_limit(session, request, "auth-password-reset", 5)
    user = session.scalar(select(User).where(User.email == details.email))
    if user is not None and user.is_active:
        raw = _account_token(session, user, "password_reset")
        session.commit()
        _send_account_email(user, "password_reset", raw)
    return {"detail": "If the account exists, a password reset email has been sent"}


@app.post("/api/v1/auth/password-reset/confirm", status_code=204, tags=["auth"])
def confirm_password_reset(
    details: PasswordResetConfirm, session: DatabaseSession
) -> None:
    token = session.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == hashlib.sha256(details.token.encode()).hexdigest(),
            AccountToken.kind == "password_reset",
            AccountToken.used_at.is_(None),
        )
    )
    if token is None or token.expires_at <= datetime.now(UTC):
        raise HTTPException(400, "This password reset link is invalid or expired")
    user = session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(400, "This password reset link is invalid or expired")
    user.password_hash = _password_hash(details.password)
    user.token_version += 1
    token.used_at = datetime.now(UTC)
    _audit(session, user, None, "account.password_reset", "user", user.user_id)
    session.commit()


@app.get("/api/v1/auth/me", response_model=UserRead, tags=["auth"])
def me(
    user: Annotated[User, Depends(_current_user)], session: DatabaseSession
) -> UserRead:
    return _user_read(user, session)


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def logout(user: CurrentUser, session: DatabaseSession) -> None:
    """Invalidate all access tokens issued for the current account."""
    user.token_version += 1
    session.commit()


@app.post(
    "/api/v1/clubs",
    response_model=ClubRead,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    tags=["clubs"],
)
def create_club(
    details: ClubCreate,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> Club:
    if session.scalar(select(Club).where(Club.slug == details.slug)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That club address is already in use"
        )
    club = Club(name=details.name.strip(), slug=details.slug)
    session.add(club)
    session.flush()
    session.add(ClubDomain(hostname=f"{club.slug}.localhost", club_id=club.club_id))
    session.add(
        ClubMembership(user_id=user.user_id, club_id=club.club_id, role="owner")
    )
    session.commit()
    session.refresh(club)
    return club


@app.get("/health/ready", response_model=HealthRead, tags=["health"])
def ready(session: DatabaseSession) -> HealthRead:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return HealthRead(status="ready")


@app.get(
    "/api/v1/public/clubs/resolve",
    response_model=ClubRead,
    response_model_exclude_none=True,
    tags=["clubs"],
    summary="Resolve a club by its registered hostname",
)
def resolve_club(
    session: DatabaseSession,
    hostname: Annotated[
        str,
        Query(
            min_length=1,
            max_length=253,
            description=(
                "Registered hostname, including the domain, without a scheme or port. "
                "For the demo club use montpellier-fc.localhost; "
                "the slug montpellier-fc alone does not match a registered hostname."
            ),
            examples=["montpellier-fc.localhost"],
        ),
    ],
) -> Club:
    # Public identity lookup only; a registered domain is not authorization.
    normalized = hostname.lower().rstrip(".")
    club = session.scalar(
        select(Club)
        .join(ClubDomain, ClubDomain.club_id == Club.club_id)
        .where(ClubDomain.hostname == normalized)
    )
    if club is None:
        raise HTTPException(404, "Club not found")
    return club


@app.patch("/api/v1/clubs/{club_id}/contact", response_model=ClubRead, response_model_exclude_none=True, tags=["clubs"])
def update_club_contact(club_id: UUID, details: ClubContactUpdate, session: DatabaseSession, user: CurrentUser) -> Club:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    club.contact_email = details.email.strip() if details.email else None
    club.contact_phone = details.phone.strip() if details.phone else None
    club.contact_address = details.address.strip() if details.address else None
    club.contact_description = details.description.strip() if details.description else None
    club.instagram_url = details.instagram_url.strip() if details.instagram_url else None
    club.facebook_url = details.facebook_url.strip() if details.facebook_url else None
    session.commit()
    session.refresh(club)
    return club


@app.patch("/api/v1/clubs/{club_id}/theme", response_model=ClubRead, response_model_exclude_none=True, tags=["clubs"])
def update_club_theme(
    club_id: UUID,
    details: ClubThemeUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> Club:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    if set(details.theme) != {"light", "dark"} or any(
        set(palette) != THEME_TOKENS for palette in details.theme.values()
    ):
        raise HTTPException(422, "Theme must include light and dark palettes")
    for palette in details.theme.values():
        if any(
            not isinstance(value, str)
            or len(value) != 7
            or value[0] != "#"
            or any(character not in "0123456789abcdefABCDEF" for character in value[1:])
            for value in palette.values()
        ):
            raise HTTPException(422, "Theme colours must be six-digit hexadecimal values")
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    club.theme = details.theme
    session.commit()
    session.refresh(club)
    return club


@app.get("/api/v1/public/clubs/{club_id}/contact", response_model=PublicContactRead, tags=["clubs"])
def public_club_contact(club_id: UUID, session: DatabaseSession) -> PublicContactRead:
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    return PublicContactRead(contact_email=club.contact_email, contact_phone=club.contact_phone, contact_address=club.contact_address, contact_description=club.contact_description, instagram_url=club.instagram_url, facebook_url=club.facebook_url)


@app.get("/api/v1/public/clubs/{club_id}/hero-image", tags=["images"])
def get_public_club_hero_image(
    club_id: UUID, session: DatabaseSession
) -> dict[str, str]:
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    image = session.scalar(
        select(ImageAsset)
        .join(ClubImage, ClubImage.image_id == ImageAsset.image_id)
        .where(
            ClubImage.club_id == club_id,
            ClubImage.is_primary.is_(True),
            ImageAsset.processing_status == "complete",
        )
    )
    if image is None:
        return {"mode": club.hero_mode, "hero_url": ""}
    return {"mode": club.hero_mode, "hero_url": _hero_public_url(image.hero_key)}


def _article_read(article: Article, image: ImageAsset | None) -> dict[str, object]:
    return {
        "article_id": article.article_id,
        "club_id": article.club_id,
        "image_id": article.image_id,
        "image_url": _hero_public_url(image.hero_key) if image and image.hero_key else None,
        "title": article.title,
        "body": article.body,
        "status": article.status,
        "scheduled_at": article.scheduled_at,
        "published_at": article.published_at,
    }


@app.get("/api/v1/public/clubs/{club_id}/articles", response_model=list[ArticleRead], tags=["articles"])
def list_public_articles(club_id: UUID, session: DatabaseSession) -> list[dict[str, object]]:
    if session.get(Club, club_id) is None:
        raise HTTPException(404, "Club not found")
    rows = session.execute(
        select(Article, ImageAsset)
        .outerjoin(ImageAsset, ImageAsset.image_id == Article.image_id)
        .where(Article.club_id == club_id, Article.status != "draft", or_(Article.scheduled_at.is_(None), Article.scheduled_at <= datetime.now(UTC)))
        .order_by(Article.published_at.desc())
    ).all()
    return [_article_read(article, image) for article, image in rows]


@app.get("/api/v1/public/clubs/{club_id}/hero-slides", tags=["images"])
def get_public_hero_slides(
    club_id: UUID, session: DatabaseSession
) -> list[dict[str, object]]:
    if session.get(Club, club_id) is None:
        raise HTTPException(404, "Club not found")
    slides = session.execute(
        select(HeroSlide, ImageAsset.hero_key, ImageAsset.original_filename)
        .outerjoin(ImageAsset, ImageAsset.image_id == HeroSlide.image_id)
        .where(HeroSlide.club_id == club_id)
        .order_by(HeroSlide.position)
    ).all()
    if not slides:
        image = session.scalar(
            select(ImageAsset)
            .join(ClubImage, ClubImage.image_id == ImageAsset.image_id)
            .where(
                ClubImage.club_id == club_id,
                ClubImage.is_primary.is_(True),
                ImageAsset.processing_status == "complete",
            )
        )
        if image is None:
            return []
        return [
            {
                "position": 0,
                "image_id": image.image_id,
                "image_url": _hero_public_url(image.hero_key)
                if image.hero_key
                else None,
                "image_name": image.original_filename,
                "image_position": "center",
                "eyebrow": "ONE CLUB. EVERYONE COUNTS.",
                "title": "More than a football club.",
                "body": "A home for players, families and volunteers.",
            }
        ]
    return [
        {
            "position": slide.position,
            "image_id": slide.image_id,
            "image_url": _hero_public_url(hero_key) if hero_key else None,
            "image_name": original_filename,
            "image_position": slide.image_position,
            "eyebrow": slide.eyebrow,
            "title": slide.title,
            "body": slide.body,
        }
        for slide, hero_key, original_filename in slides
    ]


@app.get(
    "/api/v1/public/clubs/{club_id}/teams",
    response_model=list[TeamRead],
    tags=["teams"],
)
def list_teams(club_id: UUID, session: DatabaseSession) -> list[Team]:
    if session.get(Club, club_id) is None:
        raise HTTPException(404, "Club not found")
    return list(
        session.scalars(select(Team).where(Team.club_id == club_id).order_by(Team.name))
    )


@app.get(
    "/api/v1/public/clubs/{club_id}/fixtures",
    response_model=list[FixtureRead],
    tags=["fixtures"],
)
def list_public_fixtures(club_id: UUID, session: DatabaseSession) -> list[Fixture]:
    if session.get(Club, club_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found")
    return list(
        session.scalars(
            select(Fixture)
            .where(Fixture.club_id == club_id)
            .order_by(Fixture.starts_at)
        )
    )


@app.get(
    "/api/v1/public/clubs/{club_id}/league",
    response_model=list[LeagueStandingRead],
    tags=["fixtures"],
)
def list_public_league_standings(
    club_id: UUID, session: DatabaseSession
) -> list[dict[str, object]]:
    if session.get(Club, club_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found")
    rows = session.scalars(
        select(LeagueStanding)
        .join(Team, Team.team_id == LeagueStanding.team_id)
        .where(Team.club_id == club_id)
        .order_by(LeagueStanding.position)
    ).all()
    return [
        {
            "standing_id": standing.standing_id,
            "team_id": standing.team_id,
            "position": standing.position,
            "team_name": standing.team_name,
            "played": standing.played,
            "goal_difference": standing.goal_difference,
            "points": standing.points,
            "is_current_team": False,
        }
        for standing in rows
    ]


@app.post(
    "/api/v1/clubs/{club_id}/teams",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
    tags=["teams"],
)
def create_team(
    club_id: UUID,
    team: TeamCreate,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> Team:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    if session.scalar(select(Club).where(Club.club_id == club_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found")
    if session.scalar(
        select(Team).where(Team.club_id == club_id, Team.name == team.name)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A team with that name already exists"
        )
    if (team.external_provider is None) != (team.external_id is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Provider and external ID must be supplied together",
        )
    record = Team(club_id=club_id, **team.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.put(
    "/api/v1/clubs/{club_id}/teams/{team_id}",
    response_model=TeamRead,
    tags=["teams"],
)
def update_team(
    club_id: UUID,
    team_id: UUID,
    team: TeamUpdate,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> Team:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    record = session.scalar(
        select(Team).where(Team.team_id == team_id, Team.club_id == club_id)
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    values = team.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(record, key, value)
    if (record.external_provider is None) != (record.external_id is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Provider and external ID must be supplied together",
        )
    session.commit()
    session.refresh(record)
    return record


@app.delete(
    "/api/v1/clubs/{club_id}/teams/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["teams"],
)
def delete_team(
    club_id: UUID,
    team_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> None:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    record = session.scalar(
        select(Team).where(Team.team_id == team_id, Team.club_id == club_id)
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    session.delete(record)
    session.commit()


@app.get(
    "/api/v1/clubs/{club_id}/players",
    response_model=list[PlayerRead],
    tags=["players"],
    summary="List players visible to the current club member",
)
def list_players(
    club_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> list[Player]:
    membership = session.scalar(
        select(ClubMembership).where(
            ClubMembership.user_id == user.user_id,
            ClubMembership.club_id == club_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are not a member of this club"
        )

    query = (
        select(Player)
        .where(Player.club_id == club_id)
        .order_by(Player.legal_last_name, Player.legal_first_name)
    )
    if membership.role not in {"owner", "admin", "coach"}:
        query = query.join(
            PlayerGuardian, PlayerGuardian.player_id == Player.player_id
        ).where(PlayerGuardian.user_id == user.user_id)
    players = list(session.scalars(query))
    season = session.scalar(
        select(Season).where(Season.club_id == club_id, Season.is_current.is_(True))
    )
    if season is not None:
        registrations = {
            item.player_id: item
            for item in session.scalars(
                select(PlayerRegistration).where(
                    PlayerRegistration.season_id == season.season_id,
                    PlayerRegistration.player_id.in_(
                        [item.player_id for item in players]
                    ),
                )
            )
        }
        for player in players:
            item = registrations.get(player.player_id)
            if item is not None:
                player.registration_status = item.status
                player.consent_status = item.consent_status
    return players


def _current_season(club_id: UUID, session: Session) -> Season:
    season = session.scalar(
        select(Season).where(Season.club_id == club_id, Season.is_current.is_(True))
    )
    if season is not None:
        return season
    now = datetime.now(UTC)
    year = now.year if now.month >= 7 else now.year - 1
    season = Season(
        club_id=club_id,
        name=f"{year}/{str(year + 1)[-2:]}",
        starts_on=datetime(year, 7, 1, tzinfo=UTC).date(),
        ends_on=datetime(year + 1, 6, 30, tzinfo=UTC).date(),
        is_current=True,
    )
    session.add(season)
    session.flush()
    return season


@app.post(
    "/api/v1/clubs/{club_id}/players",
    response_model=PlayerRead,
    status_code=201,
    tags=["players"],
)
def create_player(
    club_id: UUID,
    player: PlayerCreate,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> Player:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    if (
        player.team_id is not None
        and session.scalar(
            select(Team).where(Team.team_id == player.team_id, Team.club_id == club_id)
        )
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    record = Player(club_id=club_id, **player.model_dump())
    session.add(record)
    session.flush()
    season = _current_season(club_id, session)
    session.add(
        PlayerRegistration(season_id=season.season_id, player_id=record.player_id)
    )
    _audit(session, user, club_id, "player.created", "player", record.player_id)
    session.commit()
    session.refresh(record)
    return record


def _payment_read(payment: Payment, player: Player) -> PaymentRead:
    return PaymentRead(
        payment_id=payment.payment_id,
        club_id=payment.club_id,
        player_id=payment.player_id,
        player_name=f"{player.legal_first_name} {player.legal_last_name}",
        description=payment.description,
        amount_pence=payment.amount_pence,
        status=payment.status,
        due_date=payment.due_date,
        paid_at=payment.paid_at,
        created_at=payment.created_at,
    )


@app.get(
    "/api/v1/clubs/{club_id}/payments",
    response_model=list[PaymentRead],
    tags=["payments"],
)
def list_payments(
    club_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> list[PaymentRead]:
    membership = _club_membership(user, club_id, session)
    query = (
        select(Payment, Player)
        .join(Player, Player.player_id == Payment.player_id)
        .where(Payment.club_id == club_id, Player.club_id == club_id)
        .order_by(
            Payment.due_date.is_(None), Payment.due_date, Payment.created_at.desc()
        )
    )
    if membership.role not in {"owner", "admin", "coach"}:
        query = query.join(
            PlayerGuardian, PlayerGuardian.player_id == Payment.player_id
        ).where(PlayerGuardian.user_id == user.user_id)
    return [
        _payment_read(payment, player) for payment, player in session.execute(query)
    ]


@app.post(
    "/api/v1/clubs/{club_id}/payments",
    response_model=PaymentRead,
    status_code=201,
    tags=["payments"],
)
def create_payment(
    club_id: UUID,
    details: PaymentCreate,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> PaymentRead:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    player = session.scalar(
        select(Player).where(
            Player.player_id == details.player_id, Player.club_id == club_id
        )
    )
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    payment = Payment(club_id=club_id, **details.model_dump())
    session.add(payment)
    session.flush()
    _audit(session, user, club_id, "payment.created", "payment", payment.payment_id)
    session.commit()
    session.refresh(payment)
    return _payment_read(payment, player)


@app.patch(
    "/api/v1/clubs/{club_id}/payments/{payment_id}",
    response_model=PaymentRead,
    tags=["payments"],
)
def update_payment(
    club_id: UUID,
    payment_id: UUID,
    details: PaymentUpdate,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> PaymentRead:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    payment = session.scalar(
        select(Payment).where(
            Payment.payment_id == payment_id, Payment.club_id == club_id
        )
    )
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    payment.status = details.status
    payment.paid_at = datetime.now(UTC) if details.status == "paid" else None
    player = session.get(Player, payment.player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    _audit(
        session,
        user,
        club_id,
        "payment.status_updated",
        "payment",
        payment.payment_id,
        {"status": details.status},
    )
    session.commit()
    session.refresh(payment)
    return _payment_read(payment, player)


def _document_url(key: str, filename: str) -> str:
    try:
        return _object_storage_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": get_settings().object_storage_private_bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=3600,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, "Document storage is unavailable") from exc


def _document_read(document: ClubDocument) -> DocumentRead:
    return DocumentRead(
        document_id=document.document_id,
        club_id=document.club_id,
        player_id=document.player_id,
        is_public=document.is_public,
        title=document.title,
        category=document.category,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        created_at=document.created_at,
        download_url=_document_url(document.object_key, document.original_filename),
    )


@app.get(
    "/api/v1/clubs/{club_id}/documents",
    response_model=list[DocumentRead],
    tags=["documents"],
)
def list_documents(
    club_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> list[DocumentRead]:
    membership = _club_membership(user, club_id, session)
    query = select(ClubDocument).where(ClubDocument.club_id == club_id)
    if membership.role not in {"owner", "admin", "coach"}:
        query = query.where(
            (ClubDocument.player_id.is_(None))
            | ClubDocument.player_id.in_(
                select(PlayerGuardian.player_id).where(
                    PlayerGuardian.user_id == user.user_id
                )
            )
        )
    documents = session.scalars(query.order_by(ClubDocument.created_at.desc())).all()
    return [_document_read(document) for document in documents]


@app.post(
    "/api/v1/clubs/{club_id}/documents",
    response_model=DocumentRead,
    status_code=201,
    tags=["documents"],
)
def upload_document(
    club_id: UUID,
    title: Annotated[str, Query(min_length=1, max_length=200)],
    category: Annotated[str, Query(min_length=1, max_length=100)],
    document: Annotated[UploadFile, File(...)],
    session: DatabaseSession,
    user: CurrentUser,
    player_id: Annotated[UUID | None, Query()] = None,
    is_public: Annotated[bool, Query()] = False,
) -> DocumentRead:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    if is_public and player_id is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Player-linked documents cannot be published publicly",
        )
    if (
        player_id is not None
        and session.scalar(
            select(Player).where(
                Player.player_id == player_id, Player.club_id == club_id
            )
        )
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    allowed_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if document.content_type not in allowed_types:
        raise HTTPException(400, "Upload a PDF, image, text, or Word document")
    source = document.file.read(20 * 1024 * 1024 + 1)
    if len(source) > 20 * 1024 * 1024:
        raise HTTPException(413, "Document must be 20 MB or smaller")
    if not _document_content_matches(document.content_type, source):
        raise HTTPException(400, "The file content does not match its declared type")
    document_id = uuid4()
    filename = (
        (document.filename or "document")
        .replace("/", "_")
        .replace("\\", "_")
        .replace('"', "_")
        .replace("\r", "_")
        .replace("\n", "_")
    )
    if not filename.strip(" ."):
        filename = "document"
    key = f"clubs/{club_id}/documents/{document_id}/{filename}"
    try:
        _object_storage_client().put_object(
            Bucket=get_settings().object_storage_private_bucket,
            Key=key,
            Body=source,
            ContentType=document.content_type or "application/octet-stream",
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, "Document storage is unavailable") from exc
    record = ClubDocument(
        document_id=document_id,
        club_id=club_id,
        player_id=player_id,
        is_public=is_public,
        title=title.strip(),
        category=category.strip(),
        object_key=key,
        original_filename=filename,
        mime_type=document.content_type or "application/octet-stream",
        size_bytes=len(source),
    )
    session.add(record)
    _audit(session, user, club_id, "document.created", "document", document_id, {"public": is_public})
    try:
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        try:
            _object_storage_client().delete_object(
                Bucket=get_settings().object_storage_private_bucket, Key=key
            )
        except (BotoCoreError, ClientError):
            pass
        raise HTTPException(503, "Document could not be recorded") from exc
    session.refresh(record)
    return _document_read(record)


def _safeguarding_read(
    club: Club, documents: list[ClubDocument]
) -> PublicSafeguardingRead:
    return PublicSafeguardingRead(
        contact_name=club.safeguarding_contact_name,
        contact_email=club.safeguarding_contact_email,
        contact_phone=club.safeguarding_contact_phone,
        documents=[
            PublicDocumentRead(
                document_id=document.document_id,
                club_id=document.club_id,
                is_public=document.is_public,
                title=document.title,
                category=document.category,
                original_filename=document.original_filename,
                mime_type=document.mime_type,
                size_bytes=document.size_bytes,
                created_at=document.created_at,
                download_url=_document_url(
                    document.object_key, document.original_filename
                ),
            )
            for document in documents
        ],
    )


@app.get(
    "/api/v1/public/clubs/{club_id}/safeguarding",
    response_model=PublicSafeguardingRead,
    tags=["safeguarding"],
)
def public_safeguarding(
    club_id: UUID, session: DatabaseSession
) -> PublicSafeguardingRead:
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found")
    documents = session.scalars(
        select(ClubDocument)
        .where(ClubDocument.club_id == club_id, ClubDocument.is_public.is_(True))
        .order_by(ClubDocument.category, ClubDocument.title)
    ).all()
    return _safeguarding_read(club, documents)


@app.post(
    "/api/v1/public/clubs/{club_id}/newsletter/subscribe",
    status_code=202,
    tags=["newsletter"],
)
def subscribe_newsletter(
    request: Request, club_id: UUID, details: NewsletterSubscribe, session: DatabaseSession
) -> dict[str, str]:
    _enforce_rate_limit(session, request, "newsletter-subscribe", 5)
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    subscriber = session.scalar(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.club_id == club_id,
            NewsletterSubscriber.email == details.email,
        )
    )
    now = datetime.now(UTC)
    if subscriber is None:
        subscriber = NewsletterSubscriber(
            club_id=club_id, email=details.email, status="active", consented_at=now
        )
        session.add(subscriber)
    else:
        subscriber.status = "active"
        subscriber.consented_at = now
        subscriber.unsubscribed_at = None
    if get_settings().resend_api_key and get_settings().resend_audience_id and not club.resend_segment_id:
        raise HTTPException(503, "Newsletter segment is not configured")
    _resend_contact(club.resend_segment_id or "", details.email)
    session.commit()
    return {"detail": "You are subscribed to the club newsletter"}


@app.post(
    "/api/v1/public/clubs/{club_id}/newsletter/unsubscribe",
    status_code=202,
    tags=["newsletter"],
)
def unsubscribe_newsletter(
    club_id: UUID, details: NewsletterSubscribe, session: DatabaseSession
) -> dict[str, str]:
    subscriber = session.scalar(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.club_id == club_id,
            NewsletterSubscriber.email == details.email,
        )
    )
    if subscriber is not None:
        club = session.get(Club, club_id)
        if club is None:
            return {"detail": "If subscribed, the address has been removed"}
        subscriber.status = "unsubscribed"
        subscriber.unsubscribed_at = datetime.now(UTC)
        if get_settings().resend_api_key and get_settings().resend_audience_id and not club.resend_segment_id:
            raise HTTPException(503, "Newsletter segment is not configured")
        _resend_contact(club.resend_segment_id or "", details.email, unsubscribe=True)
        session.commit()
    return {"detail": "If subscribed, the address has been removed"}


@app.get(
    "/api/v1/clubs/{club_id}/newsletter/settings",
    response_model=NewsletterSegmentRead,
    tags=["newsletter"],
)
def get_newsletter_settings(
    club_id: UUID, user: CurrentUser, session: DatabaseSession
) -> NewsletterSegmentRead:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    return NewsletterSegmentRead(segment_id=club.resend_segment_id)


@app.patch(
    "/api/v1/clubs/{club_id}/newsletter/settings",
    response_model=NewsletterSegmentRead,
    tags=["newsletter"],
)
def update_newsletter_settings(
    club_id: UUID,
    details: NewsletterSegmentUpdate,
    user: CurrentUser,
    session: DatabaseSession,
) -> NewsletterSegmentRead:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    club.resend_segment_id = details.segment_id.strip()
    _audit(session, user, club_id, "newsletter.settings_updated", "club", club_id)
    session.commit()
    return NewsletterSegmentRead(segment_id=club.resend_segment_id)


@app.post(
    "/api/v1/clubs/{club_id}/newsletter/broadcasts",
    response_model=NewsletterBroadcastRead,
    status_code=201,
    tags=["newsletter"],
)
def create_newsletter_broadcast(
    club_id: UUID,
    details: NewsletterBroadcastCreate,
    user: CurrentUser,
    session: DatabaseSession,
) -> NewsletterBroadcast:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    if not club.resend_segment_id:
        raise HTTPException(409, "Configure the club's Resend segment before sending")
    content = (
        f"{details.html}"
        f"<p><small>You received this because you subscribed to "
        f"{html.escape(club.name)} news. "
        f'<a href="{{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}">Unsubscribe</a>.'
        "</small></p>"
    )
    resend_id = _resend_broadcast(
        club.resend_segment_id, details.subject.strip(), content, details.scheduled_at
    )
    status_value = "scheduled" if details.scheduled_at is not None else "sent"
    record = NewsletterBroadcast(
        club_id=club_id,
        created_by_user_id=user.user_id,
        resend_id=resend_id,
        subject=details.subject.strip(),
        status=status_value,
        scheduled_at=details.scheduled_at,
    )
    session.add(record)
    session.flush()
    _audit(session, user, club_id, "newsletter.broadcast_created", "broadcast", record.broadcast_id)
    session.commit()
    session.refresh(record)
    return record


@app.get(
    "/api/v1/clubs/{club_id}/safeguarding",
    response_model=PublicSafeguardingRead,
    tags=["safeguarding"],
)
def get_safeguarding_settings(
    club_id: UUID, user: CurrentUser, session: DatabaseSession
) -> PublicSafeguardingRead:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found")
    return _safeguarding_read(club, [])


@app.patch(
    "/api/v1/clubs/{club_id}/safeguarding",
    response_model=PublicSafeguardingRead,
    tags=["safeguarding"],
)
def update_safeguarding_settings(
    club_id: UUID,
    details: SafeguardingContactUpdate,
    user: CurrentUser,
    session: DatabaseSession,
) -> PublicSafeguardingRead:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Club not found")
    club.safeguarding_contact_name = details.name.strip() if details.name else None
    club.safeguarding_contact_email = details.email.strip() if details.email else None
    club.safeguarding_contact_phone = details.phone.strip() if details.phone else None
    session.commit()
    return _safeguarding_read(club, [])


@app.delete(
    "/api/v1/clubs/{club_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["documents"],
)
def delete_document(
    club_id: UUID,
    document_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> None:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    document = session.scalar(
        select(ClubDocument).where(
            ClubDocument.document_id == document_id, ClubDocument.club_id == club_id
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    try:
        _object_storage_client().delete_object(
            Bucket=get_settings().object_storage_private_bucket, Key=document.object_key
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, "Document storage is unavailable") from exc
    session.delete(document)
    _audit(session, user, club_id, "document.deleted", "document", document_id)
    session.commit()


@app.post(
    "/api/v1/clubs/{club_id}/players/{player_id}/registration-invites",
    response_model=RegistrationInviteRead,
    status_code=201,
    tags=["registrations"],
)
def create_registration_invite(
    club_id: UUID,
    player_id: UUID,
    invite: RegistrationInviteCreate,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> RegistrationInviteRead:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    player = session.scalar(
        select(Player).where(Player.player_id == player_id, Player.club_id == club_id)
    )
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    registration = session.scalar(
        select(PlayerRegistration)
        .join(Season)
        .where(
            PlayerRegistration.player_id == player_id,
            Season.club_id == club_id,
            Season.is_current.is_(True),
        )
    )
    if registration is None:
        registration = PlayerRegistration(
            season_id=_current_season(club_id, session).season_id, player_id=player_id
        )
        session.add(registration)
        session.flush()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=7)
    record = session.scalar(
        select(RegistrationInvite).where(
            RegistrationInvite.registration_id == registration.registration_id
        )
    )
    values = {
        "invited_email": invite.email,
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "expires_at": expires_at,
        "accepted_at": None,
    }
    if record is None:
        session.add(
            RegistrationInvite(registration_id=registration.registration_id, **values)
        )
    else:
        for key, value in values.items():
            setattr(record, key, value)
    registration.status = "invited"
    session.commit()
    return RegistrationInviteRead(
        invite_url=f"/register/player?token={token}", expires_at=expires_at
    )


def _registration_invite_access(
    club_id: UUID, player_id: UUID, user: User, session: Session
) -> tuple[Player, PlayerRegistration]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    player = session.scalar(
        select(Player).where(Player.player_id == player_id, Player.club_id == club_id)
    )
    registration = session.scalar(
        select(PlayerRegistration)
        .join(Season)
        .where(
            PlayerRegistration.player_id == player_id,
            Season.club_id == club_id,
            Season.is_current.is_(True),
        )
    )
    if player is None or registration is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registration not found")
    return player, registration


@app.get(
    "/api/v1/clubs/{club_id}/players/{player_id}/registration-invites",
    response_model=RegistrationInviteStatusRead,
    tags=["registrations"],
)
def registration_invite_status(
    club_id: UUID,
    player_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> RegistrationInviteStatusRead:
    _, registration = _registration_invite_access(club_id, player_id, user, session)
    invite = session.scalar(
        select(RegistrationInvite).where(
            RegistrationInvite.registration_id == registration.registration_id
        )
    )
    if invite is None:
        return RegistrationInviteStatusRead(status="not_sent")
    if invite.accepted_at is not None:
        current_status = "accepted"
    elif invite.expires_at <= datetime.now(UTC):
        current_status = "expired"
    else:
        current_status = "active"
    return RegistrationInviteStatusRead(
        status=current_status,
        invited_email=invite.invited_email,
        expires_at=invite.expires_at,
    )


@app.delete(
    "/api/v1/clubs/{club_id}/players/{player_id}/registration-invites",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["registrations"],
)
def revoke_registration_invite(
    club_id: UUID,
    player_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> None:
    _, registration = _registration_invite_access(club_id, player_id, user, session)
    invite = session.scalar(
        select(RegistrationInvite).where(
            RegistrationInvite.registration_id == registration.registration_id
        )
    )
    if invite is not None:
        session.delete(invite)
        registration.status = "pending"
        session.commit()


@app.post(
    "/api/v1/registration-invites/accept",
    response_model=TokenRead,
    tags=["registrations"],
)
def accept_registration_invite(
    details: RegistrationInviteAccept, session: DatabaseSession
) -> TokenRead:
    token_hash = hashlib.sha256(details.token.encode()).hexdigest()
    invite = session.scalar(
        select(RegistrationInvite).where(RegistrationInvite.token_hash == token_hash)
    )
    if (
        invite is None
        or invite.accepted_at is not None
        or invite.expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This registration invite is invalid or expired",
        )
    registration = session.get(PlayerRegistration, invite.registration_id)
    player = session.get(Player, registration.player_id) if registration else None
    if registration is None or player is None or details.email != invite.invited_email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Use the invited email address"
        )
    user = session.scalar(select(User).where(User.email == details.email))
    if user is None:
        user = User(email=details.email, password_hash=_password_hash(details.password))
        session.add(user)
        session.flush()
    elif not _password_matches(details.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "That account password is incorrect"
        )
    if (
        session.scalar(
            select(PlayerGuardian).where(
                PlayerGuardian.player_id == player.player_id,
                PlayerGuardian.user_id == user.user_id,
            )
        )
        is None
    ):
        session.add(PlayerGuardian(player_id=player.player_id, user_id=user.user_id))
    club_id = session.scalar(
        select(Season.club_id).where(Season.season_id == registration.season_id)
    )
    if (
        club_id is not None
        and session.scalar(
            select(ClubMembership).where(
                ClubMembership.user_id == user.user_id,
                ClubMembership.club_id == club_id,
            )
        )
        is None
    ):
        session.add(
            ClubMembership(user_id=user.user_id, club_id=club_id, role="member")
        )
    player.legal_first_name = details.legal_first_name
    player.legal_last_name = details.legal_last_name
    player.date_of_birth = details.date_of_birth
    player.fa_fan_id = details.fa_fan_id
    player.guardian_email = details.email
    player.registration_status = "complete"
    player.consent_status = "complete" if details.consent else "pending"
    registration.status = "complete" if details.consent else "pending"
    registration.consent_status = player.consent_status
    registration.completed_at = datetime.now(UTC) if details.consent else None
    invite.accepted_at = datetime.now(UTC)
    access_token, expires_in = _token(user)
    session.commit()
    return TokenRead(
        access_token=access_token, expires_in=expires_in, user=_user_read(user, session)
    )


def _club_membership(user: User, club_id: UUID, session: Session) -> ClubMembership:
    membership = session.scalar(
        select(ClubMembership).where(
            ClubMembership.user_id == user.user_id,
            ClubMembership.club_id == club_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are not a member of this club"
        )
    return membership


@app.get("/api/v1/clubs/{club_id}/articles", response_model=list[ArticleRead], tags=["articles"])
def list_articles(club_id: UUID, session: DatabaseSession, user: CurrentUser) -> list[dict[str, object]]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    rows = session.execute(
        select(Article, ImageAsset)
        .outerjoin(ImageAsset, ImageAsset.image_id == Article.image_id)
        .where(Article.club_id == club_id)
        .order_by(Article.published_at.desc())
    ).all()
    return [_article_read(article, image) for article, image in rows]


@app.post("/api/v1/clubs/{club_id}/articles", response_model=ArticleRead, status_code=201, tags=["articles"])
def create_article(club_id: UUID, details: ArticleCreate, session: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    image = None
    if details.image_id is not None:
        image = session.scalar(select(ImageAsset).where(ImageAsset.image_id == details.image_id, ImageAsset.club_id == club_id, ImageAsset.processing_status == "complete"))
        if image is None:
            raise HTTPException(422, "Article image does not belong to this club")
    if details.status == "scheduled" and details.scheduled_at is None:
        raise HTTPException(422, "Scheduled articles need a publish date")
    article = Article(club_id=club_id, image_id=details.image_id, title=details.title.strip(), body=details.body.strip(), status=details.status, scheduled_at=details.scheduled_at)
    session.add(article)
    session.commit()
    session.refresh(article)
    return _article_read(article, image)


@app.patch("/api/v1/clubs/{club_id}/articles/{article_id}", response_model=ArticleRead, tags=["articles"])
def update_article(club_id: UUID, article_id: UUID, details: ArticleUpdate, session: DatabaseSession, user: CurrentUser) -> dict[str, object]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    article = session.scalar(select(Article).where(Article.article_id == article_id, Article.club_id == club_id))
    if article is None:
        raise HTTPException(404, "Article not found")
    image = None
    if details.image_id is not None:
        image = session.scalar(select(ImageAsset).where(ImageAsset.image_id == details.image_id, ImageAsset.club_id == club_id, ImageAsset.processing_status == "complete"))
        if image is None:
            raise HTTPException(422, "Article image does not belong to this club")
    article.image_id = details.image_id
    article.title = details.title.strip()
    article.body = details.body.strip()
    if details.status == "scheduled" and details.scheduled_at is None:
        raise HTTPException(422, "Scheduled articles need a publish date")
    article.status = details.status
    article.scheduled_at = details.scheduled_at
    session.commit()
    session.refresh(article)
    return _article_read(article, image)


@app.delete("/api/v1/clubs/{club_id}/articles/{article_id}", status_code=204, tags=["articles"])
def delete_article(club_id: UUID, article_id: UUID, session: DatabaseSession, user: CurrentUser) -> None:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Admin access required")
    article = session.scalar(select(Article).where(Article.article_id == article_id, Article.club_id == club_id))
    if article is None:
        raise HTTPException(404, "Article not found")
    session.delete(article)
    _audit(session, user, club_id, "article.deleted", "article", article_id)
    session.commit()


def _object_storage_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        region_name=settings.object_storage_region,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key.get_secret_value(),
        config=BotoConfig(signature_version="s3v4"),
    )


def _hero_public_url(key: str) -> str:
    return f"{get_settings().object_storage_public_base_url.rstrip('/')}/{key}"


@app.post("/api/v1/clubs/{club_id}/hero-image", tags=["images"])
def upload_club_hero_image(
    club_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    image: UploadedImage,
    position: Annotated[int | None, Query()] = None,
) -> dict[str, object]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed_types:
        raise HTTPException(400, "Upload a JPEG, PNG, or WebP image")

    source = image.file.read(10 * 1024 * 1024 + 1)
    if len(source) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image must be 10 MB or smaller")
    try:
        with Image.open(io.BytesIO(source)) as source_image:
            source_image.verify()
        with Image.open(io.BytesIO(source)) as source_image:
            width, height = source_image.size
            hero = source_image.convert(
                "RGBA" if "A" in source_image.getbands() else "RGB"
            )
            hero.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
            hero_buffer = io.BytesIO()
            hero.save(hero_buffer, format="WEBP", quality=85, method=6)
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise HTTPException(400, "The uploaded file is not a readable image") from exc

    image_id = uuid4()
    prefix = f"clubs/{club_id}/images/{image_id}"
    original_key = f"{prefix}/original"
    hero_key = f"{prefix}/hero.webp"
    client = _object_storage_client()
    try:
        settings = get_settings()
        client.put_object(
            Bucket=settings.object_storage_bucket,
            Key=original_key,
            Body=source,
            ContentType=image.content_type,
        )
        client.put_object(
            Bucket=settings.object_storage_bucket,
            Key=hero_key,
            Body=hero_buffer.getvalue(),
            ContentType="image/webp",
            CacheControl="public, max-age=31536000, immutable",
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, "Image storage is unavailable") from exc

    asset = ImageAsset(
        image_id=image_id,
        club_id=club_id,
        original_key=original_key,
        original_filename=image.filename,
        original_mime_type=image.content_type,
        original_size_bytes=len(source),
        width=width,
        height=height,
        processing_status="complete",
        hero_key=hero_key,
    )
    session.add(asset)
    session.query(ClubImage).filter(
        ClubImage.club_id == club_id, ClubImage.is_primary.is_(True)
    ).update({ClubImage.is_primary: False}, synchronize_session=False)
    session.add(ClubImage(club_id=club_id, image_id=image_id, is_primary=True))
    if position is not None:
        if position < 0 or position > 2:
            raise HTTPException(422, "Hero slide position must be between 0 and 2")
        slide = session.scalar(
            select(HeroSlide).where(
                HeroSlide.club_id == club_id,
                HeroSlide.position == position,
            )
        )
        if slide is None:
            session.add(
                HeroSlide(club_id=club_id, position=position, image_id=image_id)
            )
        else:
            slide.image_id = image_id
    try:
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        for key in (original_key, hero_key):
            try:
                client.delete_object(Bucket=settings.object_storage_bucket, Key=key)
            except (BotoCoreError, ClientError):
                pass
        raise HTTPException(503, "Image could not be recorded") from exc
    return {
        "image_id": image_id,
        "width": width,
        "height": height,
        "hero_url": _hero_public_url(hero_key),
    }


@app.get("/api/v1/clubs/{club_id}/images", tags=["images"])
def list_club_images(
    club_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    folder_id: Annotated[UUID | None, Query()] = None,
) -> list[dict[str, object]]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    images = session.scalars(
        select(ImageAsset)
        .where(
            ImageAsset.club_id == club_id,
            ImageAsset.processing_status == "complete",
            ImageAsset.folder_id == folder_id if folder_id is not None else True,
        )
        .order_by(ImageAsset.created_at.desc())
    ).all()
    return [
        {
            "image_id": image.image_id,
            "folder_id": image.folder_id,
            "filename": image.original_filename,
            "mime_type": image.original_mime_type,
            "size_bytes": image.original_size_bytes,
            "width": image.width,
            "height": image.height,
            "created_at": image.created_at,
            "url": _hero_public_url(image.hero_key) if image.hero_key else None,
        }
        for image in images
    ]


@app.post("/api/v1/clubs/{club_id}/images", tags=["images"])
def upload_club_image(
    club_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    image: UploadedImage,
    folder_id: Annotated[UUID | None, Query()] = None,
) -> dict[str, object]:
    if (
        folder_id is not None
        and session.scalar(
            select(ImageFolder).where(
                ImageFolder.folder_id == folder_id, ImageFolder.club_id == club_id
            )
        )
        is None
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Image folder does not belong to this club",
        )
    result = upload_club_hero_image(club_id, session, user, image, None)
    asset = session.get(ImageAsset, result["image_id"])
    if asset is not None:
        asset.folder_id = folder_id
        session.commit()
    result["folder_id"] = folder_id
    return result


@app.post("/api/v1/clubs/{club_id}/badge", tags=["images"])
def upload_club_badge(
    club_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    image: UploadedImage,
) -> dict[str, str]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "Upload a JPEG, PNG, or WebP image")
    source = image.file.read(5 * 1024 * 1024 + 1)
    if len(source) > 5 * 1024 * 1024:
        raise HTTPException(413, "Badge must be 5 MB or smaller")
    try:
        with Image.open(io.BytesIO(source)) as source_image:
            source_image.verify()
        with Image.open(io.BytesIO(source)) as source_image:
            badge = source_image.convert(
                "RGBA" if "A" in source_image.getbands() else "RGB"
            )
            badge.thumbnail((800, 800), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            badge.save(buffer, format="WEBP", quality=90, method=6)
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(400, "The uploaded file is not a readable image") from exc
    key = f"clubs/{club_id}/badge.webp"
    settings = get_settings()
    try:
        _object_storage_client().put_object(
            Bucket=settings.object_storage_bucket,
            Key=key,
            Body=buffer.getvalue(),
            ContentType="image/webp",
            CacheControl="no-cache",
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, "Image storage is unavailable") from exc
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    club.badge_url = _hero_public_url(key)
    session.commit()
    return {"badge_url": club.badge_url}


@app.get("/api/v1/clubs/{club_id}/image-folders", tags=["images"])
def list_image_folders(
    club_id: UUID, session: DatabaseSession, user: CurrentUser
) -> list[dict[str, object]]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    folders = session.scalars(
        select(ImageFolder)
        .where(ImageFolder.club_id == club_id)
        .order_by(ImageFolder.name)
    ).all()
    return [
        {
            "folder_id": folder.folder_id,
            "parent_id": folder.parent_id,
            "name": folder.name,
        }
        for folder in folders
    ]


@app.post("/api/v1/clubs/{club_id}/image-folders", tags=["images"])
def create_image_folder(
    club_id: UUID,
    details: ImageFolderCreate,
    session: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    if (
        details.parent_id is not None
        and session.scalar(
            select(ImageFolder).where(
                ImageFolder.folder_id == details.parent_id,
                ImageFolder.club_id == club_id,
            )
        )
        is None
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Parent folder does not belong to this club",
        )
    folder = ImageFolder(
        club_id=club_id, parent_id=details.parent_id, name=details.name.strip()
    )
    session.add(folder)
    try:
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A folder with that name already exists here"
        ) from exc
    return {
        "folder_id": folder.folder_id,
        "parent_id": folder.parent_id,
        "name": folder.name,
    }


@app.patch("/api/v1/clubs/{club_id}/image-folders/{folder_id}", tags=["images"])
def update_image_folder(
    club_id: UUID,
    folder_id: UUID,
    details: ImageFolderUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    folder = session.scalar(
        select(ImageFolder).where(
            ImageFolder.folder_id == folder_id, ImageFolder.club_id == club_id
        )
    )
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")
    folder.name = details.name.strip()
    session.commit()
    return {
        "folder_id": folder.folder_id,
        "parent_id": folder.parent_id,
        "name": folder.name,
    }


@app.delete(
    "/api/v1/clubs/{club_id}/image-folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["images"],
)
def delete_image_folder(
    club_id: UUID, folder_id: UUID, session: DatabaseSession, user: CurrentUser
) -> None:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    folder = session.scalar(
        select(ImageFolder).where(
            ImageFolder.folder_id == folder_id, ImageFolder.club_id == club_id
        )
    )
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")
    session.query(ImageAsset).filter(ImageAsset.folder_id == folder_id).update(
        {ImageAsset.folder_id: None}, synchronize_session=False
    )
    session.delete(folder)
    session.commit()


@app.patch("/api/v1/clubs/{club_id}/images/{image_id}", tags=["images"])
def update_club_image(
    club_id: UUID,
    image_id: UUID,
    details: ImageUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> dict[str, object]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    image = session.scalar(
        select(ImageAsset).where(
            ImageAsset.image_id == image_id, ImageAsset.club_id == club_id
        )
    )
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    if (
        details.folder_id is not None
        and session.scalar(
            select(ImageFolder).where(
                ImageFolder.folder_id == details.folder_id,
                ImageFolder.club_id == club_id,
            )
        )
        is None
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Image folder does not belong to this club",
        )
    if details.filename is not None:
        image.original_filename = details.filename.strip()
    if details.folder_id is not None or details.move_to_root:
        image.folder_id = details.folder_id
    session.commit()
    return {
        "image_id": image.image_id,
        "folder_id": image.folder_id,
        "filename": image.original_filename,
    }


@app.delete(
    "/api/v1/clubs/{club_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["images"],
)
def delete_club_image(
    club_id: UUID,
    image_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> None:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    image = session.scalar(
        select(ImageAsset).where(
            ImageAsset.image_id == image_id, ImageAsset.club_id == club_id
        )
    )
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    client = _object_storage_client()
    settings = get_settings()
    keys = [image.original_key, image.thumb_key, image.card_key, image.hero_key]
    try:
        for key in keys:
            if key:
                client.delete_object(Bucket=settings.object_storage_bucket, Key=key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, "Image storage is unavailable") from exc
    session.delete(image)
    session.commit()


@app.put("/api/v1/clubs/{club_id}/hero-slides", tags=["images"])
def update_hero_slides(
    club_id: UUID,
    details: HeroSlidesUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[dict[str, object]]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    if len({slide.position for slide in details.slides}) != len(details.slides):
        raise HTTPException(422, "Each hero slide position must be unique")
    for details_slide in details.slides:
        if details_slide.image_id is not None:
            image = session.scalar(
                select(ImageAsset).where(
                    ImageAsset.image_id == details_slide.image_id,
                    ImageAsset.club_id == club_id,
                    ImageAsset.processing_status == "complete",
                )
            )
            if image is None:
                raise HTTPException(
                    422, "Hero slide image does not belong to this club"
                )
        slide = session.scalar(
            select(HeroSlide).where(
                HeroSlide.club_id == club_id,
                HeroSlide.position == details_slide.position,
            )
        )
        if slide is None:
            slide = HeroSlide(club_id=club_id, position=details_slide.position)
            session.add(slide)
        slide.image_id = details_slide.image_id
        slide.image_position = details_slide.image_position
        slide.eyebrow = details_slide.eyebrow
        slide.title = details_slide.title
        slide.body = details_slide.body
    session.commit()
    return [
        {"position": slide.position, "image_id": slide.image_id}
        for slide in details.slides
    ]


@app.patch("/api/v1/clubs/{club_id}/hero-mode", tags=["images"])
def update_club_hero_mode(
    club_id: UUID,
    details: HeroModeUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> dict[str, str]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Club not found")
    if details.mode == "image":
        has_image = session.scalar(
            select(ImageAsset.image_id)
            .join(ClubImage, ClubImage.image_id == ImageAsset.image_id)
            .where(
                ClubImage.club_id == club_id,
                ClubImage.is_primary.is_(True),
                ImageAsset.processing_status == "complete",
            )
        )
        if has_image is None:
            raise HTTPException(400, "Upload a hero image before selecting it")
    club.hero_mode = details.mode
    session.commit()
    return {"mode": club.hero_mode}


@app.get(
    "/api/v1/clubs/{club_id}/fixtures",
    response_model=list[FixtureRead],
    tags=["fixtures"],
)
def list_fixtures(
    club_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> list[Fixture]:
    _club_membership(user, club_id, session)
    return list(
        session.scalars(
            select(Fixture)
            .where(Fixture.club_id == club_id)
            .order_by(Fixture.starts_at)
        )
    )


@app.post(
    "/api/v1/clubs/{club_id}/fixture-import",
    tags=["fixtures"],
    summary="Synchronise linked FA Full-Time teams",
)
def sync_fixtures(
    club_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> dict[str, int | str]:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    linked_count = session.scalar(
        select(Team.team_id).where(
            Team.club_id == club_id,
            Team.external_provider == "fa_full_time",
            Team.external_id.is_not(None),
        )
    )
    if linked_count is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No FA Full-Time team is connected"
        )
    linked_teams = session.scalars(
        select(Team).where(
            Team.club_id == club_id,
            Team.external_provider == "fa_full_time",
            Team.external_id.is_not(None),
        )
    ).all()
    queued = 0
    for team in linked_teams:
        pending = session.scalar(
            select(FixtureImportRun).where(
                FixtureImportRun.team_id == team.team_id,
                FixtureImportRun.status == "queued",
            )
        )
        if pending is None:
            session.add(
                FixtureImportRun(club_id=club_id, team_id=team.team_id, status="queued")
            )
            queued += 1
    session.commit()
    return {"status": "queued", "created": queued, "updated": 0, "skipped": 0}


@app.get(
    "/api/v1/clubs/{club_id}/fixture-import/runs",
    response_model=list[FixtureImportRunRead],
    tags=["fixtures"],
)
def fixture_import_runs(
    club_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> list[FixtureImportRun]:
    _club_membership(user, club_id, session)
    return list(
        session.scalars(
            select(FixtureImportRun)
            .where(FixtureImportRun.club_id == club_id)
            .order_by(FixtureImportRun.started_at.desc())
            .limit(20)
        )
    )


@app.post(
    "/api/v1/clubs/{club_id}/fixtures",
    response_model=FixtureRead,
    status_code=status.HTTP_201_CREATED,
    tags=["fixtures"],
)
def create_fixture(
    club_id: UUID,
    fixture: FixtureCreate,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> Fixture:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    team = session.scalar(
        select(Team).where(Team.team_id == fixture.team_id, Team.club_id == club_id)
    )
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    record = Fixture(club_id=club_id, **fixture.model_dump())
    session.add(record)
    _notify_roles(
        session,
        club_id,
        {"owner", "admin", "coach", "member"},
        "fixture_created",
        "New fixture added",
        f"{record.title} has been added for {team.name}.",
        "/dashboard/availability",
        user.user_id,
    )
    session.commit()
    session.refresh(record)
    return record


@app.get(
    "/api/v1/clubs/{club_id}/fixtures/{fixture_id}/availability",
    response_model=list[AvailabilityRead],
    tags=["availability"],
)
def list_availability(
    club_id: UUID,
    fixture_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> list[Availability]:
    membership = _club_membership(user, club_id, session)
    fixture = session.scalar(
        select(Fixture).where(
            Fixture.fixture_id == fixture_id, Fixture.club_id == club_id
        )
    )
    if fixture is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fixture not found")
    query = select(Availability).where(Availability.fixture_id == fixture_id)
    if membership.role not in {"owner", "admin", "coach"}:
        query = query.join(
            PlayerGuardian, PlayerGuardian.player_id == Availability.player_id
        ).where(PlayerGuardian.user_id == user.user_id)
    return list(session.scalars(query))


@app.put(
    "/api/v1/clubs/{club_id}/fixtures/{fixture_id}/availability",
    response_model=AvailabilityRead,
    tags=["availability"],
)
def upsert_availability(
    club_id: UUID,
    fixture_id: UUID,
    response: AvailabilityUpsert,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> Availability:
    membership = _club_membership(user, club_id, session)
    fixture = session.scalar(
        select(Fixture).where(
            Fixture.fixture_id == fixture_id, Fixture.club_id == club_id
        )
    )
    player = session.scalar(
        select(Player).where(
            Player.player_id == response.player_id, Player.club_id == club_id
        )
    )
    if fixture is None or player is None or player.team_id != fixture.team_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fixture or player not found")
    if membership.role not in {"owner", "admin", "coach"}:
        linked = session.scalar(
            select(PlayerGuardian).where(
                PlayerGuardian.player_id == player.player_id,
                PlayerGuardian.user_id == user.user_id,
            )
        )
        if linked is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "You cannot respond for this player"
            )
    record = session.scalar(
        select(Availability).where(
            Availability.fixture_id == fixture_id,
            Availability.player_id == player.player_id,
        )
    )
    if record is None:
        record = Availability(
            fixture_id=fixture_id, player_id=player.player_id, **response.model_dump()
        )
        session.add(record)
    else:
        record.status = response.status
        record.note = response.note
    _notify_roles(
        session,
        club_id,
        {"owner", "admin", "coach"},
        "availability_response",
        "Availability response received",
        (
            f"{player.legal_first_name} {player.legal_last_name} responded "
            f"{response.status} for {fixture.title}."
        ),
        "/dashboard/availability",
        user.user_id,
    )
    session.commit()
    session.refresh(record)
    return record


@app.get(
    "/api/v1/clubs/{club_id}/fixtures/{fixture_id}/selection",
    response_model=list[FixtureSelectionRead],
    tags=["selection"],
)
def list_selection(
    club_id: UUID,
    fixture_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> list[FixtureSelection]:
    membership = _club_membership(user, club_id, session)
    fixture = session.scalar(
        select(Fixture).where(
            Fixture.fixture_id == fixture_id, Fixture.club_id == club_id
        )
    )
    if fixture is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fixture not found")
    query = select(FixtureSelection).where(FixtureSelection.fixture_id == fixture_id)
    if membership.role not in {"owner", "admin", "coach"}:
        query = query.join(
            PlayerGuardian, PlayerGuardian.player_id == FixtureSelection.player_id
        ).where(PlayerGuardian.user_id == user.user_id)
    return list(session.scalars(query))


@app.put(
    "/api/v1/clubs/{club_id}/fixtures/{fixture_id}/selection",
    response_model=FixtureSelectionRead,
    tags=["selection"],
)
def upsert_selection(
    club_id: UUID,
    fixture_id: UUID,
    selection: FixtureSelectionUpsert,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> FixtureSelection:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    fixture = session.scalar(
        select(Fixture).where(
            Fixture.fixture_id == fixture_id, Fixture.club_id == club_id
        )
    )
    player = session.scalar(
        select(Player).where(
            Player.player_id == selection.player_id, Player.club_id == club_id
        )
    )
    if fixture is None or player is None or player.team_id != fixture.team_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fixture or player not found")
    record = session.scalar(
        select(FixtureSelection).where(
            FixtureSelection.fixture_id == fixture_id,
            FixtureSelection.player_id == player.player_id,
        )
    )
    if record is None:
        record = FixtureSelection(
            fixture_id=fixture_id,
            player_id=player.player_id,
            selected=selection.selected,
        )
        session.add(record)
    else:
        record.selected = selection.selected
    guardians = session.scalars(
        select(PlayerGuardian.user_id).where(
            PlayerGuardian.player_id == player.player_id
        )
    )
    selection_text = (
        "has been selected for" if selection.selected else "is no longer selected for"
    )
    for guardian_id in guardians:
        _notify(
            session,
            guardian_id,
            club_id,
            "squad_selection",
            "Squad selection updated",
            (
                f"{player.legal_first_name} {player.legal_last_name} "
                f"{selection_text} {fixture.title}."
            ),
            "/dashboard/availability",
        )
    session.commit()
    session.refresh(record)
    return record


@app.get(
    "/api/v1/clubs/{club_id}/fixtures/{fixture_id}/attendance",
    response_model=list[FixtureAttendanceRead],
    tags=["attendance"],
)
def list_attendance(
    club_id: UUID,
    fixture_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> list[FixtureAttendance]:
    membership = _club_membership(user, club_id, session)
    fixture = session.scalar(
        select(Fixture).where(
            Fixture.fixture_id == fixture_id, Fixture.club_id == club_id
        )
    )
    if fixture is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fixture not found")
    query = select(FixtureAttendance).where(FixtureAttendance.fixture_id == fixture_id)
    if membership.role not in {"owner", "admin", "coach"}:
        query = query.join(
            PlayerGuardian, PlayerGuardian.player_id == FixtureAttendance.player_id
        ).where(PlayerGuardian.user_id == user.user_id)
    return list(session.scalars(query))


@app.put(
    "/api/v1/clubs/{club_id}/fixtures/{fixture_id}/attendance",
    response_model=FixtureAttendanceRead,
    tags=["attendance"],
)
def upsert_attendance(
    club_id: UUID,
    fixture_id: UUID,
    attendance: FixtureAttendanceUpsert,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> FixtureAttendance:
    membership = _club_membership(user, club_id, session)
    if membership.role not in {"owner", "admin", "coach"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Coach access required")
    fixture = session.scalar(
        select(Fixture).where(
            Fixture.fixture_id == fixture_id, Fixture.club_id == club_id
        )
    )
    player = session.scalar(
        select(Player).where(
            Player.player_id == attendance.player_id, Player.club_id == club_id
        )
    )
    if fixture is None or player is None or player.team_id != fixture.team_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fixture or player not found")
    record = session.scalar(
        select(FixtureAttendance).where(
            FixtureAttendance.fixture_id == fixture_id,
            FixtureAttendance.player_id == player.player_id,
        )
    )
    if record is None:
        record = FixtureAttendance(
            fixture_id=fixture_id,
            player_id=player.player_id,
            **attendance.model_dump(),
        )
        session.add(record)
    else:
        record.status = attendance.status
        record.note = attendance.note
    session.commit()
    session.refresh(record)
    return record


@app.get(
    "/api/v1/clubs/{club_id}/notifications",
    response_model=list[NotificationRead],
    tags=["notifications"],
)
def list_notifications(
    club_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> list[Notification]:
    _club_membership(user, club_id, session)
    return list(
        session.scalars(
            select(Notification)
            .where(
                Notification.club_id == club_id, Notification.user_id == user.user_id
            )
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    )


@app.put(
    "/api/v1/clubs/{club_id}/notifications/{notification_id}/read",
    response_model=NotificationRead,
    tags=["notifications"],
)
def mark_notification_read(
    club_id: UUID,
    notification_id: UUID,
    user: Annotated[User, Depends(_current_user)],
    session: DatabaseSession,
) -> Notification:
    _club_membership(user, club_id, session)
    notification = session.scalar(
        select(Notification).where(
            Notification.notification_id == notification_id,
            Notification.club_id == club_id,
            Notification.user_id == user.user_id,
        )
    )
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notification.read_at = datetime.now(UTC)
    session.commit()
    session.refresh(notification)
    return notification
