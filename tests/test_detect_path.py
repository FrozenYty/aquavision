"""ADR 13's anchor: a relative `weight_path` means the repository root, not the process CWD (A4).

`load_online` used to resolve a relative weight against `Path.cwd()`, so the same registration loaded
from the repository root and failed from `server/` or from a service manager with another working
directory. This test loads the same row from two different working directories and demands one answer.
A fake `Detector` keeps it free of torch and of a real weight file.
"""

from __future__ import annotations

from pathlib import Path

from app import detector
from app.config import Settings
from app.db import PROJECT_ROOT, Base, engine_from_dsn
from app.models import ModelVersion
from app.seed import SPECIES_SEED, seed_species
from sqlalchemy.orm import sessionmaker


class _RecordingDetector:
    """Stands in for the real detector: records the path it was given, imports nothing heavy."""

    seen: list[Path] = []

    def __init__(
        self,
        weights: str | Path,
        *,
        model_version_id: int,
        version_name: str,
        data_dir: Path,
        device: str | None = None,
        imgsz: int = 640,
    ) -> None:
        self.weights = Path(weights)
        self.model_version_id = model_version_id
        self.version_name = version_name
        _RecordingDetector.seen.append(self.weights)

    @property
    def class_names(self) -> list[str]:
        return [str(row["class_code"]) for row in SPECIES_SEED]


def _online_model(tmp_path) -> tuple[sessionmaker, Settings]:
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'detect.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        seed_species(session)
        session.add(
            ModelVersion(
                version_name="anchor-check",
                # A file that already exists at the repository root. The fake detector never reads it;
                # the loader only checks that the relative path lands on a file that is really there.
                weight_path="README.md",
                labels_path="labels.txt",
                status=1,
                is_online=1,
            )
        )
        session.commit()
    return factory, Settings(data_dir=str(tmp_path / "data"))


def test_a_relative_weight_path_resolves_against_the_repository_root(tmp_path, monkeypatch):
    factory, settings = _online_model(tmp_path)
    monkeypatch.setattr(detector, "Detector", _RecordingDetector)
    _RecordingDetector.seen = []

    # A file of that name inside the working directory must not be the one chosen: the anchor is the
    # repository root. If it were the CWD, the second directory (without the file) would fail to load.
    first = tmp_path / "first-working-directory"
    first.mkdir()
    (first / "README.md").write_text("not a weight file", encoding="utf-8")
    second = tmp_path / "second-working-directory"
    second.mkdir()

    resolved = []
    for cwd in (first, second):
        monkeypatch.chdir(cwd)
        found, reason = detector.load_online(factory, settings)
        assert found is not None, f"load_online failed from the working directory {cwd}: {reason}"
        resolved.append(found.weights)

    expected = PROJECT_ROOT / "README.md"
    assert resolved == [expected, expected]
