"""Hold web/static/js/live.js to the /ws/capture protocol in docs/api-contract-en.md §7.

The client and the contract are written by different people; these checks make a mismatch fail the build
instead of failing on stage. They read the files as text, the same way tests/test_api_js.py does.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE_JS = ROOT / "web" / "static" / "js" / "live.js"
CONTRACT = ROOT / "docs" / "api-contract-en.md"

# The message types §7 defines, in both directions.
CONTRACT_TYPES = {"auth", "auth_ok", "start", "frame", "detect", "status", "stop"}
# Close codes §7 defines.
CONTRACT_CLOSE_CODES = {4401, 4408}


def section_7() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    return text[text.index("## 7. WebSocket protocol") : text.index("## 8.")]


def client_types() -> set[str]:
    source = LIVE_JS.read_text(encoding="utf-8")
    sent = set(re.findall(r'type:\s*"([a-z_]+)"', source))
    received = set(re.findall(r'msg\.type ===\s*"([a-z_]+)"', source))
    return sent | received


def test_section_7_is_present():
    assert "| client → server | `auth`" in section_7(), "the §7 table was not found"


def test_client_uses_only_message_types_the_contract_defines():
    unknown = sorted(client_types() - CONTRACT_TYPES)
    assert not unknown, f"live.js uses message types §7 does not define: {unknown}"


def test_client_sends_auth_first_and_never_puts_the_token_in_the_url():
    source = LIVE_JS.read_text(encoding="utf-8")
    assert '{ type: "auth", token:' in source, "live.js must send the auth message"
    assert "?token=" not in source, "§7 forbids the token in the query string"
    assert "auth_ok" in source, "live.js must wait for auth_ok before it sends start"


def test_client_handles_the_close_codes_the_contract_defines():
    source = LIVE_JS.read_text(encoding="utf-8")
    for code in CONTRACT_CLOSE_CODES:
        assert str(code) in source, f"live.js does not handle close code {code}"
    contract_codes = {int(c) for c in re.findall(r"`(44\d\d)`", section_7())}
    assert contract_codes == CONTRACT_CLOSE_CODES, f"§7 close codes changed: {contract_codes}"


def test_client_start_message_carries_the_fields_the_contract_names():
    source = LIVE_JS.read_text(encoding="utf-8")
    start = re.search(r'type: "start",([^}]*)\}', source)
    assert start, "live.js must send a start message"
    for field in ("session_id", "fps", "detect_interval_ms"):
        assert re.search(rf"\b{field}\b", start.group(1)), f"start message lacks {field}"


def test_client_reads_the_frame_and_detect_fields_the_contract_names():
    source = LIVE_JS.read_text(encoding="utf-8")
    for field in ("frame_id", "captured_at", "quality"):
        assert f"header?.{field}" in source or f"header.{field}" in source, (
            f"frame header lacks {field}"
        )
    assert "msg.boxes" in source and "msg.latency_ms" in source, (
        "detect must yield boxes and latency_ms"
    )
