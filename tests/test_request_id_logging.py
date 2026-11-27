"""The request id in the log line (PLAN P4-05, api-contract §1).

The id already rides on every response and on `X-Request-Id`; the defect was that no log record
carried it, so the id a caller reported could not be searched for. The filter appends it, and
`create_app` installs that filter on the root handlers the process actually writes through.
"""

from __future__ import annotations

import io
import logging

from app import main
from app.envelope import request_id_ctx


def test_a_record_gets_the_request_id_in_force() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(main.RequestIdFilter())
    logger = logging.getLogger("app.test.request_id")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    token = request_id_ctx.set("req-1a2b3c4d")
    try:
        logger.info("frame %s stored", 3)
    finally:
        request_id_ctx.reset(token)
        logger.removeHandler(handler)

    assert "frame 3 stored [req=req-1a2b3c4d]" in stream.getvalue()


def test_the_application_installs_the_filter_on_the_root_handlers() -> None:
    root = logging.getLogger()
    handler = logging.NullHandler()
    root.addHandler(handler)
    try:
        main.install_request_id_logging()
        assert any(isinstance(item, main.RequestIdFilter) for item in handler.filters)
    finally:
        root.removeHandler(handler)
