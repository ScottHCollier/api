from datetime import datetime

from api.fa_full_time import (
    current_season_url,
    current_table_url,
    parse_fixtures,
    parse_standings,
    parse_upcoming_fixtures,
)


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
