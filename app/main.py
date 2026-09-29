"""Entry point: starts the mail scheduler in the background and serves the dashboard."""
import os
import sys
import threading

import uvicorn

from . import config, engine, store


def check_config():
    missing = [] if (os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")) else [
        "CLAUDE_CODE_OAUTH_TOKEN"]
    missing += [k for k in ("DASHBOARD_PASSWORD",
                           "ZOHO_INFO_CLIENT_ID", "ZOHO_INFO_CLIENT_SECRET", "ZOHO_INFO_REFRESH_TOKEN",
                           "ZOHO_ALAN_CLIENT_ID", "ZOHO_ALAN_CLIENT_SECRET", "ZOHO_ALAN_REFRESH_TOKEN")
               if not os.environ.get(k)]
    if missing:
        engine.log("MISSING VARIABLES: " + ", ".join(missing))
        store.kv_set("errors", ["Missing variables: " + ", ".join(missing)])
    return not missing


def main():
    store.conn()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        # one-off: python -m app.main check   (tests Zoho access without acting on mail)
        from .zoho import Mailbox
        for n in ("info", "alan"):
            b = Mailbox(n)
            print(n, b.address, "account", b.ensure_account(), "inbox folder", b.folder_id("inbox"))
        return
    if check_config():
        threading.Thread(target=engine.scheduler_loop, daemon=True).start()
    uvicorn.run("app.web:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), log_level="warning")


if __name__ == "__main__":
    main()
