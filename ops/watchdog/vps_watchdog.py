#!/usr/bin/env python3
"""
vps_watchdog.py
Deterministic DevOps Watchdog for SignalCraft and other VPS services.
- Tracks byte offsets to parse incremental logs efficiently.
- Detects log rotations to reset offsets.
- Deduplicates repetitive errors using MD5 hashes and cooldown periods.
- Warns about stale heartbeats (no activity on cron jobs).
- Pushes rich, actionable Telegram alerts.
"""

import os
import sys
import json
import time
import hashlib
import re
import urllib.request
import urllib.error

# Regex to catch typical error patterns. Expand as needed.
ERROR_PATTERN = re.compile(
    r"(?i)(\[ERROR\]|ERROR:|FATAL|CRITICAL|\bTraceback\b|Exception|Failed to|DH-\d+)"
)

# Directories & Configuration
DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(DIR, "config.json")
STATE_FILE = os.path.join(DIR, "state.json")
STATE_TMP = os.path.join(DIR, "state.tmp")
POLL_FILE = os.path.join(DIR, "poll_state.json")

# Default DEDUP cooldown (seconds)
ALERT_COOLDOWN_SEC = 3600
# Polling interval (seconds)
POLL_INTERVAL = 2
# Max log lines to return
MAX_LOG_LINES = 20
# Max message size (Telegram limit is ~4096)
MAX_MESSAGE_SIZE = 3500


def load_json(filepath, default):
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default


