"""A preview is read-only and uses the exact figures written into the generated file."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from app.models import DetectObject, DetectTask, MediaAsset, SpeciesDict
from sqlalchemy import select
from test_time_basis import FIRST_ID, _app_client, auth, seed_the_local_day_boundaries, sign_in


@pytest.mark.parametrize("basis,count", [("raw", 3), ("reviewed", 2)])
def test_preview_figures_equal_the_generated_file(tmp_path, monkeypatch, basis, count):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        seed_the_local_day_boundaries(client)
        with client.app.state.session_factory() as session:
            task = DetectTask(task_code="preview-task", task_type=2, asset_count=1, status=2)
            session.add(task)
            session.add(SpeciesDict(class_code="holothurian", cn_name="Sea cucumber", category=1))
            session.flush()
            asset = session.scalar(select(MediaAsset).where(MediaAsset.frame_id == FIRST_ID))
            for status in [0, 2, 3]:
                session.add(
                    DetectObject(
                        task_id=task.task_id,
                        asset_id=asset.asset_id,
                        frame_id=FIRST_ID,
                        class_code="holothurian",
                        confidence=0.8,
                        x=0.1,
                        y=0.1,
                        w=0.2,
                        h=0.2,
                        review_status=status,
                    )
                )
            session.commit()
        headers = auth(sign_in(client))
        period = {"period_start": "2026-11-02", "period_end": "2026-11-02", "basis": basis}
        response = client.get("/api/reports/preview", params=period, headers=headers)
        assert response.status_code == 200, response.text
        preview = response.json()["data"]
        assert preview["figures"]["frames"] == 2
        assert preview["figures"]["species"][0]["count"] == count
        assert client.get("/api/reports", headers=headers).json()["data"]["total"] == 0
        period["preview_token"] = preview["preview_token"]
        generated = client.post("/api/reports", json=period, headers=headers).json()["data"]
        document = Path(generated["file_path"]).read_text(encoding="utf-8")
        figures = preview["figures"]
        assert f"{figures['frames']} 帧" in document
        assert f"{figures['rejected']} 帧，拦截率 {figures['rate']:.2%}" in document
        for item in figures["species"]:
            assert f"| {item['name']} | {item['count']} | {item['share']:.2%} |" in document
        with client.app.state.session_factory() as session:
            session.scalar(
                select(MediaAsset).where(MediaAsset.frame_id == FIRST_ID)
            ).quality_flag = 1
            session.commit()
        refused = client.post("/api/reports", json=period, headers=headers)
        assert refused.status_code == 409, refused.text
        assert client.get("/api/reports", headers=headers).json()["data"]["total"] == 1
        assert preview["basis"] == basis
        node = shutil.which("node")
        assert node, "Node is required to verify the displayed preview"
        module = (Path(__file__).resolve().parents[1] / "web/static/js/report-preview.js").as_uri()
        script = f"import {{reportPreviewHtml}} from {json.dumps(module)}; console.log(reportPreviewHtml({json.dumps(preview)}));"
        output = subprocess.run(
            [node, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=30,
        ).stdout
        assert f"{figures['frames']} 帧" in output
        for item in figures["species"]:
            assert f"<td>{item['count']}</td><td>{item['share']:.2%}</td>" in output


def test_preview_refuses_a_reversed_period(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "UTC") as client:
        response = client.get(
            "/api/reports/preview",
            headers=auth(sign_in(client)),
            params={
                "period_start": "2026-11-03",
                "period_end": "2026-11-02",
            },
        )
        assert response.status_code == 400
        assert response.json()["code"] == 40002


def test_report_page_tracks_its_current_preview():
    node = shutil.which("node")
    assert node, "Node is required to verify the report page"
    subprocess.run(
        [node, str(Path(__file__).with_name("report_preview.mjs"))],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_brief_template_keeps_the_species_section_and_the_footer(tmp_path, monkeypatch):
    with _app_client(tmp_path, monkeypatch, "Asia/Shanghai") as client:
        headers = auth(sign_in(client))
        period = {"period_start": "2026-11-02", "period_end": "2026-11-02", "basis": "raw"}
        brief = client.post(
            "/api/reports", json={**period, "template": "brief"}, headers=headers
        ).json()
        assert brief["code"] == 0, brief
        document = Path(brief["data"]["file_path"]).read_text(encoding="utf-8")
        assert "统计周期" in document
        assert "## 物种组成" in document
        assert "模型版本" in document and "口径" in document
        assert "## 采集与质量" not in document
        assert "- 模型版本" not in document

        standard = client.post(
            "/api/reports", json={**period, "template": "standard"}, headers=headers
        ).json()
        assert standard["code"] == 0, standard
        full = Path(standard["data"]["file_path"]).read_text(encoding="utf-8")
        assert "## 采集与质量" in full
        assert "- 模型版本" in full
