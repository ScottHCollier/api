from unittest.mock import Mock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from api.database import get_session
from api.main import _document_content_matches, app


def test_liveness_without_database():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_document_content_validation_rejects_mismatched_types():
    assert _document_content_matches("application/pdf", b"%PDF-1.7")
    assert not _document_content_matches("application/pdf", b"not a pdf")
    assert _document_content_matches("image/png", b"\x89PNG\r\n\x1a\nrest")
    assert not _document_content_matches("image/png", b"\xff\xd8\xffjpeg")


def test_register_login_and_current_user(client):
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": "  Alice@Example.COM ", "password": "correct horse battery"},
    )
    assert registration.status_code == 201
    payload = registration.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == "alice@example.com"
    assert "password" not in payload["user"]
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        ).json()["user_id"]
        == payload["user"]["user_id"]
    )

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ALICE@example.com", "password": "correct horse battery"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["user_id"] == payload["user"]["user_id"]


def test_seeded_user_includes_club_memberships(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "scott@example.com",
            "password": "password",
        },
    )
    assert response.status_code == 200
    memberships = response.json()["user"]["memberships"]
    assert {
        (membership["club_slug"], membership["role"]) for membership in memberships
    } == {
        ("montpellier-fc", "owner"),
    }


def test_auth_rejects_duplicates_bad_passwords_and_bad_tokens(client):
    body = {"email": "member@example.com", "password": "a secure password"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code == 409
    assert (
        client.post(
            "/api/v1/auth/login",
            json={**body, "password": "wrong password"},
        ).status_code
        == 401
    )
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.token"}
        ).status_code
        == 401
    )


