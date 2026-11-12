"""The permission matrix, negatively tested (P3-11, FR-M1-02, AC-02).

Every (role, method, path) pair the documents decide is in `MATRIX` below, and both directions are
asserted: a role the documents refuse gets 403 with the project envelope, and a role they allow does
**not** get 403 — a guard that refused everything would pass a one-directional test.

Where the expectations come from, and nothing else:

- **SRS Table 2-1** gives each role's profile. The collector "controls capture, creates and views their
  own detection jobs and results; cannot change models or system parameters". The analyst "views all
  jobs and results; may review, correct, export and generate reports; maintains the species dictionary
  and sample library". The algorithm engineer has "full access to the annotation bench, dataset
  management, training jobs and model management; registers and activates model versions". The
  administrator holds "all management permissions plus audit log access".
- **SRS FR-M1-02** adds the boundary rule — "algorithm and configuration endpoints are restricted to
  the algorithm engineer and administrator" — and its acceptance names one pair outright: a collector
  calling model activation receives 403.
- **The contract** states three of them in words: a review submission and its rollback are open to
  `analyst`, `algo` and `admin`; demo reset is "administrator only"; the audit log is the
  administrator's.

The rule applied to the routes those sentences do not mention by name: the role responsible for the
part of the system the route acts on is decided by Table 2-1's profiles, so the engineer's and the
analyst's endpoints are theirs, and the administrator is never excluded. Reading is open to every
signed-in role, because Table 2-1 gives the collector their own results and `FR-M4-02` the timeline -
the audit log aside, which is the administrator's.

The code's guards were read afterwards, not used to write this table. That is the whole point: a table
generated from `require(...)` would only prove the code equals itself.
"""

from __future__ import annotations

import re

import pytest
from app.config import get_settings
from app.db import Base, engine_from_dsn
from app.envelope import FORBIDDEN, NOT_IMPLEMENTED
from app.models import SysLog, SysUser
from app.security import hash_password
from app.seed import seed_species
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

ROLES = ("observer", "analyst", "algo", "admin")

#: Every signed-in role.
ALL_ROLES = ROLES
#: Routes only the administrator may call: account management (FR-M1-03) and the audit log (Table 2-1).
ADMINISTRATOR = ("admin",)
#: Table 2-1: the engineer registers and activates models, and FR-M1-02 restricts algorithm and
#: configuration endpoints to the engineer and the administrator.
ALGORITHM = ("algo", "admin")
#: Table 2-1: the analyst produces the reports.
REPORTS = ("analyst", "admin")
#: Table 2-1's sample library (the analyst) and dataset management (the engineer); the contract gives a
#: review submission and its rollback to analyst, algo and admin.
SAMPLES = ("analyst", "algo", "admin")

#: (method, path, roles the documents allow). Every role **not** listed must receive 403.
#: Path parameters are replaced with values that exist, or with `missing` where the handler's own 404
#: is the expected non-403 answer.
MATRIX: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # --- Table 2-1: reading is open to every signed-in role -------------------------------------
    ("GET", "/api/auth/me", ALL_ROLES),
    ("GET", "/api/cameras", ALL_ROLES),
    ("GET", "/api/capture/sessions", ALL_ROLES),
    ("POST", "/api/capture/sessions", ALL_ROLES),
    ("POST", "/api/capture/sessions/{session_id}/close", ALL_ROLES),
    ("POST", "/api/capture/sessions/{session_id}/frames", ALL_ROLES),
    ("POST", "/api/compare/frames/{frame_id}", ALL_ROLES),
    ("GET", "/api/datasets", ALL_ROLES),
    ("POST", "/api/detect/batches", ALL_ROLES),
    ("POST", "/api/detect/frames/{frame_id}", ALL_ROLES),
    ("GET", "/api/experiments", ALL_ROLES),
    ("GET", "/api/frames", ALL_ROLES),
    ("GET", "/api/frames/{frame_id}", ALL_ROLES),
    ("GET", "/api/frames/{frame_id}/objects", ALL_ROLES),
    ("GET", "/api/hard-samples", ALL_ROLES),
    ("GET", "/api/messages", ALL_ROLES),
    ("POST", "/api/messages/{msg_id}/read", ALL_ROLES),
    ("GET", "/api/models", ALL_ROLES),
    ("GET", "/api/monitor", ALL_ROLES),
    ("GET", "/api/params", ALL_ROLES),
    ("GET", "/api/reports", ALL_ROLES),
    ("GET", "/api/review/frames/{frame_id}/versions", ALL_ROLES),
    ("GET", "/api/species", ALL_ROLES),
    ("GET", "/api/stats/corrections", ALL_ROLES),
    ("GET", "/api/stats/quality", ALL_ROLES),
    ("GET", "/api/stats/species", ALL_ROLES),
    ("GET", "/api/stats/trend", ALL_ROLES),
    ("GET", "/api/tasks", ALL_ROLES),
    ("GET", "/api/tasks/{task_id}", ALL_ROLES),
    # The collector's own job: FR-M3-02 gives the operator progress, cancel and retry.
    ("POST", "/api/tasks/{task_id}/cancel", ALL_ROLES),
    ("POST", "/api/tasks/{task_id}/retry", ALL_ROLES),
    # --- Table 2-1: the engineer's and the analyst's endpoints ------------------------------------
    ("POST", "/api/models/{model_id}/activate", ALGORITHM),
    ("PATCH", "/api/params", ALGORITHM),
    ("POST", "/api/datasets", SAMPLES),
    ("PATCH", "/api/species/{class_code}", SAMPLES),
    ("DELETE", "/api/hard-samples/{frame_id}", SAMPLES),
    ("POST", "/api/review/frames/{frame_id}", SAMPLES),
    ("POST", "/api/review/frames/{frame_id}/rollback", SAMPLES),
    ("POST", "/api/reports", REPORTS),
    # --- Table 2-1 and FR-M1-03: the administrator alone ------------------------------------------
    ("GET", "/api/users", ADMINISTRATOR),
    ("POST", "/api/users", ADMINISTRATOR),
    ("POST", "/api/users/{user_id}/status", ADMINISTRATOR),
    ("POST", "/api/users/{user_id}/reset-password", ADMINISTRATOR),
    ("GET", "/api/logs", ADMINISTRATOR),
    # The contract: "administrator only"; with demo mode on, the role decides, not the feature gate.
    ("POST", "/api/demo/reset", ADMINISTRATOR),
)

