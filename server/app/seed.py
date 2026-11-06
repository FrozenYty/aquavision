"""Species dictionary seed (P1-01).

Four rows at launch, in labels.txt order — data model §3.6 makes that order a
contract: species_id 1..4 must read holothurian, strongylocentrotus, chlamys,
asterias, or every result is mislabelled. Categories follow SRS §3.5.1: the
first three are the economic species of the farm, the starfish is the pest that
preys on scallops.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SpeciesDict

SPECIES_SEED: tuple[dict[str, object], ...] = (
    {
        "class_code": "holothurian",
        "cn_name": "海参",
        "latin_name": "Apostichopus japonicus",
        "category": 1,  # economic
    },
    {
        "class_code": "strongylocentrotus",
        "cn_name": "海胆",
        "latin_name": "Strongylocentrotus intermedius",
        "category": 1,  # economic
    },
    {
        "class_code": "chlamys",
        "cn_name": "扇贝",
        "latin_name": "Chlamys farreri",
        "category": 1,  # economic
    },
    {
        "class_code": "asterias",
        "cn_name": "海星",
        "latin_name": "Asterias amurensis",
        "category": 2,  # pest
        "remark": "扇贝养殖的主要敌害，密度异常时需人工清除。",
    },
)


def seed_species(session: Session) -> int:
    """Insert the seed rows that are missing; return how many were inserted.

    Idempotent: existing class_code rows are left untouched, so re-running the
    script on a live database never duplicates or overwrites a curated
    dictionary.
    """
    present = set(session.scalars(select(SpeciesDict.class_code)))
    inserted = 0
    for row in SPECIES_SEED:
        if row["class_code"] in present:
            continue
        session.add(SpeciesDict(**row))  # type: ignore[arg-type]
        inserted += 1
    session.commit()
    return inserted
