"""The demo reset's decisions and the mock's three new routes, both run for real under Node.

The settings page deletes data, so its decisions are kept out of the DOM in web/static/js/demo.js and
called here: whether the typed confirmation unlocks the button, which per-table counts the page shows,
and how success, demo-mode-off and failure read. A 404 must never be able to read like a success, so
the refusal view is a value with no rows at all and the page draws only that value.

The mock half calls web/static/mock/index.js through its own ``handle()`` - the entry point api.js uses
- so the tests exercise the route table and the tab's recorded state, not a fixture: an untouched tab
has no timeline, a submission adds exactly one entry, and a rollback to the current set is a 409.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEMO_JS = ROOT / "web" / "static" / "js" / "demo.js"
MOCK_JS = ROOT / "web" / "static" / "mock" / "index.js"
ADMIN = ROOT / "web" / "templates" / "admin.html"

NODE = shutil.which("node")
# Locally a missing Node skips; in CI it fails, so the checks can never pass by being skipped there.
if NODE is None and os.environ.get("CI"):
    pytest.fail("Node is required in CI to run tests/test_mock_demo.py", pytrace=False)
needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")


def run_js(source: str):
    out = subprocess.run(
        [NODE, "--input-type=module", "-e", source],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    return json.loads(out.stdout)


def call(fn: str, *args):
    source = (
        f"import * as m from {json.dumps(DEMO_JS.as_uri())};"
        f"console.log(JSON.stringify(m.{fn}(...{json.dumps(list(args))})));"
    )
    return run_js(source)


def mock(body: str):
    """Run one sequence of handle() calls in a fresh Node process and return its logged JSON."""
    return run_js(f"import {{ handle }} from {json.dumps(MOCK_JS.as_uri())};" + body)


def mock_with_store(store: dict | None, body: str):
    """One page-load's worth of the mock, over a fake per-tab store (Node has no sessionStorage)."""
    source = (
        f"const store = {json.dumps(store or {})};"
        "globalThis.sessionStorage = {"
        "  getItem: (key) => (key in store ? store[key] : null),"
        "  setItem: (key, value) => { store[key] = String(value); },"
        "};"
        f"const {{ handle }} = await import({json.dumps(MOCK_JS.as_uri())});" + body
    )
    return run_js(source)


# The demo-reset response shape from docs/api-contract-en.md §6 (Demo reset).
RESULT = {
    "deleted": {"media_asset": 12, "detect_object": 34, "sys_log": 57},
    "frame_files_removed": 12,
    "model_online": "v8n-E0-exploratory",
}
DEMO_OFF = {"code": 40401, "message": "演示模式未开启"}
SERVER_ERROR = {"code": 50001, "message": "服务器内部错误"}


# ---- The section's decisions --------------------------------------------------------------------


@needs_node
def test_the_reset_button_unlocks_only_on_the_typed_token():
    assert call("resetGate", {"token": ""}) == {
        "enabled": False,
        "hint": "先输入 RESET 才能启用按钮",
    }
    assert call("resetGate", {"token": "RESET"}) == {
        "enabled": True,
        "hint": "将删除采集数据；账号、物种字典、模型版本、参数会保留",
    }
    assert call("resetGate", {"token": "reset"})["enabled"] is False
    assert call("resetGate", {"token": "RESET "})["enabled"] is False
    assert call("resetGate", {"token": "RESET", "busy": True}) == {
        "enabled": False,
        "hint": "正在复位…",
    }


@needs_node
def test_the_counts_shown_are_exactly_what_the_server_reported():
    rows = call("deletedRows", {"media_asset": 12, "detect_object": 34, "sys_log": 0})
    assert rows == [
        {"table": "detect_object", "label": "检测框", "count": 34},
        {"table": "media_asset", "label": "采集帧", "count": 12},
        {"table": "sys_log", "label": "操作日志", "count": 0},
    ]


@needs_node
def test_an_unknown_table_keeps_its_own_name():
    assert call("deletedRows", {"mystery_table": 2}) == [
        {"table": "mystery_table", "label": "mystery_table", "count": 2},
    ]


@needs_node
def test_a_success_view_carries_the_counts_and_the_online_model():
    view = call("resetView", {"result": RESULT})
    assert view["state"] == "success"
    assert view["text"] == "已删除 103 行业务记录，移除 12 个图像文件。"
    assert view["rows"] == [
        {"table": "detect_object", "label": "检测框", "count": 34},
        {"table": "media_asset", "label": "采集帧", "count": 12},
        {"table": "sys_log", "label": "操作日志", "count": 57},
    ]
    assert view["model"] == "v8n-E0-exploratory"
    assert view["files"] == 12