#: Routes that are not behind the role matrix at all: they are the only two without a token.
EXEMPT = {("POST", "/api/auth/login"), ("GET", "/api/health")}

#: The envelope code a refusal carries.
FORBIDDEN_CODE = FORBIDDEN


@pytest.fixture
def client(tmp_path, monkeypatch):
    """An app with one account per role, demo mode on, and no background worker."""
    monkeypatch.setenv("DB_DSN", f"sqlite:///{(tmp_path / 'matrix.db').as_posix()}")
    monkeypatch.setenv("AV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AV_WORKER_ENABLED", "0")
    # Demo reset is "administrator only" per the contract, but answers 404 while the feature is off;
    # with it on, every role reaches the guard and the pair is decided by the role.
    monkeypatch.setenv("AV_DEMO_ENABLED", "1")
    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    engine = engine_from_dsn(f"sqlite:///{(tmp_path / 'matrix.db').as_posix()}")
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    with app.state.session_factory() as session:
        seed_species(session)
        for role in ROLES:
            hashed, salt = hash_password("password123")
            session.add(
                SysUser(
                    username=role,
                    password_hash=hashed,
                    salt=salt,
                    role_code=role,
                    real_name=role,
                    status=1,
                    fail_count=0,
                )
            )
        session.commit()

    # The capture routes accept only the local machine (FR-M1-02, P3-20), so this client says
    # where it is instead of relying on the test runner's default address.
    with TestClient(app, client=("127.0.0.1", 50000)) as test_client:
        yield test_client
    get_settings.cache_clear()


def sign_in(client: TestClient, role: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": role, "password": "password123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


#: What a path parameter becomes in an actual request. `missing` asks the handler for its own 404,
#: which is the expected non-403 answer on the allowed side.
FILLERS = {
    "session_id": "s-1",
    "class_code": "holothurian",
    "frame_id": "missing",
}


def concrete(path: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda match: FILLERS.get(match.group(1), "1"), path)


def call(client: TestClient, headers: dict[str, str], method: str, path: str):
    return client.request(method, concrete(path), json={}, headers=headers)


def test_the_matrix_is_honoured_in_both_directions(client):
    """Refused pairs answer 403 with the envelope; allowed pairs answer anything but 401 or 403."""
    tokens = {role: sign_in(client, role) for role in ROLES}
    problems: list[str] = []

    for method, path, allowed in MATRIX:
        for role in ROLES:
            response = call(client, tokens[role], method, path)
            if role in allowed:
                if response.status_code in (401, 403):
                    problems.append(
                        f"{role} was refused {method} {path}: {response.status_code} {response.text}"
                    )
                elif response.status_code >= 500 and response.json().get("code") != (
                    NOT_IMPLEMENTED
                ):
                    # 501 is the project's honest "not built yet" answer, not a broken route.
                    problems.append(
                        f"{role} broke {method} {path}: {response.status_code} {response.text}"
                    )
            else:
                body = response.json()
                if response.status_code != 403 or body.get("code") != FORBIDDEN_CODE:
                    problems.append(
                        f"{role} was not refused {method} {path}: "
                        f"{response.status_code} {response.text}"
                    )

    assert not problems, "\n".join(problems)


def test_every_refusal_is_logged_and_writes_nothing_else(client):
    """FR-M1-02's processing step: refuse, then record the attempt. One row per refusal, no more."""
    refused = [
        (method, path, role)
        for method, path, allowed in MATRIX
        for role in ROLES
        if role not in allowed
    ]
    tokens = {role: sign_in(client, role) for role in ROLES}
    for method, path, role in refused:
        response = call(client, tokens[role], method, path)
        assert response.status_code == 403, f"{role} {method} {path}: {response.text}"

    with sessionmaker(bind=client.app.state.engine)() as session:
        rows = session.scalars(
            select(SysLog).where(SysLog.action == "forbidden").order_by(SysLog.log_id)
        ).all()
        written = [str(row.target_id) for row in rows]

    assert written == [f"{method} {concrete(path)}" for method, path, _role in refused]


def test_the_matrix_covers_every_mounted_route(client):
    """A route someone adds without adding a row here fails this test, not the next audit."""
    mounted = {
        (method.upper(), path)
        for path, operations in client.app.openapi()["paths"].items()
        for method in operations
    }
    listed = {(method, path) for method, path, _allowed in MATRIX}
    exempt = set(EXEMPT)

    unlisted = sorted(mounted - listed - exempt)
    stale = sorted(listed - mounted)
    assert not unlisted, f"routes with no row in MATRIX: {unlisted}"
    assert not stale, f"MATRIX names routes the application does not mount: {stale}"
