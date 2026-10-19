from app.db.base import Base


def test_sqlalchemy_base_is_available() -> None:
    assert set(Base.metadata.tables) >= {
        "users",
        "hospitals",
        "branches",
        "doctors",
        "patients",
    }
