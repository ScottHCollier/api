from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthRead(BaseModel):
    status: Literal["ok", "ready"]


class ClubRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    club_id: UUID
    name: str
    slug: str
    badge_url: str | None
    theme: dict | None = None


class ClubCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(
        min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )


class ClubThemeUpdate(BaseModel):
    theme: dict[str, dict[str, str]]


class PublicContactRead(BaseModel):
    contact_email: str | None
    contact_phone: str | None
    contact_address: str | None
    contact_description: str | None
    instagram_url: str | None
    facebook_url: str | None


class ClubContactUpdate(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=1000)
    instagram_url: str | None = Field(default=None, max_length=2048)
    facebook_url: str | None = Field(default=None, max_length=2048)


class HeroModeUpdate(BaseModel):
    mode: Literal["current", "image"]


class HeroSlideUpdate(BaseModel):
    position: int = Field(ge=0, le=2)
    image_id: UUID | None = None
    image_position: Literal["top", "center", "bottom"] = "center"
    eyebrow: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=500)


class HeroSlidesUpdate(BaseModel):
    slides: list[HeroSlideUpdate] = Field(min_length=1, max_length=3)


class ArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    article_id: UUID
    club_id: UUID
    image_id: UUID | None
    image_url: str | None = None
    title: str
    body: str
    status: Literal["draft", "published", "scheduled"]
    scheduled_at: datetime | None
    published_at: datetime


class ArticleCreate(BaseModel):
    image_id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    status: Literal["draft", "published", "scheduled"] = "published"
    scheduled_at: datetime | None = None


class ArticleUpdate(ArticleCreate):
    pass


class ImageFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: UUID | None = None


class ImageFolderUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ImageUpdate(BaseModel):
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    folder_id: UUID | None = None
    move_to_root: bool = False


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    external_provider: Literal["fa_full_time"] | None = None
    external_id: str | None = Field(default=None, max_length=100)
    external_league_id: str | None = Field(default=None, max_length=100)
    external_name: str | None = Field(default=None, max_length=200)
    external_url: str | None = Field(default=None, max_length=2048)


class TeamUpdate(TeamCreate):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    external_provider: Literal["fa_full_time"] | None = None
    external_id: str | None = Field(default=None, max_length=100)


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: UUID
    club_id: UUID
    name: str
    description: str
    external_provider: str | None
    external_id: str | None
    external_league_id: str | None
    external_name: str | None
    external_url: str | None


class LeagueStandingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    standing_id: UUID
    team_id: UUID
    position: int
    team_name: str
    played: int
    goal_difference: int
    points: int
    is_current_team: bool = False


class PlayerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: UUID
    club_id: UUID
    team_id: UUID | None
    legal_first_name: str
    legal_last_name: str
    position: str | None
    date_of_birth: date | None
    email: str | None
    phone: str | None
    guardian_name: str | None
    guardian_email: str | None
    guardian_phone: str | None
    fa_fan_id: str | None
    auto_renew_next_season: bool
    homegrown_player: bool
    registration_status: str
    consent_status: str
    notes: str | None


class PlayerCreate(BaseModel):
    team_id: UUID | None = None
    legal_first_name: str = Field(min_length=1, max_length=100)
    legal_last_name: str = Field(min_length=1, max_length=100)
    position: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    guardian_name: str | None = Field(default=None, max_length=200)
    guardian_email: str | None = Field(default=None, max_length=320)
    guardian_phone: str | None = Field(default=None, max_length=50)
    fa_fan_id: str | None = Field(default=None, max_length=50)
    auto_renew_next_season: bool = False
    homegrown_player: bool = False
    registration_status: Literal["pending", "invited", "complete"] = "pending"
    notes: str | None = Field(default=None, max_length=2000)


class RegistrationInviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RegistrationInviteRead(BaseModel):
    invite_url: str
    expires_at: datetime


class RegistrationInviteStatusRead(BaseModel):
    status: Literal["not_sent", "active", "expired", "accepted"]
    invited_email: str | None = None
    expires_at: datetime | None = None


