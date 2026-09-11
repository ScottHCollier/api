from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Club(Base):
    __tablename__ = "clubs"

    club_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    badge_url: Mapped[str | None] = mapped_column(String(2048))
    theme: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    instagram_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    hero_mode: Mapped[str] = mapped_column(String(20), server_default=text("'current'"))
    safeguarding_contact_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    safeguarding_contact_email: Mapped[str | None] = mapped_column(
        String(320), nullable=True
    )
    safeguarding_contact_phone: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    resend_segment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ImageAsset(Base):
    __tablename__ = "image_assets"

    image_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    folder_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("image_folders.folder_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_key: Mapped[str] = mapped_column(String(1024), unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_mime_type: Mapped[str] = mapped_column(String(100))
    original_size_bytes: Mapped[int] = mapped_column()
    width: Mapped[int] = mapped_column()
    height: Mapped[int] = mapped_column()
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    focal_x: Mapped[float | None] = mapped_column(nullable=True)
    focal_y: Mapped[float | None] = mapped_column(nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'")
    )
    thumb_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    card_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    hero_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ImageFolder(Base):
    __tablename__ = "image_folders"
    __table_args__ = (UniqueConstraint("club_id", "parent_id", "name"),)

    folder_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("image_folders.folder_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ClubImage(Base):
    __tablename__ = "club_images"
    __table_args__ = (
        UniqueConstraint("club_id", "image_id", name="uq_club_images_club_image"),
        Index(
            "uq_club_images_one_primary",
            "club_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    club_image_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    image_id: Mapped[UUID] = mapped_column(
        ForeignKey("image_assets.image_id", ondelete="CASCADE"), index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    position: Mapped[int] = mapped_column(server_default=text("0"))


class HeroSlide(Base):
    __tablename__ = "hero_slides"
    __table_args__ = (UniqueConstraint("club_id", "position"),)

    slide_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    image_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("image_assets.image_id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column()
    image_position: Mapped[str] = mapped_column(
        String(20), server_default=text("'center'")
    )
    eyebrow: Mapped[str] = mapped_column(
        String(100), server_default=text("'ONE CLUB. EVERYONE COUNTS.'")
    )
    title: Mapped[str] = mapped_column(
        String(300), server_default=text("'More than a football club.'")
    )
    body: Mapped[str] = mapped_column(String(500), server_default=text("''"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Article(Base):
    __tablename__ = "articles"

    article_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    image_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("image_assets.image_id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(String(10000))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'published'"), index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    user_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    token_version: Mapped[int] = mapped_column(server_default=text("0"))
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_club_created_at", "club_id", "created_at"),
        Index("ix_audit_events_actor_created_at", "actor_user_id", "created_at"),
    )

    audit_event_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )
    club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[UUID | None] = mapped_column(nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    bucket_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column()


class AccountToken(Base):
    __tablename__ = "account_tokens"
    __table_args__ = (UniqueConstraint("token_hash"),)

    account_token_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"
    __table_args__ = (UniqueConstraint("club_id", "email"),)

    subscriber_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'active'"))
    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class NewsletterBroadcast(Base):
    __tablename__ = "newsletter_broadcasts"

    broadcast_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True
    )
    resend_id: Mapped[str] = mapped_column(String(100), unique=True)
    subject: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), server_default=text("'draft'"))
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ClubMembership(Base):
    __tablename__ = "club_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "club_id", name="uq_club_memberships_user_club"),
        CheckConstraint(
            "role IN ('member', 'coach', 'admin', 'owner')",
            name="ck_club_memberships_role",
        ),
    )

    membership_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))


class ClubDomain(Base):
    __tablename__ = "club_domains"

    club_domain_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    hostname: Mapped[str] = mapped_column(String(253), unique=True)
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("club_id", "name"),
        UniqueConstraint(
            "external_provider",
            "external_id",
            name="uq_teams_external_provider_id",
        ),
    )

    team_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(1000), server_default=text("''"))
    # Provider identity is separate from the display name because league systems
    # may rename a team or present different names in different seasons.
    external_provider: Mapped[str | None] = mapped_column(String(50))
    external_id: Mapped[str | None] = mapped_column(String(100))
    external_league_id: Mapped[str | None] = mapped_column(String(100))
    external_name: Mapped[str | None] = mapped_column(String(200))
    external_url: Mapped[str | None] = mapped_column(String(2048))


