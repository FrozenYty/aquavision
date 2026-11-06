"""The response envelope and the error codes behind it (contract §2, §3).

Every response leaves through here. Routers return `ok(data)` or raise `ApiError`; nothing builds a
bare `JSONResponse` by hand, because a response that forgets `request_id` is a response nobody can
match to a log line.

The codes are grouped by range, as the contract lists them. `50100` is the one addition: a route that
is mounted but whose module is not built returns it, so the frontend can tell "not built yet" from
"broken" — the alternative, returning fake data, is the failure this code exists to prevent.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

OK = 0

MISSING_PARAM = 40001
BAD_PARAM = 40002
TOKEN_EXPIRED = 40101
UNAUTHENTICATED = 40102
FORBIDDEN = 40301
NOT_FOUND = 40401
CONFLICT = 40901
INTERNAL = 50001
NOT_IMPLEMENTED = 50100

#: The HTTP status that goes with each code, so a caller can act on the status alone.
STATUS = {
    OK: 200,
    MISSING_PARAM: 400,
    BAD_PARAM: 400,
    TOKEN_EXPIRED: 401,
    UNAUTHENTICATED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    CONFLICT: 409,
    INTERNAL: 500,
    NOT_IMPLEMENTED: 501,
}

#: The request id of the request being served, set by the middleware in `main`.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class ApiError(Exception):
    """A failure the caller should see, with the contract's code and a message safe to display."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = STATUS.get(code, 400)


def envelope(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
        "request_id": request_id_ctx.get(),
    }


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    """A successful response. Routers return this; the middleware handles the rest."""
    return envelope(OK, message, data)


def not_built(what: str) -> ApiError:
    """A mounted route whose module has not been written yet.

    Named rather than anonymous: the message says what is missing, so the frontend team reads the
    response instead of hunting through logs.
    """
    return ApiError(NOT_IMPLEMENTED, f"{what} 尚未实现")
