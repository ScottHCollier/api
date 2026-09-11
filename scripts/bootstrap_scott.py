"""Clear the development database and create Scott's initial club workspace."""

from api.database import SessionLocal
from api.models import (
    Availability,
    Club,
    ClubDomain,
    ClubMembership,
    Fixture,
    FixtureImportRun,
    Player,
    PlayerGuardian,
    PlayerRegistration,
    RegistrationInvite,
    Season,
    Team,
    User,
)
from api.seed import seed_database


def main() -> None:
    with SessionLocal.begin() as session:
        for model in (
            Availability,
            RegistrationInvite,
            FixtureImportRun,
            PlayerRegistration,
            Season,
            Fixture,
            PlayerGuardian,
            Player,
            ClubMembership,
            Team,
            ClubDomain,
            User,
            Club,
        ):
            session.query(model).delete()

        seed_database(session)
    print("Reset complete: Scott Collier workspace created for Montpellier FC.")


if __name__ == "__main__":
    main()