class RegistrationInviteAccept(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    legal_first_name: str = Field(min_length=1, max_length=100)
    legal_last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    fa_fan_id: str | None = Field(default=None, max_length=50)
    consent: bool

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PaymentRead(BaseModel):
    payment_id: UUID
    club_id: UUID
    player_id: UUID
    player_name: str
    description: str
    amount_pence: int
    status: Literal["pending", "paid", "overdue", "cancelled"]
    due_date: date | None
    paid_at: datetime | None
    created_at: datetime


class PaymentCreate(BaseModel):
    player_id: UUID
    description: str = Field(min_length=1, max_length=200)
    amount_pence: int = Field(gt=0, le=10_000_000)
    due_date: date | None = None


class PaymentUpdate(BaseModel):
    status: Literal["pending", "paid", "overdue", "cancelled"]


class DocumentRead(BaseModel):
    document_id: UUID
    club_id: UUID
    player_id: UUID | None
    is_public: bool
    title: str
    category: str
    original_filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    download_url: str


class PublicDocumentRead(BaseModel):
    document_id: UUID
    club_id: UUID
    is_public: bool
    title: str
    category: str
    original_filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    download_url: str


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    player_id: UUID | None = None


class SafeguardingContactUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)


class PublicSafeguardingRead(BaseModel):
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    documents: list[PublicDocumentRead]


class FixtureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fixture_id: UUID
    club_id: UUID
    team_id: UUID
    title: str
    opposition: str | None
    is_home: bool | None
    competition: str | None
    starts_at: datetime
    venue: str
    home_score: int | None
    away_score: int | None
    external_provider: str | None
    external_id: str | None


class FixtureCreate(BaseModel):
    team_id: UUID
    title: str = Field(min_length=1, max_length=200)
    competition: str | None = Field(default=None, max_length=200)
    starts_at: datetime
    venue: str = Field(min_length=1, max_length=200)


class FixtureImportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    import_run_id: UUID
    club_id: UUID
    team_id: UUID
    status: Literal["queued", "running", "complete", "failed"]
    started_at: datetime
    completed_at: datetime | None
    created_count: int
    updated_count: int
    error: str | None
    attempt_count: int
    next_attempt_at: datetime | None


class AvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    availability_id: UUID
    fixture_id: UUID
    player_id: UUID
    status: Literal["available", "maybe", "unavailable"]
    note: str | None
    responded_at: datetime


class AvailabilityUpsert(BaseModel):
    player_id: UUID
    status: Literal["available", "maybe", "unavailable"]
    note: str | None = Field(default=None, max_length=500)


class FixtureSelectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    selection_id: UUID
    fixture_id: UUID
    player_id: UUID
    selected: bool
    updated_at: datetime


class FixtureSelectionUpsert(BaseModel):
    player_id: UUID
    selected: bool


class FixtureAttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attendance_id: UUID
    fixture_id: UUID
    player_id: UUID
    status: Literal["attended", "late", "absent", "injured"]
    note: str | None
    recorded_at: datetime


class FixtureAttendanceUpsert(BaseModel):
    player_id: UUID
    status: Literal["attended", "late", "absent", "injured"]
    note: str | None = Field(default=None, max_length=500)


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id: UUID
    club_id: UUID
    kind: str
    title: str
    body: str
    href: str | None
    read_at: datetime | None
    created_at: datetime


class MembershipRead(BaseModel):
    club_id: UUID
    club_slug: str
    role: Literal["member", "coach", "admin", "owner"]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    is_verified: bool
    is_active: bool
    created_at: datetime
    memberships: list[MembershipRead] = Field(default_factory=list)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            normalized.count("@") != 1
            or normalized.startswith("@")
            or normalized.endswith("@")
        ):
            raise ValueError("Enter a valid email address")
        return normalized


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class EmailVerification(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class NewsletterSubscribe(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1:
            raise ValueError("Enter a valid email address")
        return normalized


class NewsletterBroadcastCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    html: str = Field(min_length=1, max_length=100000)
    scheduled_at: datetime | None = None


class NewsletterBroadcastRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    broadcast_id: UUID
    club_id: UUID
    resend_id: str
    subject: str
    status: str
    scheduled_at: datetime | None
    created_at: datetime


class NewsletterSegmentUpdate(BaseModel):
    segment_id: str = Field(min_length=1, max_length=100)


class NewsletterSegmentRead(BaseModel):
    segment_id: str | None


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