@needs_node
def test_demo_mode_off_is_its_own_state_and_has_no_counts():
    view = call("resetView", {"error": DEMO_OFF})
    assert view["state"] == "off"
    assert view["rows"] == []
    assert view["model"] is None
    assert view["files"] is None
    assert "演示模式未开启" in view["title"]
    assert "没有删除任何数据" in view["text"]
    assert "AV_DEMO_ENABLED" in view["text"]


@needs_node
def test_any_other_error_is_a_failure_with_no_counts():
    view = call("resetView", {"error": SERVER_ERROR})
    assert view["state"] == "failure"
    assert view["rows"] == []
    assert view["model"] is None
    assert view["title"] == "复位失败"
    assert "服务器内部错误" in view["text"]


@needs_node
def test_no_online_model_reads_as_such():
    view = call(
        "resetView",
        {"result": {"deleted": {}, "frame_files_removed": 0, "model_online": None}},
    )
    assert view["state"] == "success"
    assert view["model"] == "没有上线的模型"
    assert view["rows"] == []
    assert view["text"] == "已删除 0 行业务记录，移除 0 个图像文件。"


# ---- The page -----------------------------------------------------------------------------------


def page_text() -> str:
    return ADMIN.read_text(encoding="utf-8")


def render_block() -> str:
    """renderReset() as written, so the success-only table can be checked."""
    page = page_text()
    start = page.index("const renderReset = (view) =>")
    return page[start : page.index('$("btn-demo-reset").onclick', start)]


def test_the_settings_page_has_the_demo_reset_section():
    page = page_text()
    for element in (
        'id="reset-token"',
        'id="btn-demo-reset"',
        'id="reset-hint"',
        'id="reset-result"',
    ):
        assert element in page, f"admin.html lacks the demo reset section's {element}"
    assert 'from "../static/js/demo.js"' in page
    assert "会删除" in page and "会保留" in page
    assert "AV_DEMO_ENABLED" in page


def test_the_page_calls_the_demo_reset_route():
    assert "api.demoReset(" in page_text()


def test_both_outcomes_go_through_the_same_pure_view():
    page = page_text()
    assert "renderReset(resetView({ result }))" in page
    assert "const view = resetView({ error: err });" in page
    assert "renderReset(view);" in page


def test_a_404_cannot_be_drawn_like_a_success():
    # The decision: a refusal view has no counts for the page to draw from.
    refused = call("resetView", {"error": DEMO_OFF})
    assert refused["state"] != "success"
    assert refused["rows"] == []
    assert refused["model"] is None
    # The page: the result table is built only inside the success branch of the single renderer.
    block = render_block()
    success = block.index('view.state === "success"')
    rows = block.index("view.rows")
    refusal = block.index('view.state === "off" ? "warning" : "danger"')
    assert success < rows < refusal, "the count table is drawn only from a success view"


# ---- The mock's three new routes ----------------------------------------------------------------


@needs_node
def test_a_tab_with_no_review_answers_an_empty_timeline():
    out = mock("""
const frame = (await handle("GET", "/frames", { query: { page: 1, size: 1 } })).data.items[0];
const versions = await handle("GET", `/review/frames/${frame.frame_id}/versions`, {});
console.log(JSON.stringify({ frame: frame.frame_id, versions }));
""")
    assert out["versions"]["code"] == 0
    assert out["versions"]["data"] == {"frame_id": out["frame"], "items": []}


@needs_node
def test_one_submission_answers_one_timeline_entry():
    out = mock("""
const frame = (await handle("GET", "/frames", { query: { page: 1, size: 1 } })).data.items[0];
const objects = (await handle("GET", `/frames/${frame.frame_id}/objects`, {})).data.items;
const submit = await handle("POST", `/review/frames/${frame.frame_id}`, {
  body: { objects: objects.slice(1) },
});
const versions = await handle("GET", `/review/frames/${frame.frame_id}/versions`, {});
console.log(JSON.stringify({ before: objects.length, submit: submit.data, versions: versions.data }));
""")
    items = out["versions"]["items"]
    assert len(items) == 1
    entry = items[0]
    assert set(entry) == {
        "log_id",
        "action",
        "created_at",
        "author",
        "before_count",
        "after_count",
    }
    assert entry["action"] == "submit"
    assert entry["before_count"] == out["before"]
    assert entry["after_count"] == out["submit"]["object_count"]
    assert isinstance(entry["log_id"], int)
    assert entry["author"] == "演示账号"