def test_auth_validates_password_length(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_readiness(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_failure_is_sanitized():
    session = Mock()
    session.execute.side_effect = OperationalError("secret SQL", {}, Exception())
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
    finally:
        app.dependency_overrides.clear()


def test_resolve_registered_domain(client):
    response = client.get(
        "/api/v1/public/clubs/resolve",
        params={"hostname": "MONTPELLIER-FC.LOCALHOST."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert UUID(payload["club_id"]).version == 4
    assert payload == {
        "club_id": payload["club_id"],
        "name": "Montpellier FC",
        "slug": "montpellier-fc",
        "badge_url": "/badge.png",
    }


def test_unknown_domain_does_not_fall_back_to_slug(client):
    response = client.get(
        "/api/v1/public/clubs/resolve",
        params={"hostname": "montpellier-fc.example.com"},
    )
    assert response.status_code == 404


def test_teams_are_scoped_to_club(client):
    club_id = client.get(
        "/api/v1/public/clubs/resolve", params={"hostname": "montpellier-fc.localhost"}
    ).json()["club_id"]
    response = client.get(f"/api/v1/public/clubs/{club_id}/teams")
    assert response.status_code == 200
    teams = response.json()
    assert len(teams) == 1
    assert {team["club_id"] for team in teams} == {club_id}
    assert all(UUID(team["team_id"]).version == 4 for team in teams)
    assert set(teams[0]) == {
        "team_id",
        "club_id",
        "name",
        "description",
        "external_provider",
        "external_id",
        "external_league_id",
        "external_name",
        "external_url",
    }
    montpellier_id = club_id
    linked = next(
        team
        for team in client.get(f"/api/v1/public/clubs/{montpellier_id}/teams").json()
        if team["name"] == "Men's First 11"
    )
    assert linked["external_provider"] == "fa_full_time"
    assert linked["external_id"] == "963186578"
    assert linked["external_league_id"] == "516676"
    assert client.get(f"/api/v1/public/clubs/{uuid4()}/teams").status_code == 404


def test_team_lookup_rejects_non_uuid_club_id(client):
    assert client.get("/api/v1/public/clubs/montpellier-fc/teams").status_code == 422


def test_player_visibility_is_limited_by_role_and_guardianship(client):
    club_id = client.get(
        "/api/v1/public/clubs/resolve", params={"hostname": "montpellier-fc.localhost"}
    ).json()["club_id"]

    def token(email, password):
        return client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        ).json()["access_token"]

    owner = token("scott@example.com", "password")
    parent = owner
    owner_response = client.get(
        f"/api/v1/clubs/{club_id}/players",
        headers={"Authorization": f"Bearer {owner}"},
    )
    parent_response = client.get(
        f"/api/v1/clubs/{club_id}/players",
        headers={"Authorization": f"Bearer {parent}"},
    )
    assert owner_response.status_code == parent_response.status_code == 200
    assert len(owner_response.json()) == 8
    assert len(parent_response.json()) == 8


def test_player_list_requires_membership(client):
    club_id = client.get(
        "/api/v1/public/clubs/resolve", params={"hostname": "montpellier-fc.localhost"}
    ).json()["club_id"]
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": "unaffiliated@example.com", "password": "a secure password"},
    )
    response = client.get(
        f"/api/v1/clubs/{club_id}/players",
        headers={"Authorization": f"Bearer {registration.json()['access_token']}"},
    )
    assert response.status_code == 403


def test_fixture_creation_and_parent_availability_scope(client):
    club_id = client.get(
        "/api/v1/public/clubs/resolve", params={"hostname": "montpellier-fc.localhost"}
    ).json()["club_id"]

    def token(email, password):
        return client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        ).json()["access_token"]

    owner = token("scott@example.com", "password")
    fixtures = client.get(
        f"/api/v1/clubs/{club_id}/fixtures",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert fixtures.status_code == 200
    assert fixtures.json() == []


def test_articles_are_role_protected_and_public_workflow_is_scoped(client):
    club_id = client.get(
        "/api/v1/public/clubs/resolve", params={"hostname": "montpellier-fc.localhost"}
    ).json()["club_id"]
    token = client.post(
        "/api/v1/auth/login", json={"email": "scott@example.com", "password": "password"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    draft = client.post(
        f"/api/v1/clubs/{club_id}/articles",
        headers=headers,
        json={"title": "Private draft", "body": "Not public yet", "status": "draft"},
    )
    assert draft.status_code == 201
    assert client.get(f"/api/v1/public/clubs/{club_id}/articles").json() == []
    published = client.post(
        f"/api/v1/clubs/{club_id}/articles",
        headers=headers,
        json={"title": "Published story", "body": "Club news", "status": "published"},
    )
    assert published.status_code == 201
    public = client.get(f"/api/v1/public/clubs/{club_id}/articles")
    assert public.status_code == 200
    assert [item["title"] for item in public.json()] == ["Published story"]
    updated = client.patch(
        f"/api/v1/clubs/{club_id}/articles/{published.json()['article_id']}",
        headers=headers,
        json={"title": "Updated story", "body": "Updated body", "status": "published"},
    )
    assert updated.status_code == 200
    assert client.get(f"/api/v1/public/clubs/{club_id}/articles").json()[0]["title"] == "Updated story"


def test_public_contact_and_team_introduction_updates_require_admin(client):
    club_id = client.get(
        "/api/v1/public/clubs/resolve", params={"hostname": "montpellier-fc.localhost"}
    ).json()["club_id"]
    token = client.post(
        "/api/v1/auth/login", json={"email": "scott@example.com", "password": "password"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    contact = client.patch(
        f"/api/v1/clubs/{club_id}/contact", headers=headers,
        json={"email": "hello@example.com", "phone": "01234", "address": "Club Road"},
    )
    assert contact.status_code == 200
    assert client.get(f"/api/v1/public/clubs/{club_id}/contact").json() == {
        "contact_email": "hello@example.com", "contact_phone": "01234", "contact_address": "Club Road", "contact_description": None, "instagram_url": None, "facebook_url": None
    }
    team = client.get(f"/api/v1/public/clubs/{club_id}/teams").json()[0]
    updated = client.put(
        f"/api/v1/clubs/{club_id}/teams/{team['team_id']}", headers=headers,
        json={"name": team["name"], "description": "A team introduction."},
    )
    assert updated.status_code == 200
    assert client.get(f"/api/v1/public/clubs/{club_id}/teams").json()[0]["description"] == "A team introduction."


def test_openapi_declares_uuid_identifiers():
    schema = app.openapi()
    for model, fields in (
        ("ClubRead", ["club_id"]),
        ("TeamRead", ["team_id", "club_id"]),
    ):
        properties = schema["components"]["schemas"][model]["properties"]
        assert "id" not in properties
        assert all(properties[field]["format"] == "uuid" for field in fields)
    parameter = schema["paths"]["/api/v1/public/clubs/{club_id}/teams"]["get"][
        "parameters"
    ][0]
    assert parameter["schema"]["format"] == "uuid"


def test_cors_allows_only_configured_origins():
    with TestClient(app) as client:
        allowed = client.get(
            "/health", headers={"Origin": "http://montpellier-fc.localhost:3000"}
        )
        denied = client.get("/health", headers={"Origin": "https://unknown.example"})
    assert allowed.headers["access-control-allow-origin"] == (
        "http://montpellier-fc.localhost:3000"
    )
    assert "access-control-allow-origin" not in denied.headers
