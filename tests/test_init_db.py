"""Schema creation and species seeding (P1-01).

The tests run against a SQLite file under tests/tmp (the conftest replacement
for tmp_path): the DDL is plain SQLAlchemy and behaves identically on SQLite
and PostgreSQL, while keeping CI free of a database server. The script itself
is also run as a subprocess, because PLAN.md words the acceptance as
"scripts/init_db.py runs" — not "the functions under it".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from app.db import Base
from app.models import EXPECTED_COLUMNS, TABLES, ModelVersion, SpeciesDict
from app.seed import SPECIES_SEED, seed_species
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """An engine on a fresh SQLite file; the schema is created per test."""
    eng = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def species_rows(eng: Engine) -> list[SpeciesDict]:
    """All seed rows, in species_id order — the order the contract speaks about."""
    with Session(eng) as session:
        return list(session.scalars(select(SpeciesDict).order_by(SpeciesDict.species_id)))


def test_all_fourteen_tables_exist(engine: Engine):
    """The dictionary counts fourteen tables; the schema must agree, column by column."""
    inspector = inspect(engine)
    names = set(inspector.get_table_names())
    expected = {table.__tablename__ for table in TABLES}
    assert names == expected == set(EXPECTED_COLUMNS)

    for table, count in EXPECTED_COLUMNS.items():
        assert len(inspector.get_columns(table)) == count, f"{table} drifted from the dictionary"


def test_seed_inserts_four_classes_in_labels_order(engine: Engine):
    """PLAN P1-01: four classes seeded; the order must match labels.txt (a contract)."""
    with Session(engine) as session:
        inserted = seed_species(session)

    assert inserted == 4
    rows = species_rows(engine)
    assert [row.class_code for row in rows] == [str(r["class_code"]) for r in SPECIES_SEED]
    assert [row.cn_name for row in rows] == ["海参", "海胆", "扇贝", "海星"]


def test_seed_is_idempotent(engine: Engine):
    """Re-running on a live database adds nothing and overwrites nothing."""
    with Session(engine) as session:
        first = seed_species(session)
        second = seed_species(session)

    assert (first, second, len(species_rows(engine))) == (4, 0, 4)


def test_categories_follow_the_srs(engine: Engine):
    """Three economic species, one pest — the split SRS §3.5.1 builds on."""
    with Session(engine) as session:
        seed_species(session)
    by_code = {row.class_code: row.category for row in species_rows(engine)}
    assert by_code == {
        "holothurian": 1,
        "strongylocentrotus": 1,
        "chlamys": 1,
        "asterias": 2,
    }


def test_script_runs_on_an_empty_database(tmp_path: Path):
    """The acceptance test, word for word: the script runs and four classes are seeded."""
    db = tmp_path / "empty.db"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "init_db.py"), "--dsn", f"sqlite:///{db}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK: fourteen tables, four classes" in result.stdout

    eng = create_engine(f"sqlite:///{db}")
    try:
        assert len(inspect(eng).get_table_names()) == len(EXPECTED_COLUMNS)
        assert len(species_rows(eng)) == 4
    finally:
        eng.dispose()


def test_script_creates_the_missing_database_directory(tmp_path: Path):
    """A clone has no data/ (git-ignored); the documented command must still create its database."""
    db = tmp_path / "missing-parent" / "app.db"
    assert not db.parent.exists()

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "init_db.py"), "--dsn", f"sqlite:///{db}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert db.is_file()

    eng = create_engine(f"sqlite:///{db}")
    try:
        with Session(eng) as session:
            online = list(session.scalars(select(ModelVersion).where(ModelVersion.is_online == 1)))
    finally:
        eng.dispose()
    assert len(online) == 1, "the delivered model version must be registered as the online one"


def test_the_hard_sample_pool_index_is_part_of_the_schema(engine: Engine):
    """AC-34 measured the pool at 357 s per request without this covering index."""
    indexes = {index["name"] for index in inspect(engine).get_indexes("detect_object")}
    assert "ix_detect_object_hard_pool" in indexes, sorted(indexes)


def test_init_db_adds_a_missing_index_to_an_existing_database(tmp_path: Path):
    """A database created before the index was declared gets it from the deployment command."""
    db = tmp_path / "existing.db"
    dsn = f"sqlite:///{db}"
    command = [sys.executable, str(ROOT / "scripts" / "init_db.py"), "--dsn", dsn]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr

    engine = create_engine(dsn)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP INDEX ix_detect_object_hard_pool")
        assert "ix_detect_object_hard_pool" not in {
            index["name"] for index in inspect(engine).get_indexes("detect_object")
        }
    finally:
        engine.dispose()

    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode == 0, second.stderr
    assert "ix_detect_object_hard_pool" in second.stdout, second.stdout

    engine = create_engine(dsn)
    try:
        names = {index["name"] for index in inspect(engine).get_indexes("detect_object")}
    finally:
        engine.dispose()
    assert "ix_detect_object_hard_pool" in names, sorted(names)
