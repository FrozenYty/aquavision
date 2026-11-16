"""The asset gate follows imports, deduplicates, and fails when a page grows."""

import importlib.util
from pathlib import Path


def tool():
    path = Path(__file__).resolve().parents[1] / "scripts/check-frontend-budget.py"
    spec = importlib.util.spec_from_file_location("frontend_budget", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_budget_follows_imports_and_fails_on_growth(tmp_path):
    module = tool()
    web = tmp_path / "web"
    web.mkdir()
    page = web / "index.html"
    page.write_text(
        '<link rel="stylesheet" href="style.css"><script type="module">import "./a.js";</script>'
    )
    (web / "style.css").write_text("body {}")
    (web / "a.js").write_text('import "./b.js"; import("./b.js");')
    (web / "b.js").write_text('import "./a.js";')
    row = module.measure(page, web)
    expected = (
        len(b'import "./a.js";') + (web / "a.js").stat().st_size + (web / "b.js").stat().st_size
    )
    assert row["js"] == expected
    assert row["css"] == len("body {}")
    assert module.check([row], js_limit=expected, css_limit=7) == 0
    assert module.check([row], js_limit=expected - 1, css_limit=7) == 1
    assert module.check([row], js_limit=expected, css_limit=6) == 1


def test_budget_checks_the_real_thirteen_pages():
    module = tool()
    web = Path(__file__).resolve().parents[1] / "web"
    rows = [module.measure(page, web) for page in sorted((web / "templates").glob("*.html"))]
    assert len(rows) == 13
    assert module.check(rows) == 0


def test_budget_command_returns_failure_for_an_oversized_asset(tmp_path, monkeypatch):
    module = tool()
    templates = tmp_path / "web/templates"
    templates.mkdir(parents=True)
    (templates / "index.html").write_text('<script src="big.js"></script>')
    asset = templates / "big.js"
    asset.write_text(" " * (module.JS_LIMIT + 1))
    monkeypatch.setattr(module, "__file__", str(tmp_path / "scripts/check-frontend-budget.py"))
    assert module.main() == 1
    asset.write_text("// small")
    assert module.main() == 0
