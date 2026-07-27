#!/usr/bin/env python3
"""Drive Pipulate chat through raw-WebSocket and normal-UI lanes.

The harness answers one narrow question:

    Which WebSocket implementation actually receives browser chat frames?

It creates two independently witnessed lanes:

1. RAW:
   A fresh browser-side WebSocket sends directly to /ws. This bypasses
   sendSidebarMessage() and the existing sidebarWs object.

2. UI:
   Selenium fills #msg and clicks #send-btn, exercising the production
   pipulate.js path.

Chrome performance logging records Network.webSocket* events so the report
contains the actual transmitted and received frame payloads. Browser console
logs, the final DOM, and a screenshot are saved beside report.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


RAW_SOCKET_SCRIPT = r"""
const message = arguments[0];
const timeoutMs = arguments[1];
const done = arguments[arguments.length - 1];

let socket = null;
let finished = false;
let idleTimer = null;

const hardTimer = setTimeout(() => {
    finish(false, "hard timeout waiting for WebSocket response");
}, timeoutMs);

function finish(ok, error) {
    if (finished) return;
    finished = true;
    clearTimeout(hardTimer);
    if (idleTimer) clearTimeout(idleTimer);

    const result = {
        ok: ok,
        error: error,
        message: message,
        socket_url: socket ? socket.url : null,
        frames: window.__pipulateProbeFrames || []
    };

    try {
        if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
    } catch (_) {
        // The result is already complete.
    }

    done(result);
}

function armIdleFinish() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => finish(true, null), 1200);
}

window.__pipulateProbeFrames = [];

