"""The review version panel's decisions, run for real: web/static/js/versions.js under Node.

A rollback overwrites the reviewer's canvas, so the decisions that matter are kept out of the DOM:
what a timeline entry reads as, whether the restore button may act, and what a finished rollback may
do to the canvas. A refused rollback is a normal outcome - the reviewer picked the set that is already
current, or another frame's entry - so the canvas must stay exactly as it was and only the reason is
shown. These tests call those functions instead of reading them. The page side is held too:
review.html must contain the panel and call both version routes (PLAN P3-05).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VERSIONS_JS = ROOT / "web" / "static" / "js" / "versions.js"
REVIEW = ROOT / "web" / "templates" / "review.html"

NODE = shutil.which("node")
# Locally a missing Node skips; in CI it fails, so the checks can never pass by being skipped there.
if NODE is None and os.environ.get("CI"):
    pytest.fail("Node is required in CI to run tests/test_review_versions_page.py", pytrace=False)
needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")


def call(fn: str, *args):
    script = (
        f"import * as m from {json.dumps(VERSIONS_JS.as_uri())};"
        f"console.log(JSON.stringify(m.{fn}(...{json.dumps(list(args))})));"
    )
    out = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    return json.loads(out.stdout)


# A timeline entry as GET /api/review/frames/{id}/versions returns one (api-contract §6).
SUBMIT = {
    "log_id": 87,
    "action": "submit",
    "created_at": "2026-11-03T19:34:10+00:00",
    "author": "Gao Tianxiang",
    "before_count": 12,
    "after_count": 11,
}
ROLLBACK = {**SUBMIT, "log_id": 91, "action": "rollback", "before_count": 11, "after_count": 12}
NO_OP = {"code": 40901, "message": "该版本与当前结果相同，无需回滚"}
OTHER_FRAME = {"code": 40901, "message": "该复核记录属于另一帧，不能用于回滚"}


@needs_node
def test_an_entry_reads_as_its_action_and_box_counts():
    assert call("versionText", SUBMIT) == "提交 · 12 → 11"
    assert call("versionText", ROLLBACK) == "回滚 · 11 → 12"
    assert call("versionText", {**SUBMIT, "action": "audit"}) == "audit · 12 → 11"


@needs_node
def test_an_entry_without_an_author_is_system_written():
    assert call("authorText", SUBMIT) == "Gao Tianxiang"
    assert call("authorText", {**SUBMIT, "author": None}) == "系统"


@needs_node
def test_restore_is_disabled_until_an_entry_is_selected():
    assert call("restoreState", {"selectedLogId": None, "versionCount": 1}) == {
        "enabled": False,
        "hint": "先选择一个版本",
    }
    assert call("restoreState", {"selectedLogId": 87, "versionCount": 1}) == {
        "enabled": True,
        "hint": "恢复会用该版的目标覆盖当前画布",
    }
    assert call("restoreState", {"selectedLogId": None, "versionCount": 0}) == {
        "enabled": False,
        "hint": "没有可回滚的版本",
    }


@needs_node
def test_restore_is_disabled_while_the_request_is_in_flight():
    assert call("restoreState", {"selectedLogId": 87, "restoring": True, "versionCount": 1}) == {
        "enabled": False,
        "hint": "正在恢复…",
    }


@needs_node
def test_a_conflict_is_reported_as_a_normal_refusal_not_a_failure():
    assert call("refusalNotice", NO_OP) == {
        "kind": "warning",
        "text": "未回滚：该版本与当前结果相同，无需回滚。画面未改动。",
    }
    assert call("refusalNotice", OTHER_FRAME)["kind"] == "warning"
    assert "该复核记录属于另一帧" in call("refusalNotice", OTHER_FRAME)["text"]


@needs_node
def test_a_missing_entry_and_a_server_error_are_failures():
    missing = call("refusalNotice", {"code": 40401, "message": "复核记录不存在"})
    assert missing == {
        "kind": "danger",
        "text": "回滚失败：这条版本记录已不存在，请刷新版本列表后重试。",
    }
    broken = call("refusalNotice", {"code": 50001, "message": "服务器内部错误"})
    assert broken == {"kind": "danger", "text": "回滚失败：服务器内部错误"}


@needs_node
def test_the_canvas_is_reloaded_only_after_a_successful_restore():
    assert call("rollbackPlan", None) == {"reload": True, "notice": None}
    refused = call("rollbackPlan", NO_OP)
    assert refused["reload"] is False
    assert refused["notice"] == call("refusalNotice", NO_OP)


@needs_node
def test_the_success_message_reports_the_new_version():
    result = {
        "log_id": 87,
        "frame_id": "20261103T193012-0042",
        "version_no": 4,
        "object_count": 11,
        "hard_sample": True,
        "rejected": 2,
        "added": 1,
    }
    assert call("restoreText", result) == "已恢复到第 4 版：目标 11 个，新增 1，驳回 2"


def rollback_block() -> str:
    """The page's rollbackTo() as written, so the order of its branches can be checked."""
    page = REVIEW.read_text(encoding="utf-8")
    start = page.index("async function rollbackTo")
    return page[start : page.index('$("btn-versions").onclick', start)]


def test_the_review_page_has_the_version_panel():
    page = REVIEW.read_text(encoding="utf-8")
    for element in (
        'id="btn-versions"',
        'id="versions"',
        'id="version-list"',
        'id="btn-rollback"',
        'id="version-hint"',
    ):
        assert element in page, f"review.html lacks the version panel's {element}"
    assert 'from "../static/js/versions.js"' in page


def test_the_page_calls_both_version_routes():
    page = REVIEW.read_text(encoding="utf-8")
    assert "api.listReviewVersions(" in page, "the panel must read the frame's timeline"
    assert "api.rollbackReview(" in page, "the panel must be able to restore an entry"


def test_a_refused_rollback_reports_before_anything_could_touch_the_canvas():
    block = rollback_block()
    assert "const plan = rollbackPlan(error)" in block
    assert "if (!plan.reload)" in block
    refusal = block.index("if (!plan.reload)")
    reloaded = block.index("await reloadBoxes()")
    assert refusal < reloaded, "the refusal branch must run before the canvas is reloaded"
    notice = block.index("toast(plan.notice.text, plan.notice.kind)", refusal)
    assert notice < reloaded, "a refusal must only say why, before any canvas reload"


def test_a_failed_timeline_is_drawn_as_a_failure_not_an_empty_list():
    assert "showError(list, err" in REVIEW.read_text(encoding="utf-8")