class LeagueStanding(Base):
    __tablename__ = "league_standings"
    __table_args__ = (UniqueConstraint("team_id", "position"),)

    standing_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.team_id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column()
    team_name: Mapped[str] = mapped_column(String(200))
    played: Mapped[int] = mapped_column()
    goal_difference: Mapped[int] = mapped_column()
    points: Mapped[int] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("teams.team_id", ondelete="SET NULL"), index=True
    )
    legal_first_name: Mapped[str] = mapped_column(String(100))
    legal_last_name: Mapped[str] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    guardian_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fa_fan_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    auto_renew_next_season: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    homegrown_player: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    registration_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'")
    )
    consent_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'")
    )
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class PlayerGuardian(Base):
    __tablename__ = "player_guardians"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "user_id", name="uq_player_guardians_player_user"
        ),
    )

    player_guardian_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("club_id", "name"),)

    season_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(20))
    starts_on: Mapped[date] = mapped_column()
    ends_on: Mapped[date] = mapped_column()
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class PlayerRegistration(Base):
    __tablename__ = "player_registrations"
    __table_args__ = (
        UniqueConstraint("season_id", "player_id"),
        CheckConstraint(
            "status IN ('pending', 'invited', 'complete')",
            name="ck_player_registrations_status",
        ),
        CheckConstraint(
            "consent_status IN ('pending', 'complete')",
            name="ck_player_registrations_consent_status",
        ),
    )

    registration_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    season_id: Mapped[UUID] = mapped_column(
        ForeignKey("seasons.season_id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    consent_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RegistrationInvite(Base):
    __tablename__ = "registration_invites"
    __table_args__ = (
        UniqueConstraint("registration_id"),
        UniqueConstraint("token_hash"),
    )

    invite_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    registration_id: Mapped[UUID] = mapped_column(
        ForeignKey("player_registrations.registration_id", ondelete="CASCADE"),
        unique=True,
    )
    invited_email: Mapped[str] = mapped_column(String(320))
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'paid', 'overdue', 'cancelled')",
            name="ck_payments_status",
        ),
        CheckConstraint("amount_pence > 0", name="ck_payments_amount_positive"),
    )

    payment_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(200))
    amount_pence: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'"))
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ClubDocument(Base):
    __tablename__ = "club_documents"

    document_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), nullable=True, index=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100))
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class FixtureImportRun(Base):
    __tablename__ = "fixture_import_runs"

    import_run_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.team_id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_count: Mapped[int] = mapped_column(server_default=text("0"))
    updated_count: Mapped[int] = mapped_column(server_default=text("0"))
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempt_count: Mapped[int] = mapped_column(server_default=text("0"))
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Fixture(Base):
    __tablename__ = "fixtures"
    __table_args__ = (
        UniqueConstraint(
            "external_provider",
            "external_id",
            name="uq_fixtures_external_provider_id",
        ),
    )

    fixture_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.team_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    opposition: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_home: Mapped[bool | None] = mapped_column(nullable=True)
    competition: Mapped[str | None] = mapped_column(String(200), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    venue: Mapped[str] = mapped_column(String(200))
    home_score: Mapped[int | None] = mapped_column(nullable=True)
    away_score: Mapped[int | None] = mapped_column(nullable=True)
    external_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Availability(Base):
    __tablename__ = "availability"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id", "player_id", name="uq_availability_fixture_player"
        ),
        CheckConstraint(
            "status IN ('available', 'maybe', 'unavailable')",
            name="ck_availability_status",
        ),
    )

    availability_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.fixture_id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    responded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class FixtureSelection(Base):
    __tablename__ = "fixture_selections"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id", "player_id", name="uq_fixture_selection_fixture_player"
        ),
    )

    selection_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.fixture_id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    selected: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=datetime.now
    )


class FixtureAttendance(Base):
    __tablename__ = "fixture_attendance"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id", "player_id", name="uq_fixture_attendance_fixture_player"
        ),
        CheckConstraint(
            "status IN ('attended', 'late', 'absent', 'injured')",
            name="ck_fixture_attendance_status",
        ),
    )

    attendance_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.fixture_id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Notification(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.club_id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500))
    href: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
