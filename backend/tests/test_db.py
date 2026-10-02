"""Database init and seed."""

from sqlalchemy import func, select

from app.db import DEFAULT_CASH, DEFAULT_WATCHLIST, init_db, make_engine, users_profile, watchlist


def test_fresh_database_is_seeded(db_url):
    engine = make_engine(db_url)

    assert init_db(engine) is True
    with engine.connect() as conn:
        cash = conn.execute(select(users_profile.c.cash_balance)).scalar_one()
        tickers = set(conn.execute(select(watchlist.c.ticker)).scalars())

    assert cash == DEFAULT_CASH
    assert tickers == set(DEFAULT_WATCHLIST)


def test_init_is_idempotent(db_url):
    engine = make_engine(db_url)
    init_db(engine)

    assert init_db(engine) is False
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(watchlist)).scalar_one()
    assert count == len(DEFAULT_WATCHLIST)


def test_sqlite_parent_directory_is_created(tmp_path):
    path = tmp_path / "nested" / "dir" / "x.db"
    engine = make_engine(f"sqlite:///{path}")
    init_db(engine)

    assert path.exists()
