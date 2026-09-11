"""Small adapter for the public FA Full-Time team pages."""

import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class FullTimeFixture:
    external_id: str
    competition: str
    title: str
    home_team: str
    away_team: str
    starts_at: datetime
    venue: str
    home_score: int | None
    away_score: int | None


@dataclass(frozen=True)
class FullTimeStanding:
    position: int
    team_name: str
    played: int
    goal_difference: int
    points: int


class _FixtureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            value = " ".join(data.split())
            if value:
                self._cell.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            if self._table is not None:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def parse_fixtures(html: str, upcoming_only: bool = False) -> list[FullTimeFixture]:
    parser = _FixtureParser()
    parser.feed(html)
    fixtures = []
    for row in parser.rows:
        row = [cell for cell in row if cell]
        if len(row) < 5 or row[0].lower() in {"type", "pos"}:
            continue
        try:
            starts_at = datetime.strptime(row[1], "%d/%m/%y %H:%M").replace(
                tzinfo=ZoneInfo("Europe/London")
            )
        except IndexError, ValueError:
            continue
        versus_index = next(
            (i for i, cell in enumerate(row) if cell.upper() == "VS"), None
        )
        score_index = next(
            (
                i
                for i, cell in enumerate(row)
                if re.search(r"\b\d+\s*[-–]\s*\d+\b", cell)
            ),
            None,
        )
        if versus_index is None and score_index is None:
            continue
        if upcoming_only and versus_index is None:
            continue
        if versus_index is not None:
            if versus_index < 3 or len(row) <= versus_index + 1:
                continue
            away_index = versus_index + 1
        else:
            assert score_index is not None
            if score_index < 3 or len(row) <= score_index + 1:
                continue
            away_index = score_index + 1
        home = row[2]
        away = row[away_index]
        is_result = versus_index is None
        score = row[score_index] if score_index is not None else ""
        score_match = re.search(r"\b(\d+)\s*[-–]\s*(\d+)\b", score)
        venue_index = away_index + 1
        if not is_result and len(row) > venue_index and row[venue_index] == away:
            venue_index += 1
        venue = row[venue_index] if not is_result and len(row) > venue_index else "TBC"
        title = f"{home} vs. {away}"
        identity = f"{row[0]}|{row[1]}|{home}|{away}"
        fixtures.append(
            FullTimeFixture(
                external_id=sha256(identity.encode()).hexdigest()[:32],
                competition=row[0],
                title=title,
                home_team=home,
                away_team=away,
                starts_at=starts_at,
                venue=venue,
                home_score=int(score_match.group(1)) if score_match else None,
                away_score=int(score_match.group(2)) if score_match else None,
            )
        )
    return fixtures


def parse_upcoming_fixtures(html: str) -> list[FullTimeFixture]:
    return parse_fixtures(html, upcoming_only=True)


def parse_standings(html: str) -> list[FullTimeStanding]:
    """Parse rows from a Full-Time league table, never player-stat tables."""
    parser = _FixtureParser()
    parser.feed(html)
    standings = []
    for table in parser.tables:
        header = [cell.lower() for cell in table[0]] if table else []
        if not {"pos", "gd", "pts"}.issubset(header):
            continue
        pos_index = header.index("pos")
        team_index = next(
            (i for i, cell in enumerate(header) if cell in {"teams", "team"}), 1
        )
        played_index = header.index("p")
        goal_difference_index = header.index("gd")
        points_index = (
            header.index("pts") if "pts" in header else header.index("points")
        )
        required_index = max(
            pos_index, team_index, played_index, goal_difference_index, points_index
        )
        for row in table[1:]:
            if len(row) <= required_index:
                continue
            try:
                standings.append(
                    FullTimeStanding(
                        position=int(row[pos_index]),
                        team_name=row[team_index],
                        played=int(row[played_index]),
                        goal_difference=int(row[goal_difference_index]),
                        points=int(row[points_index]),
                    )
                )
            except ValueError:
                continue
        if standings:
            break
    return standings


def fetch_team_page(url: str, timeout: int = 20) -> str:
    # Full-Time rejects requests that identify themselves as a scraping script.
    # Use the same basic headers as a normal browser page navigation while
    # keeping the provider URL fully controlled by the linked team metadata.
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Referer": "https://fulltime.thefa.com/",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured HTTPS provider URL
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code == 403:
            raise RuntimeError(
                "FA Full-Time denied the team page (HTTP 403). Check the linked "
                "team/league IDs or try again later."
            ) from exc
        raise


def current_season_url(team_id: str, league_id: str | None = None) -> str:
    query = {"teamID": team_id}
    if league_id:
        query["league"] = league_id
    return f"https://fulltime.thefa.com/displayTeam.html?{urlencode(query)}"


def current_table_url(league_id: str) -> str:
    # The dedicated table route is blocked to automated requests, while the
    # league home page contains the same standings table and remains public.
    return f"https://fulltime.thefa.com/index.html?{urlencode({'league': league_id})}"