def save_state(state):
    """Safely saves state JSON using a temp file to prevent corruption on crash."""
    with open(STATE_TMP, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(STATE_TMP, STATE_FILE)


def send_telegram(config, message):
    """Sends a Telegram alert."""
    token = config.get("telegram_bot_token", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = config.get("telegram_chat_id", os.getenv("TELEGRAM_CHAT_ID", ""))

    # Try reading from Signalcraft .env if missing from config/env
    if not token or not chat_id:
        env_fallback = "/home/signalcraft/.env"
        if os.path.exists(env_fallback):
            with open(env_fallback, "r") as f:
                for line in f:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        token = line.strip().split("=")[1]
                    elif line.startswith("TELEGRAM_CHAT_ID="):
                        chat_id = line.strip().split("=")[1]

    if not token or not chat_id:
        print("Telegram Alert Skiped: No bot token or chat ID configured.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as _:
            pass
    except urllib.error.URLError as e:
        print(f"Failed to send Telegram alert: {e}")


def hash_error(log_name, error_str):
    """Generate an MD5 hash explicitly scoped to the log name."""
    clean_str = error_str.strip()
    return hashlib.md5(f"{log_name}::{clean_str}".encode("utf-8")).hexdigest()


def is_duplicate(state, error_hash, now):
    """Check if the error hash is currently in cooldown."""
    alerts = state.get("alerts", {})
    last_time = alerts.get(error_hash, 0)
    if now - last_time < ALERT_COOLDOWN_SEC:
        return True
    return False


def record_alert(state, error_hash, now):
    if "alerts" not in state:
        state["alerts"] = {}
    state["alerts"][error_hash] = now

    # Garbage collect old hashes to prevent memory bloat
    stale_keys = [
        k for k, v in state["alerts"].items() if now - v > ALERT_COOLDOWN_SEC * 2
    ]
    for k in stale_keys:
        del state["alerts"][k]


def get_log_file_path(service_name):
    """Map service name to log file path from config."""
    config = load_json(CONFIG_FILE, {})
    for log_cfg in config.get("logs", []):
        if log_cfg.get("name") == service_name:
            return log_cfg.get("path", "")
    return ""


def read_last_lines(filepath, n=20):
    """Read last n lines from a file efficiently."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            return "".join(lines[-n:])
    except Exception:
        return None


def handle_telegram_command(config, text):
    """Process Telegram bot commands and return response message."""
    parts = text.strip().split()
    if not parts:
        return None

    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None

    if cmd == "/logs":
        if not arg:
            available = [l.get("name", "?") for l in config.get("logs", [])]
            return (
                f"📋 Available logs:\n"
                + "\n".join(f"- {n}" for n in available)
                + f"\n\nUsage: /logs <service_name>"
            )

        filepath = get_log_file_path(arg)
        if not filepath:
            return f"❌ Unknown service: {arg}"

        content = read_last_lines(filepath, MAX_LOG_LINES)
        if content is None:
            return f"❌ Cannot read log file: {filepath}"

        truncated = content[:MAX_MESSAGE_SIZE]
        return f"🧾 Logs ({arg}, last {MAX_LOG_LINES} lines):\n```\n{truncated}```"

    elif cmd == "/errors":
        if not arg:
            return "Usage: /errors <service_name>"

        filepath = get_log_file_path(arg)
        if not filepath:
            return f"❌ Unknown service: {arg}"

        content = read_last_lines(filepath, 100)
        if content is None:
            return f"❌ Cannot read log file: {filepath}"

        error_lines = [l for l in content.splitlines() if ERROR_PATTERN.search(l)]
        if not error_lines:
            return f"✅ No errors found in last 100 lines of {arg}"

        return f"🚨 Errors ({arg}):\n" + "\n".join(
            f"- {l.strip()}" for l in error_lines[:20]
        )

    elif cmd == "/status":
        config = load_json(CONFIG_FILE, {})
        now = time.time()
        lines = ["📊 **System Status**\n"]

        for log_cfg in config.get("logs", []):
            name = log_cfg.get("name", "?")
            path = log_cfg.get("path", "")
            max_stale = log_cfg.get("max_stale_minutes", 0)

            if not os.path.exists(path):
                lines.append(f"❌ {name}: **MISSING**")
            else:
                mtime = os.path.getmtime(path)
                age_min = int((now - mtime) / 60)
                status = "✅" if age_min < max_stale else "⚠️"
                lines.append(f"{status} {name}: {age_min} min old")

        return "\n".join(lines)

    elif cmd == "/help":
        return """🤖 **Watchdog Commands:**

/logs <service> - Get last 20 log lines
/errors <service> - Get only error lines
/status - Show all monitored services
/help - Show this help

Examples:
/logs daily_update
/errors token_refresh
/status"""

    return f"Unknown command: {cmd}\nUse /help for available commands."


def poll_telegram_updates(config):
    """Poll Telegram for new bot commands using getUpdates."""
    token = config.get("telegram_bot_token", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = config.get("telegram_chat_id", os.getenv("TELEGRAM_CHAT_ID", ""))

    if not token or not chat_id:
        return

    # Try SignalCraft .env fallback
    if not token or not chat_id:
        env_fallback = "/home/signalcraft/.env"
        if os.path.exists(env_fallback):
            with open(env_fallback, "r") as f:
                for line in f:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        token = line.strip().split("=")[1]
                    elif line.startswith("TELEGRAM_CHAT_ID="):
                        chat_id = line.strip().split("=")[1]

    if not token or not chat_id:
        return

    poll_state = load_json(POLL_FILE, {"offset": 0})
    offset = poll_state.get("offset", 0)

    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=30"
        if offset > 0:
            url += f"&offset={offset}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if not data.get("ok"):
            return

        updates = data.get("result", [])
        if not updates:
            return

        for update in updates:
            msg = update.get("message", {})
            text = msg.get("text", "")
            if text.startswith("/"):
                response = handle_telegram_command(config, text)
                if response:
                    send_telegram(config, response)

        # Update offset to next update
        new_offset = updates[-1].get("update_id", 0) + 1
        with open(POLL_FILE, "w") as f:
            json.dump({"offset": new_offset}, f)

    except Exception as e:
        pass  # Silently skip polling errors


def process_log(log_cfg, state, now):
    name = log_cfg.get("name", "UnknownApp")
    path = log_cfg.get("path", "")
    max_stale_m = log_cfg.get("max_stale_minutes", 0)
    severity = log_cfg.get("severity", "ERROR")

    issues = []

    # 1. File Not Found Handling
    if not os.path.exists(path):
        issues.append(f"❌ Log file missing entirely: `{path}`")
        return issues

    # 2. Staleness / Beat Check
    mtime = os.path.getmtime(path)
    if max_stale_m > 0 and (now - mtime) > (max_stale_m * 60):
        # Prevent spamming heartbeat alerts by using a custom hash
        hb_hash = hash_error(name, "HEARTBEAT_DEAD")
        if not is_duplicate(state, hb_hash, now):
            issues.append(
                f"⚠️ Activity Dead: No writes in {(now - mtime) // 60} minutes!"
            )
            record_alert(state, hb_hash, now)

    # 3. Size and Rotation Tracking
    current_size = os.path.getsize(path)
    if "offsets" not in state:
        state["offsets"] = {}
    last_offset = state["offsets"].get(name, 0)

    # If the file shrank, it was log-rotated or truncated. Reset offset!
    if current_size < last_offset:
        last_offset = 0

    if current_size == last_offset:
        # No new changes
        return issues

    # 4. Incremental Log Scanning
    new_errors = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(last_offset)
            for line in f:
                if ERROR_PATTERN.search(line):
                    ehash = hash_error(name, line)
                    if not is_duplicate(state, ehash, now):
                        new_errors.append(line.strip()[:150])  # Truncate long traces
                        record_alert(state, ehash, now)

            # Update position after reading
            state["offsets"][name] = f.tell()
    except Exception as e:
        issues.append(f"⚠️ Permissions/Read Error on log file: {str(e)}")

    if new_errors:
        issues.append(f"**Found {len(new_errors)} new {severity}s:**")
        for err in new_errors:
            issues.append(f"- `{err}`")

    return issues


def main():
    config = load_json(CONFIG_FILE, {})
    if not config or "logs" not in config:
        print("Invalid or missing config.json")
        sys.exit(1)

    state = load_json(STATE_FILE, {"offsets": {}, "alerts": {}})
    now = time.time()

    # Optional startup ping
    # if state.get("is_first_run", True):
    #    send_telegram(config, "✅ *VPS Watchdog Started Successfully*\nMonitoring initialized.")
    #    state["is_first_run"] = False

    all_alerts = {}

    for log_cfg in config["logs"]:
        issues = process_log(log_cfg, state, now)
        if issues:
            all_alerts[log_cfg.get("name", "Unknown")] = issues

    save_state(state)

    # Poll for Telegram commands (non-blocking via short timeout)
    poll_telegram_updates(config)

    # Dispatch alerts aggregated by App
    if all_alerts:
        msg_lines = ["🚨 **VPS WATCHDOG ALERT** 🚨\n"]
        for app_name, warnings in all_alerts.items():
            msg_lines.append(f"**App**: `{app_name}`")
            msg_lines.extend(warnings)
            msg_lines.append("")

        msg_lines.append("📋 *View logs:* `/logs <service>`")
        msg_lines.append("📊 *Check status:* `/status`")
        send_telegram(config, "\n".join(msg_lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as fatal_err:
        # 5. Global Failure Wrapper
        fallback_cfg = load_json(CONFIG_FILE, {})
        send_telegram(
            fallback_cfg,
            f"💀 **WATCHDOG FATAL CRASH**\n`{str(fatal_err)}`\nWatchdog is offline!",
        )
        sys.exit(1)
