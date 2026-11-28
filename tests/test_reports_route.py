"""The report archive is filtered by the server, and the generated file is downloadable (FR-M5-04).

`GET /api/reports` accepted only `page` and `size`, so the page fetched the whole archive and filtered
it in the browser; and no route served the Markdown `_render` writes, although FR-M5-04 calls the
report downloadable and `report.file_path` records it (TM-096). These tests hold both halves at the
HTTP level: the period filter is an overlap test on the stored UTC instants (ADR 14), and the file
route answers the document itself or an envelope that names why it cannot.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import Report
from test_time_basis import _app_client, auth, sign_in


def generate(client, headers, **period):
    """Generate one report through the route; a fixture that writes the row would not prove the route."""
    body = client.post("/api/reports", json=period, headers=headers).json()
    assert body["code"] == 0, body
    return body["data"]


def history(client, headers, **params):
    body = client.get("/api/reports", params=params, headers=headers).json()
    assert body["code"] == 0, body
    return body["data"]


def store(client, report_code: str, **fields) -> None:
    """A row written directly: the file states and the traversal case cannot be produced by the route."""
    row = {
        "report_code": report_code,
        "period_start": datetime(2026, 11, 2),
        "period_end": datetime(2026, 11, 2, 23, 59, 59),
        "template": "standard",
        "basis": "reviewed",
        "status": 1,
    }
    row = row | fields
    with client.app.state.session_factory() as session:
        session.add(Report(**row))
        session.commit()


def test_history_filters_by_period_overlap_on_the_stored_instants(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        spanning = generate(
            client,
            headers,
            period_start="2026-11-01",
            period_end="2026-11-03",
            basis="reviewed",
        )
        # 00:00-00:30 local on 11-02 is stored as 11-01T16:00Z-16:30Z: a string slice of the stored
        # column would put this report on 11-01 and drop it from an 11-02 filter.
        short = generate(
            client,
            headers,
            period_start="2026-11-02T00:00:00+08:00",
            period_end="2026-11-02T00:30:00+08:00",
            basis="reviewed",
        )
        later = generate(
            client,
            headers,
            period_start="2026-11-10",
            period_end="2026-11-10",
            basis="reviewed",
        )
        assert history(client, headers)["total"] == 3

        day = history(client, headers, **{"from": "2026-11-02", "to": "2026-11-02"})
        assert day["total"] == 2
        assert {row["report_code"] for row in day["items"]} == {
            spanning["report_code"],
            short["report_code"],
        }

        # Overlap, not equality: the span that ends on 11-03 was not generated for 11-03.
        edge = history(client, headers, **{"from": "2026-11-03", "to": "2026-11-04"})
        assert edge["total"] == 1
        assert [row["report_code"] for row in edge["items"]] == [spanning["report_code"]]

        other = history(client, headers, **{"from": "2026-11-10", "to": "2026-11-10"})
        assert other["total"] == 1
        assert [row["report_code"] for row in other["items"]] == [later["report_code"]]

        none = history(client, headers, **{"from": "2026-11-05", "to": "2026-11-06"})
        assert none == {"items": [], "total": 0, "page": 1, "size": 24}


def test_history_counts_and_pages_the_filtered_set(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        generate(
            client,
            headers,
            period_start="2026-11-02",
            period_end="2026-11-02",
            basis="raw",
        )
        generate(
            client,
            headers,
            period_start="2026-11-02",
            period_end="2026-11-02",
            basis="raw",
        )
        generate(
            client,
            headers,
            period_start="2026-11-10",
            period_end="2026-11-10",
            basis="raw",
        )

        first = history(client, headers, **{"from": "2026-11-02", "to": "2026-11-02"}, size=1)
        assert first["total"] == 2
        assert len(first["items"]) == 1
        second = history(
            client,
            headers,
            **{"from": "2026-11-02", "to": "2026-11-02", "page": 2},
            size=1,
        )
        assert second["total"] == 2
        assert len(second["items"]) == 1
        assert second["items"][0]["report_id"] != first["items"][0]["report_id"]


def test_history_filters_by_template_and_basis_together(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        standard = generate(
            client,
            headers,
            period_start="2026-11-02",
            period_end="2026-11-02",
            template="standard",
            basis="reviewed",
        )
        brief = generate(
            client,
            headers,
            period_start="2026-11-02",
            period_end="2026-11-02",
            template="brief",
            basis="raw",
        )
        mixed = generate(
            client,
            headers,
            period_start="2026-11-02",
            period_end="2026-11-02",
            template="standard",
            basis="raw",
        )
        assert history(client, headers)["total"] == 3

        by_template = history(client, headers, template="brief")
        assert by_template["total"] == 1
        assert [row["report_code"] for row in by_template["items"]] == [brief["report_code"]]

        by_basis = history(client, headers, basis="raw")
        assert by_basis["total"] == 2
        assert {row["report_code"] for row in by_basis["items"]} == {
            brief["report_code"],
            mixed["report_code"],
        }

        both = history(client, headers, template="standard", basis="raw")
        assert both["total"] == 1
        assert [row["report_code"] for row in both["items"]] == [mixed["report_code"]]
        assert both["items"][0]["report_code"] != standard["report_code"]

        # Combined with the period: every filter has to agree.
        elsewhere = history(
            client,
            headers,
            template="standard",
            basis="raw",
            **{"from": "2026-11-09", "to": "2026-11-09"},
        )
        assert elsewhere["total"] == 0


def test_history_refuses_an_invalid_or_reversed_range(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        reversed_range = client.get(
            "/api/reports",
            params={"from": "2026-11-05", "to": "2026-11-01"},
            headers=headers,
        )
        assert reversed_range.status_code == 400
        assert reversed_range.json()["code"] == 40002
        assert "结束日期" in reversed_range.json()["message"]

        invalid = client.get("/api/reports", params={"from": "2026-13-01"}, headers=headers)
        assert invalid.status_code == 400
        assert invalid.json()["code"] == 40002

        invalid_template = client.get(
            "/api/reports", params={"template": "poster"}, headers=headers
        )
        assert invalid_template.status_code == 400
        assert invalid_template.json()["code"] == 40002


def test_download_answers_the_stored_markdown_as_an_attachment(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        report = generate(
            client,
            headers,
            period_start="2026-11-02",
            period_end="2026-11-02",
            basis="raw",
        )
        response = client.get(f"/api/reports/{report['report_code']}/file", headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/markdown")
        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment")
        assert f'filename="{report["report_code"]}.md"' in disposition
        stored = Path(report["file_path"]).read_bytes()
        assert response.content == stored
        assert response.text.startswith(f"# 巡检报告 {report['report_code']}")


def test_download_refuses_an_unknown_report_code(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        response = client.get("/api/reports/RP000000-999/file", headers=headers)
        assert response.status_code == 404
        assert response.json()["code"] == 40401
        assert "不存在" in response.json()["message"]


def test_download_requires_a_signed_in_caller(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        report = generate(
            client,
            headers,
            period_start="2026-11-02",
            period_end="2026-11-02",
            basis="raw",
        )
        response = client.get(f"/api/reports/{report['report_code']}/file")
        assert response.status_code == 401
        assert response.json()["code"] == 40102


def test_download_refuses_a_stored_path_outside_the_data_root(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        # The database is trusted, but the stored path must still be contained: `../secret.md` is
        # inside neither the reports directory nor the data root.
        (tmp_path / "secret.md").write_text("TOPSECRET", encoding="utf-8")
        store(client, "RP999999-901", file_path="../secret.md")
        response = client.get("/api/reports/RP999999-901/file", headers=headers)
        assert response.status_code == 404
        assert response.json()["code"] == 40401
        assert "TOPSECRET" not in response.text


def test_download_reports_a_missing_file_as_404_not_500(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        store(client, "RP999999-902", file_path="reports/typescript-was-here.md")
        response = client.get("/api/reports/RP999999-902/file", headers=headers)
        assert response.status_code == 404
        assert response.json()["code"] == 40401
        assert "重新生成" in response.json()["message"]


def test_download_refuses_a_report_that_is_not_ready(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        store(client, "RP999999-903", status=0, file_path=None)
        generating = client.get("/api/reports/RP999999-903/file", headers=headers)
        # The row exists and the file is coming: a state conflict says retry, a 404 would not.
        assert generating.status_code == 409
        assert generating.json()["code"] == 40901
        assert "稍后" in generating.json()["message"]

        store(
            client,
            "RP999999-904",
            status=2,
            file_path=None,
            error_msg="写入文件失败：OSError",
        )
        failed = client.get("/api/reports/RP999999-904/file", headers=headers)
        # A failed report has no document and never will: the answer names the recorded reason.
        assert failed.status_code == 404
        assert failed.json()["code"] == 40401
        assert "写入文件失败" in failed.json()["message"]
