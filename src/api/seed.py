"""Repeatable development seed for Scott's Montpellier FC workspace."""

import argparse
import hashlib
import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.config import get_settings
from api.database import SessionLocal
from api.models import Club, ClubDomain, ClubMembership, Payment, Player, Team, User

SCOTT_EMAIL = "scott@example.com"
SCOTT_PASSWORD = "password"


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return "pbkdf2_sha256$600000$" + salt.hex() + "$" + digest.hex()


def seed_database(session: Session) -> None:
    session.execute(
        insert(Club)
        .values(name="Montpellier FC", slug="montpellier-fc", badge_url="/badge.png")
        .on_conflict_do_nothing(index_elements=["slug"])
    )
    club = session.scalar(select(Club).where(Club.slug == "montpellier-fc"))
    assert club is not None
    session.execute(
        insert(ClubDomain)
        .values(hostname="montpellier-fc.localhost", club_id=club.club_id)
        .on_conflict_do_nothing(index_elements=["hostname"])
    )
    session.execute(
        insert(Team)
        .values(
            club_id=club.club_id,
            name="Men's First 11",
            external_provider="fa_full_time",
            external_id="963186578",
            external_league_id="516676",
            external_name="Montpellier",
            external_url="https://fulltime.thefa.com/displayTeam.html?teamID=963186578&league=516676",
        )
        .on_conflict_do_nothing(index_elements=["club_id", "name"])
    )
    session.execute(
        insert(User)
        .values(email=SCOTT_EMAIL, password_hash=password_hash(SCOTT_PASSWORD))
        .on_conflict_do_nothing(index_elements=["email"])
    )
    user = session.scalar(select(User).where(User.email == SCOTT_EMAIL))
    assert user is not None
    session.execute(
        insert(ClubMembership)
        .values(user_id=user.user_id, club_id=club.club_id, role="owner")
        .on_conflict_do_update(
            index_elements=["user_id", "club_id"], set_={"role": "owner"}
        )
    )

    team = session.scalar(
        select(Team).where(Team.club_id == club.club_id, Team.name == "Men's First 11")
    )
    assert team is not None
    seeded_players = [
        {
            "first": "Archie",
            "last": "Bennett",
            "position": "Goalkeeper",
            "dob": "2012-09-14",
            "guardian_name": "Hannah Bennett",
            "guardian_email": "hannah.bennett@example.com",
            "guardian_phone": "07700 900101",
            "fa_fan_id": "FT-FAN-1001",
            "auto_renew": True,
            "homegrown": True,
            "status": "complete",
            "notes": "Left-footed goalkeeper; confident receiving back passes.",
        },
        {
            "first": "Ben",
            "last": "Carter",
            "position": "Defender",
            "dob": "2013-02-22",
            "guardian_name": "Mark Carter",
            "guardian_email": "mark.carter@example.com",
            "guardian_phone": "07700 900102",
            "fa_fan_id": "FT-FAN-1002",
            "auto_renew": True,
            "homegrown": True,
            "status": "complete",
            "notes": "Centre-back who can also cover right back.",
        },
        {
            "first": "Charlie",
            "last": "Davies",
            "position": "Defender",
            "dob": "2012-11-03",
            "guardian_name": "Sophie Davies",
            "guardian_email": "sophie.davies@example.com",
            "guardian_phone": "07700 900103",
            "fa_fan_id": "FT-FAN-1003",
            "auto_renew": False,
            "homegrown": True,
            "status": "invited",
            "notes": "Registration invite sent; awaiting consent.",
        },
        {
            "first": "Ethan",
            "last": "Foster",
            "position": "Midfielder",
            "dob": "2013-06-18",
            "guardian_name": "Rachel Foster",
            "guardian_email": "rachel.foster@example.com",
            "guardian_phone": "07700 900104",
            "fa_fan_id": "FT-FAN-1004",
            "auto_renew": True,
            "homegrown": True,
            "status": "complete",
            "notes": "Box-to-box midfielder; monitor workload after school fixtures.",
        },
        {
            "first": "Freddie",
            "last": "Green",
            "position": "Midfielder",
            "dob": "2012-08-29",
            "email": "freddie.green@example.com",
            "phone": "07700 900105",
            "fa_fan_id": "FT-FAN-1005",
            "auto_renew": True,
            "homegrown": False,
            "status": "complete",
            "notes": "Player contact is used directly for availability reminders.",
        },
        {
            "first": "Noah",
            "last": "Hughes",
            "position": "Winger",
            "dob": "2013-04-11",
            "guardian_name": "Tom Hughes",
            "guardian_email": "tom.hughes@example.com",
            "guardian_phone": "07700 900106",
            "fa_fan_id": "FT-FAN-1006",
            "auto_renew": False,
            "homegrown": True,
            "status": "pending",
            "notes": "Needs registration documents before first competitive match.",
        },
        {
            "first": "Oscar",
            "last": "Lewis",
            "position": "Forward",
            "dob": "2012-12-07",
            "guardian_name": "Emma Lewis",
            "guardian_email": "emma.lewis@example.com",
            "guardian_phone": "07700 900107",
            "fa_fan_id": "FT-FAN-1007",
            "auto_renew": True,
            "homegrown": True,
            "status": "complete",
            "notes": "Striker; preferred position is central forward.",
        },
        {
            "first": "Theo",
            "last": "Morgan",
            "position": "Winger",
            "dob": "2013-10-25",
            "guardian_name": "James Morgan",
            "guardian_email": "james.morgan@example.com",
            "guardian_phone": "07700 900108",
            "fa_fan_id": "FT-FAN-1008",
            "auto_renew": False,
            "homegrown": True,
            "status": "invited",
            "notes": "Fast wide player; registration invite awaiting response.",
        },
    ]
    for item in seeded_players:
        exists = session.scalar(
            select(Player).where(
                Player.club_id == club.club_id,
                Player.legal_first_name == item["first"],
                Player.legal_last_name == item["last"],
            )
        )
        if exists is not None:
            continue
        session.add(
            Player(
                club_id=club.club_id,
                team_id=team.team_id,
                legal_first_name=item["first"],
                legal_last_name=item["last"],
                position=item["position"],
                date_of_birth=date.fromisoformat(item["dob"]),
                email=item.get("email"),
                phone=item.get("phone"),
                guardian_name=item.get("guardian_name"),
                guardian_email=item.get("guardian_email"),
                guardian_phone=item.get("guardian_phone"),
                fa_fan_id=item["fa_fan_id"],
                auto_renew_next_season=item["auto_renew"],
                homegrown_player=item["homegrown"],
                registration_status=item["status"],
                notes=item["notes"],
            )
        )
    session.flush()
    players = session.scalars(
        select(Player)
        .where(Player.club_id == club.club_id)
        .order_by(Player.legal_last_name)
    ).all()
    if not session.scalar(select(Payment).where(Payment.club_id == club.club_id)):
        session.add_all(
            [
                Payment(
                    club_id=club.club_id,
                    player_id=players[0].player_id,
                    description="September membership",
                    amount_pence=2500,
                    due_date=date(2026, 9, 15),
                ),
                Payment(
                    club_id=club.club_id,
                    player_id=players[1].player_id,
                    description="Season registration",
                    amount_pence=4000,
                    status="paid",
                    due_date=date(2026, 8, 31),
                ),
            ]
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--if-enabled", action="store_true")
    args = parser.parse_args()
    if args.if_enabled and not get_settings().seed_on_startup:
        print("Startup seeding disabled.")
        return
    with SessionLocal.begin() as session:
        seed_database(session)
    print("Montpellier FC and Scott owner workspace seeded.")


if __name__ == "__main__":
    main()
