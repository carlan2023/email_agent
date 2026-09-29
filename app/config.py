"""All settings come from environment variables (set them in Railway > Variables)."""
import os
from datetime import timedelta, timezone


def env(key, default=None):
    v = os.environ.get(key)
    return default if v is None or v.strip() == "" else v.strip()


def env_bool(key, default=False):
    return str(env(key, str(default))).lower() in ("1", "true", "yes", "on")


# Zoho
ZOHO_DC = env("ZOHO_DC", "com")
MAILBOXES = {
    "info": {
        "address": env("ZOHO_INFO_ADDRESS", "info@iqsuganda.com"),
        "client_id": env("ZOHO_INFO_CLIENT_ID"),
        "client_secret": env("ZOHO_INFO_CLIENT_SECRET"),
        "refresh_token": env("ZOHO_INFO_REFRESH_TOKEN"),
        "account_id": env("ZOHO_INFO_ACCOUNT_ID"),
    },
    "alan": {
        "address": env("ZOHO_ALAN_ADDRESS", "alan.mitanda@iqsuganda.com"),
        "client_id": env("ZOHO_ALAN_CLIENT_ID"),
        "client_secret": env("ZOHO_ALAN_CLIENT_SECRET"),
        "refresh_token": env("ZOHO_ALAN_REFRESH_TOKEN"),
        "account_id": env("ZOHO_ALAN_ACCOUNT_ID"),
    },
}
OWNER_EMAIL = env("OWNER_EMAIL", MAILBOXES["alan"]["address"])
OWN_ADDRESSES = {a.lower() for a in [MAILBOXES["info"]["address"], MAILBOXES["alan"]["address"], OWNER_EMAIL]}

# Claude
# Auth: CLAUDE_CODE_OAUTH_TOKEN (your subscription, from `claude setup-token`) or ANTHROPIC_API_KEY (pay per use)
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
BUILD_MODEL = env("BUILD_MODEL", "opus")      # proposals, invoices, client replies
FAST_MODEL = env("FAST_MODEL", "haiku")       # triage and follow-ups
MAX_BUILD_USD = float(env("MAX_BUILD_USD", "8"))  # cost cap per build, applies only with an API key
MAX_REPLY_USD = float(env("MAX_REPLY_USD", "3"))

# Behaviour
DATA_DIR = env("DATA_DIR", "/data")
POLL_MINUTES = int(env("POLL_MINUTES", "10"))
INITIAL_LOOKBACK_DAYS = int(env("INITIAL_LOOKBACK_DAYS", "3"))
START_INVOICE = int(env("START_INVOICE", "2613"))
FOLLOWUP_DAYS = [int(x) for x in env("FOLLOWUP_DAYS", "3,7,14").split(",")]
FORM_REMINDER_DAYS = [int(x) for x in env("FORM_REMINDER_DAYS", "4,10").split(",")]
COLD_AFTER_DAYS = int(env("COLD_AFTER_DAYS", "21"))
DIGEST_HOUR = int(env("DIGEST_HOUR", "7"))                   # Kampala time
BUSINESS_START, BUSINESS_END = 8, 18                          # outgoing client mail window, Kampala time
AUTO_GRADUATE_AFTER = int(env("AUTO_GRADUATE_AFTER", "5"))    # unedited approvals before auto is offered
KILL_SWITCH = env_bool("KILL_SWITCH", False)                  # true = nothing goes to clients at all

DASHBOARD_USER = env("DASHBOARD_USER", "allan")
DASHBOARD_PASSWORD = env("DASHBOARD_PASSWORD")
PUBLIC_URL = env("PUBLIC_URL", "")

KAMPALA = timezone(timedelta(hours=3))

# Kinds of outgoing email and their default autonomy. "review" waits on the dashboard; "auto" sends.
EMAIL_KINDS = {
    "proposal": "Proposal and invoice",
    "request_form": "Request for details / application form",
    "followup": "Follow-up after proposal",
    "form_reminder": "Reminder to return the form",
    "reply_simple": "Reply to a simple client question",
    "reply_complex": "Reply on price, scope, acceptance or complaints",
    "acknowledge": "Holding reply (we received your message)",
}
DEFAULT_AUTONOMY = {k: "review" for k in EMAIL_KINDS}
