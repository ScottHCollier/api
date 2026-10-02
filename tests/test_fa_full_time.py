from datetime import datetime
from types import SimpleNamespace

from api.fa_full_time import (
    FullTimeFixture,
    current_season_url,
    current_table_url,
    parse_fixtures,
    parse_standings,
    parse_upcoming_fixtures,
)
from api.import_fixtures import _fixture_team_details, _resolve_source_team_name


def test_current_season_url_uses_stable_team_identity():
    assert current_season_url("963186578", "516676") == (
        "https://fulltime.thefa.com/displayTeam.html?teamID=963186578&league=516676"
    )


def test_current_table_url_uses_league_identity():
    assert current_table_url("516676") == (
        "https://fulltime.thefa.com/index.html?league=516676"
    )


def test_parse_upcoming_full_time_rows():
    html = """
    <table>
      <tr>
        <th>Type</th><th>Date / Time</th><th>Home Team</th><th></th>
        <th>Away Team</th><th>Venue</th>
      </tr>
      <tr>
        <td>MFLP</td><td>12/09/26 15:00</td><td>Montpellier First</td>
        <td>VS</td><td>Meadow Athletic</td>
        <td>Riverside Recreation Ground</td>
      </tr>
      <tr>
        <td>Results</td><td>01/09/26 15:00</td><td>Old Team</td>
        <td>1 - 0</td><td>Montpellier First</td>
      </tr>
    </table>
    """
    fixtures = parse_upcoming_fixtures(html)
    assert len(fixtures) == 1
    assert fixtures[0].title == "Montpellier First vs. Meadow Athletic"
    assert fixtures[0].venue == "Riverside Recreation Ground"
    assert fixtures[0].home_score is None
    assert fixtures[0].starts_at == datetime.fromisoformat("2026-09-12T15:00:00+01:00")
    assert len(fixtures[0].external_id) == 32


def test_parser_ignores_empty_upcoming_fixture_table():
    assert (
        parse_upcoming_fixtures("<p>There are currently no fixtures to show</p>") == []
    )


def test_parser_includes_past_results():
    html = """
    <table><tr><td>L</td><td>01/09/26 15:00</td><td>Montpellier First</td>
    <td>2 - 1</td><td>Old Athletic</td></tr></table>
    """
    fixtures = parse_fixtures(html)
    assert len(fixtures) == 1
    assert fixtures[0].title == "Montpellier First vs. Old Athletic"
    assert fixtures[0].venue == "TBC"
    assert fixtures[0].home_score == 2
    assert fixtures[0].away_score == 1
    assert parse_upcoming_fixtures(html) == []


def test_parser_accepts_compact_score_cells():
    html = """
    <table><tr><td>L</td><td>01/09/26 15:00</td><td>Montpellier First</td>
    <td>2–1</td><td>Old Athletic</td></tr></table>
    """
    fixtures = parse_fixtures(html)
    assert len(fixtures) == 1
    assert fixtures[0].home_score == 2
    assert fixtures[0].away_score == 1


def test_parser_reads_full_time_standings():
    html = """
    <table><tr><th>Pos</th><th>Teams</th><th>P</th><th>W</th><th>D</th>
    <th>L</th><th>F</th><th>A</th><th>GD</th><th>Pts</th></tr>
    <tr><td>1</td><td>Montpellier First</td><td>5</td><td>4</td><td>1</td>
    <td>0</td><td>12</td><td>4</td><td>8</td><td>13</td></tr></table>
    """
    standings = parse_standings(html)
    assert standings[0].team_name == "Montpellier First"
    assert standings[0].played == 5
    assert standings[0].goal_difference == 8
    assert standings[0].points == 13


def test_import_repairs_stale_provider_name_from_fixture_frequency():
    items = [
        FullTimeFixture("1", "Prem", "Montpellier (Cheltenham) 1st vs. Bibury First", "Montpellier (Cheltenham) 1st", "Bibury First", datetime.now(), "TBC", 1, 0),
        FullTimeFixture("2", "Prem", "Shurdington Rovers 1st vs. Montpellier (Cheltenham) 1st", "Shurdington Rovers 1st", "Montpellier (Cheltenham) 1st", datetime.now(), "TBC", 0, 2),
        FullTimeFixture("3", "Prem", "FC Wickhamford Firsts vs. Montpellier (Cheltenham) 1st", "FC Wickhamford Firsts", "Montpellier (Cheltenham) 1st", datetime.now(), "TBC", 0, 2),
    ]
    team = SimpleNamespace(name="Men's Firsts", external_name="FC Wickhamford Firsts")

    source_name = _resolve_source_team_name(items, team)

    assert source_name == "Montpellier (Cheltenham) 1st"
    assert _fixture_team_details(items[0], source_name) == ("Bibury First", True)
    assert _fixture_team_details(items[1], source_name) == ("Shurdington Rovers 1st", False)
