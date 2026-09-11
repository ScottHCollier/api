from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from api.database import Base
from api.models import Club, ClubDomain, Player, Team
from api.seed import seed_database


def test_seed_is_repeatable_and_preserves_edits(session):
    club = session.scalars(select(Club).where(Club.slug == "montpellier-fc")).one()
    club_id = club.club_id
    before = {
        model: set(session.scalars(select(key)))
        for model, key in (
            (Club, Club.club_id),
            (ClubDomain, ClubDomain.club_domain_id),
            (Team, Team.team_id),
            (Player, Player.player_id),
        )
    }
    club.name = "Edited club name"
    session.flush()
    seed_database(session)
    session.expire_all()
    assert session.get(Club, club_id).name == "Edited club name"
    for model, expected in ((Club, 1), (ClubDomain, 1), (Team, 1), (Player, 8)):
        assert session.scalar(select(func.count()).select_from(model)) == expected
        key = inspect(model).primary_key[0]
        assert set(session.scalars(select(key))) == before[model]


def test_seed_restores_missing_records(session):
    team = session.scalars(select(Team).where(Team.name == "Men's First 11")).first()
    club_id = team.club_id
    session.delete(team)
    session.flush()
    seed_database(session)
    restored = session.scalars(
        select(Team).where(Team.club_id == club_id, Team.name == "Men's First 11")
    ).one()
    assert isinstance(restored.team_id, UUID)


def test_team_requires_existing_club(session):
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(Team(club_id=uuid4(), name="Under 16s"))
        session.flush()


def test_team_names_are_unique_within_club(session):
    club_id = session.scalars(select(Club.club_id)).first()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(Team(club_id=club_id, name="Men's First 11"))
        session.flush()


def test_seed_links_montpellier_first_team_to_fa_full_time(session):
    team = session.scalars(select(Team).where(Team.name == "Men's First 11")).one()
    assert team.external_provider == "fa_full_time"
    assert team.external_id == "963186578"
    assert team.external_league_id == "516676"
    assert team.external_name == "Montpellier"


def test_migration_round_trip_and_model_consistency(migrated_engine):
    with migrated_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        assert not compare_metadata(
            MigrationContext.configure(connection), Base.metadata
        )
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        command.upgrade(config, "head")
        assert not compare_metadata(
            MigrationContext.configure(
                connection, opts={"compare_server_default": True}
            ),
            Base.metadata,
        )


def test_database_generates_uuid_keys_and_cascades_deletes(session):
    club = Club(name="New club", slug="new-club")
    session.add(club)
    session.flush()
    domain = ClubDomain(hostname="new-club.localhost", club_id=club.club_id)
    team = Team(name="Seniors", club_id=club.club_id)
    session.add_all([domain, team])
    session.flush()
    assert all(
        isinstance(value, UUID) and value.version == 4
        for value in (club.club_id, domain.club_domain_id, team.team_id)
    )
    domain_id, team_id = domain.club_domain_id, team.team_id
    session.delete(club)
    session.flush()
    session.expunge_all()
    assert session.get(ClubDomain, domain_id) is None
    assert session.get(Team, team_id) is None


def test_uuid_migration_preserves_legacy_records_and_relationships(migrated_engine):
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.downgrade(config, "0001")
            connection.execute(
                text(
                    "INSERT INTO clubs (id, name, slug) VALUES "
                    "('custom-legacy-club', 'Edited club', 'custom-club')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO club_domains (hostname, club_id) VALUES "
                    "('custom.example', 'custom-legacy-club')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO teams (id, club_id, name) VALUES "
                    "('custom-team', 'custom-legacy-club', 'Seniors')"
                )
            )
            command.upgrade(config, "head")
            club = connection.execute(
                text("SELECT club_id, name FROM clubs WHERE slug = 'custom-club'")
            ).one()
            assert isinstance(club.club_id, UUID)
            assert club.name == "Edited club"
            domain = connection.execute(
                text(
                    "SELECT club_domain_id, club_id FROM club_domains "
                    "WHERE hostname = 'custom.example'"
                )
            ).one()
            team = connection.execute(
                text("SELECT team_id, club_id FROM teams WHERE name = 'Seniors'")
            ).one()
            assert isinstance(domain.club_domain_id, UUID)
            assert isinstance(team.team_id, UUID)
            assert domain.club_id == team.club_id == club.club_id
            command.downgrade(config, "0001")
            command.upgrade(config, "head")
            assert (
                connection.scalar(
                    text("SELECT club_id FROM clubs WHERE slug = 'custom-club'")
                )
                == club.club_id
            )
            assert (
                connection.scalar(
                    text("SELECT team_id FROM teams WHERE name = 'Seniors'")
                )
                == team.team_id
            )
        finally:
            transaction.rollback()