try {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${window.location.host}/ws`);

    socket.onopen = () => {
        window.__pipulateProbeFrames.push({
            direction: "event",
            payload: "OPEN"
        });
        socket.send(message);
        window.__pipulateProbeFrames.push({
            direction: "sent",
            payload: message
        });
    };

    socket.onmessage = event => {
        const payload = String(event.data);
        window.__pipulateProbeFrames.push({
            direction: "received",
            payload: payload
        });

        if (payload === "%%STREAM_END%%") {
            finish(true, null);
        } else if (payload !== "%%STREAM_START%%") {
            armIdleFinish();
        }
    };

    socket.onerror = () => {
        finish(false, "browser WebSocket error");
    };

    socket.onclose = event => {
        window.__pipulateProbeFrames.push({
            direction: "event",
            payload: `CLOSE code=${event.code} reason=${event.reason}`
        });
        if (!finished) armIdleFinish();
    };
} catch (error) {
    finish(false, String(error));
}
"""


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_driver(headless: bool) -> tuple[uc.Chrome, str]:
    effective_os = os.environ.get("EFFECTIVE_OS", "").lower()

    if not effective_os:
        import platform

        effective_os = platform.system().lower()

    browser_path: str | None = None
    driver_path: str | None = None

    if effective_os == "linux":
        browser_path = shutil.which("chromium") or shutil.which("chromium-browser")
        driver_path = shutil.which("undetected-chromedriver")

        if not browser_path:
            raise RuntimeError("No chromium or chromium-browser executable found.")

        if not driver_path:
            raise RuntimeError("No undetected-chromedriver executable found.")

    elif effective_os == "darwin":
        candidates = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        )
        browser_path = next((path for path in candidates if Path(path).exists()), None)

        if not browser_path:
            raise RuntimeError("Google Chrome was not found in /Applications.")

    else:
        raise RuntimeError(f"Unsupported EFFECTIVE_OS value: {effective_os!r}")

    profile_path = tempfile.mkdtemp(prefix="pipulate_chat_route_probe_")

    options = uc.ChromeOptions()
    options.set_capability(
        "goog:loggingPrefs",
        {
            "browser": "ALL",
            "performance": "ALL",
        },
    )
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1600,1200")

    driver = uc.Chrome(
        options=options,
        user_data_dir=profile_path,
        browser_executable_path=browser_path,
        driver_executable_path=driver_path,
    )
    return driver, profile_path


def run_raw_socket(
    driver: uc.Chrome,
    message: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    driver.set_script_timeout(timeout_seconds + 5)
    result = driver.execute_async_script(
        RAW_SOCKET_SCRIPT,
        message,
        int(timeout_seconds * 1000),
    )
    return result if isinstance(result, dict) else {"ok": False, "result": result}


def assistant_message_count(driver: uc.Chrome) -> int:
    return int(
        driver.execute_script(
            """
            return document.querySelectorAll(
                "#msg-list .message.assistant"
            ).length;
            """
        )
    )


def chat_text(driver: uc.Chrome) -> str:
    return str(
        driver.execute_script(
            """
            const element = document.getElementById("msg-list");
            return element ? element.innerText : "";
            """
        )
    )


def wait_for_ui_response(
    driver: uc.Chrome,
    before_assistant_count: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_text = ""
    stable_since: float | None = None

    while time.monotonic() < deadline:
        current_text = chat_text(driver)
        current_count = assistant_message_count(driver)

        if current_count > before_assistant_count:
            if current_text != last_text:
                last_text = current_text
                stable_since = time.monotonic()
            elif stable_since is not None and time.monotonic() - stable_since >= 1.2:
                return {
                    "ok": True,
                    "assistant_count": current_count,
                    "chat_text": current_text,
                }

        time.sleep(0.1)

    return {
        "ok": False,
        "error": "timeout waiting for an assistant message to settle",
        "assistant_count": assistant_message_count(driver),
        "chat_text": chat_text(driver),
    }


def run_ui_message(
    driver: uc.Chrome,
    message: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    before_count = assistant_message_count(driver)
    textarea = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.ID, "msg"))
    )
    send_button = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.ID, "send-btn"))
    )

    textarea.clear()
    textarea.send_keys(message)
    send_button.click()

    result = wait_for_ui_response(
        driver,
        before_assistant_count=before_count,
        timeout_seconds=timeout_seconds,
    )
    result["message"] = message
    return result


def websocket_performance_events(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for entry in entries:
        try:
            envelope = json.loads(entry["message"])
            event = envelope["message"]
        except (KeyError, TypeError, json.JSONDecodeError):
            continue

        method = event.get("method", "")
        if not method.startswith("Network.webSocket"):
            continue

        params = event.get("params", {})
        frame = params.get("response") or params.get("request") or {}

        events.append(
            {
                "method": method,
                "request_id": params.get("requestId"),
                "url": params.get("url"),
                "opcode": frame.get("opcode"),
                "mask": frame.get("mask"),
                "payload": frame.get("payloadData"),
                "timestamp": params.get("timestamp"),
            }
        )

    return events


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Drive and record Pipulate chat through two browser lanes."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:5001/",
        help="Running Pipulate URL.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Maximum seconds per submitted message.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the automated Chromium window.",
    )
    args = parser.parse_args()

    marker = f"CHAT_ROUTE_PROBE_{utc_stamp()}"
    output_dir = Path("data/chat_route_probe") / marker
    output_dir.mkdir(parents=True, exist_ok=False)

    driver: uc.Chrome | None = None
    profile_path: str | None = None

    report: dict[str, Any] = {
        "marker": marker,
        "url": args.url,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "raw_websocket": [],
        "ui": [],
    }

    try:
        driver, profile_path = build_driver(headless=not args.headed)
        driver.get(args.url)

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "msg"))
        )

        raw_messages = (
            f"[ls {marker}_RAW]",
            f"Test {marker}_RAW",
        )
        for message in raw_messages:
            report["raw_websocket"].append(
                run_raw_socket(
                    driver,
                    message=message,
                    timeout_seconds=args.timeout,
                )
            )

        # The normal sidebar socket receives broadcasts generated by the raw
        # lane too. Reload before exercising the UI so its DOM evidence begins
        # from a clean visual boundary.
        driver.refresh()
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "msg"))
        )

        ui_messages = (
            f"[ls {marker}_UI]",
            f"Test {marker}_UI",
        )
        for message in ui_messages:
            report["ui"].append(
                run_ui_message(
                    driver,
                    message=message,
                    timeout_seconds=args.timeout,
                )
            )

        performance_entries = driver.get_log("performance")
        browser_entries = driver.get_log("browser")

        report["cdp_websocket_events"] = websocket_performance_events(
            performance_entries
        )
        report["browser_console"] = browser_entries
        report["final_chat_text"] = chat_text(driver)
        report["completed_at"] = datetime.now(timezone.utc).isoformat()

        (output_dir / "performance.json").write_text(
            json.dumps(performance_entries, indent=2),
            encoding="utf-8",
        )
        (output_dir / "browser_console.json").write_text(
            json.dumps(browser_entries, indent=2),
            encoding="utf-8",
        )
        (output_dir / "page.html").write_text(
            driver.page_source,
            encoding="utf-8",
        )
        driver.save_screenshot(str(output_dir / "screenshot.png"))

    except Exception as exc:
        report["fatal_error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        raise

    finally:
        (output_dir / "report.json").write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

        if profile_path:
            shutil.rmtree(profile_path, ignore_errors=True)

        print(json.dumps(report, indent=2))
        print(f"\nREPORT_PATH={output_dir / 'report.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
