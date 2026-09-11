"""Import upcoming fixtures from linked FA Full-Time teams."""

import argparse
import logging
import re
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, or_, select

from api.config import get_settings
from api.database import SessionLocal
from api.fa_full_time import (
    FullTimeFixture,
    current_season_url,
    current_table_url,
    fetch_team_page,
    parse_fixtures,
    parse_standings,
)
from api.models import Fixture, FixtureImportRun, LeagueStanding, Team

logger = logging.getLogger(__name__)


def _normalise_team_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _fixture_team_details(
    item: FullTimeFixture, team: Team
) -> tuple[str | None, bool | None]:
    """Resolve the imported opposition against the team's provider display name."""
    team_name = _normalise_team_name(team.external_name or team.name)
    home_name = _normalise_team_name(item.home_team)
    away_name = _normalise_team_name(item.away_team)
    if team_name and (team_name in home_name or home_name in team_name):
        return item.away_team, True
    if team_name and (team_name in away_name or away_name in team_name):
        return item.home_team, False
    return None, None


def import_fixtures(
    club_id: UUID | None = None, queued_only: bool = False
) -> tuple[int, int, int]:
    created = updated = skipped = 0
    with SessionLocal.begin() as session:
        if queued_only:
            query = (
                select(Team, FixtureImportRun)
                .join(FixtureImportRun, FixtureImportRun.team_id == Team.team_id)
                .where(
                    FixtureImportRun.status == "queued",
                    or_(
                        FixtureImportRun.next_attempt_at.is_(None),
                        FixtureImportRun.next_attempt_at <= datetime.now(UTC),
                    ),
                )
                .with_for_update(skip_locked=True)
            )
            if club_id is not None:
                query = query.where(Team.club_id == club_id)
            team_runs = session.execute(query).all()
        else:
            query = select(Team).where(
                Team.external_provider == "fa_full_time", Team.external_id.is_not(None)
            )
            if club_id is not None:
                query = query.where(Team.club_id == club_id)
            team_runs = [(team, None) for team in session.scalars(query).all()]
        for team, run in team_runs:
            if run is None:
                run = FixtureImportRun(
                    club_id=team.club_id, team_id=team.team_id, status="running"
                )
                session.add(run)
                session.flush()
            else:
                run.status = "running"
                run.attempt_count += 1
            try:
                # The league-scoped page is the established Full-Time endpoint and
                # includes the competition/type column (including cups). Only use
                # the team-wide page when no league context was supplied.
                source_urls = [
                    current_season_url(
                        team.external_id,
                        team.external_league_id,
                    )
                ]
                parsed_by_id = {}
                fetch_errors = []
                source_html = None
                for source_url in source_urls:
                    try:
                        html = fetch_team_page(
                            source_url,
                            get_settings().fa_request_timeout_seconds,
                        )
                        source_html = source_html or html
                        parsed_by_id.update(
                            {item.external_id: item for item in parse_fixtures(html)}
                        )
                    except Exception as exc:
                        fetch_errors.append(exc)
                        logger.warning("Full-Time source unavailable: %s", source_url)
                if not parsed_by_id and fetch_errors:
                    raise fetch_errors[-1]
                parsed = list(parsed_by_id.values())
                standings = []
                if team.external_league_id:
                    try:
                        standings = parse_standings(
                            fetch_team_page(
                                current_table_url(team.external_league_id),
                                get_settings().fa_request_timeout_seconds,
                            )
                        )
                    except Exception as exc:
                        logger.warning("Full-Time standings unavailable: %s", exc)
                season_start = datetime(date.today().year, 7, 1, tzinfo=UTC)
                if date.today().month < 7:
                    season_start = season_start.replace(year=season_start.year - 1)
            except Exception as exc:
                logger.exception("Full-Time import failed for team %s", team.team_id)
                run.status = "queued" if run.attempt_count < 3 else "failed"
                run.error = str(exc)[:500]
                run.completed_at = None if run.status == "queued" else datetime.now(UTC)
                run.next_attempt_at = (
                    datetime.now(UTC) + timedelta(minutes=5 * run.attempt_count)
                    if run.status == "queued"
                    else None
                )
                skipped += 1
                continue
            team_created = team_updated = 0
            for item in parsed:
                opposition, is_home = _fixture_team_details(item, team)
                fixture = session.scalar(
                    select(Fixture).where(
                        Fixture.external_provider == "fa_full_time",
                        Fixture.external_id == item.external_id,
                    )
                )
                if fixture is None:
                    session.add(
                        Fixture(
                            club_id=team.club_id,
                            team_id=team.team_id,
                            title=item.title,
                            opposition=opposition,
                            is_home=is_home,
                            competition=item.competition,
                            starts_at=item.starts_at,
                            venue=item.venue,
                            home_score=item.home_score,
                            away_score=item.away_score,
                            external_provider="fa_full_time",
                            external_id=item.external_id,
                        )
                    )
                    created += 1
                    team_created += 1
                else:
                    fixture.team_id = team.team_id
                    fixture.title = item.title
                    fixture.opposition = opposition
                    fixture.is_home = is_home
                    fixture.competition = item.competition
                    fixture.starts_at = item.starts_at
                    fixture.venue = item.venue
                    fixture.home_score = item.home_score
                    fixture.away_score = item.away_score
                    updated += 1
                    team_updated += 1
            if standings:
                session.execute(
                    delete(LeagueStanding).where(LeagueStanding.team_id == team.team_id)
                )
                session.add_all(
                    LeagueStanding(
                        team_id=team.team_id,
                        position=item.position,
                        team_name=item.team_name,
                        played=item.played,
                        goal_difference=item.goal_difference,
                        points=item.points,
                    )
                    for item in standings
                )
            session.execute(
                delete(Fixture).where(
                    Fixture.team_id == team.team_id,
                    Fixture.external_provider == "fa_full_time",
                    Fixture.starts_at < season_start,
                )
            )
            run.status = "complete"
            run.created_count = team_created
            run.updated_count = team_updated
            run.completed_at = datetime.now(UTC)
            run.next_attempt_at = None
    return created, updated, skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queued", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    created, updated, skipped = import_fixtures(queued_only=args.queued)
    logger.info(
        "Full-Time fixtures: %s created, %s updated, %s teams skipped",
        created,
        updated,
        skipped,
    )


if __name__ == "__main__":
    main()