@needs_node
def test_a_rollback_restores_the_recorded_set_and_appends_an_entry():
    out = mock("""
const frame = (await handle("GET", "/frames", { query: { page: 1, size: 1 } })).data.items[0];
const objects = (await handle("GET", `/frames/${frame.frame_id}/objects`, {})).data.items;
const reduced = objects.slice(1);
await handle("POST", `/review/frames/${frame.frame_id}`, { body: { objects: reduced } });
await handle("POST", `/review/frames/${frame.frame_id}`, { body: { objects } });
const timeline = await handle("GET", `/review/frames/${frame.frame_id}/versions`, {});
const older = timeline.data.items[timeline.data.items.length - 1];
const rollback = await handle("POST", `/review/frames/${frame.frame_id}/rollback`, {
  body: { log_id: older.log_id },
});
const after = await handle("GET", `/frames/${frame.frame_id}/objects`, {});
const history = await handle("GET", `/review/frames/${frame.frame_id}/versions`, {});
console.log(JSON.stringify({
  reduced: reduced.length, timeline: timeline.data.items, older, rollback,
  after: after.data.items.length, history: history.data.items,
}));
""")
    rollback = out["rollback"]
    assert rollback["code"] == 0
    assert set(rollback["data"]) == {
        "log_id",
        "frame_id",
        "version_no",
        "object_count",
        "hard_sample",
        "rejected",
        "added",
    }
    assert rollback["data"]["log_id"] == out["older"]["log_id"]
    assert rollback["data"]["object_count"] == out["reduced"]
    assert out["after"] == out["reduced"], "the recorded set is the one now stored"
    history = out["history"]
    assert len(history) == 3
    assert history[0]["action"] == "rollback"
    assert history[0]["after_count"] == out["reduced"]


@needs_node
def test_rolling_back_to_the_current_set_is_a_409_no_op():
    out = mock("""
const frame = (await handle("GET", "/frames", { query: { page: 1, size: 1 } })).data.items[0];
const objects = (await handle("GET", `/frames/${frame.frame_id}/objects`, {})).data.items;
await handle("POST", `/review/frames/${frame.frame_id}`, { body: { objects } });
const timeline = await handle("GET", `/review/frames/${frame.frame_id}/versions`, {});
const rollback = await handle("POST", `/review/frames/${frame.frame_id}/rollback`, {
  body: { log_id: timeline.data.items[0].log_id },
});
console.log(JSON.stringify(rollback));
""")
    assert out["code"] == 40901
    assert out["data"] is None
    assert "无需回滚" in out["message"]


@needs_node
def test_another_frames_entry_and_an_unknown_entry_are_refused():
    out = mock("""
const frames = (await handle("GET", "/frames", { query: { page: 1, size: 2 } })).data.items;
const [one, two] = frames;
const objects = (await handle("GET", `/frames/${one.frame_id}/objects`, {})).data.items;
await handle("POST", `/review/frames/${one.frame_id}`, { body: { objects } });
const recorded = (await handle("GET", `/review/frames/${one.frame_id}/versions`, {})).data.items[0];
const other = await handle("POST", `/review/frames/${two.frame_id}/rollback`, {
  body: { log_id: recorded.log_id },
});
const missing = await handle("POST", `/review/frames/${one.frame_id}/rollback`, {
  body: { log_id: 999999 },
});
console.log(JSON.stringify({ other, missing }));
""")
    assert out["other"]["code"] == 40901
    assert "另一帧" in out["other"]["message"]
    assert out["missing"]["code"] == 40401


@needs_node
def test_demo_reset_reports_what_it_deleted_and_empties_the_tab():
    out = mock("""
const before = await handle("GET", "/monitor", {});
const reset = await handle("POST", "/demo/reset", {});
const after = await handle("GET", "/monitor", {});
const models = await handle("GET", "/models", {});
console.log(JSON.stringify({
  before: before.data, reset, after: after.data, models: models.data,
}));
""")
    data = out["reset"]["data"]
    assert set(data) == {"deleted", "frame_files_removed", "model_online"}
    for table in (
        "media_asset",
        "detect_object",
        "detect_task",
        "report",
        "dataset",
        "train_experiment",
        "sys_message",
        "sys_log",
    ):
        assert isinstance(data["deleted"][table], int), table
    assert data["deleted"]["media_asset"] == out["before"]["frames"]
    assert data["frame_files_removed"] == data["deleted"]["media_asset"]
    assert out["after"]["frames"] == 0
    online = [model for model in out["models"]["items"] if model["is_online"]]
    assert data["model_online"] == online[0]["version_name"]


@needs_node
def test_a_reset_survives_the_next_page_load_in_the_same_tab():
    first = mock_with_store(
        None,
        """
const reset = await handle("POST", "/demo/reset", {});
console.log(JSON.stringify({ reset: reset.data, store }));
""",
    )
    assert first["reset"]["deleted"]["media_asset"] > 0
    second = mock_with_store(
        first["store"],
        """
const monitor = await handle("GET", "/monitor", {});
const models = await handle("GET", "/models", {});
console.log(JSON.stringify({ monitor: monitor.data, models: models.data }));
""",
    )
    assert second["monitor"]["frames"] == 0, "the seeded demo rows must not come back after a reset"
    online = [model for model in second["models"]["items"] if model["is_online"]]
    assert online and online[0]["version_name"] == first["reset"]["model_online"]
