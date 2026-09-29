"""One pipeline cycle: read mail, sort it, let Claude act, send what is approved, follow up, report."""
import json
import os
import re
import shutil
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

from . import agent, config, llm, store
from .zoho import Mailbox

CYCLE_LOCK = threading.Lock()
DASHES = {"—": ", ", "–": " to "}
CLIENT_KINDS = set(config.EMAIL_KINDS)


def log(msg):
    line = f"{datetime.now(config.KAMPALA).strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(os.path.join(config.DATA_DIR, "pipeline.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def now_ms():
    return int(time.time() * 1000)


def kampala_now():
    return datetime.now(config.KAMPALA)


def in_business_hours(t=None):
    t = t or kampala_now()
    return t.weekday() < 5 and config.BUSINESS_START <= t.hour < config.BUSINESS_END


def mail_dir(row_id):
    mb, mid = row_id.split(":", 1)
    return os.path.join(config.DATA_DIR, "mail", mb, mid)


def load_mail(row_id):
    d = mail_dir(row_id)
    p = os.path.join(d, "message.json")
    if not os.path.isfile(p):
        return {}, []
    with open(p, encoding="utf-8") as f:
        m = json.load(f)
    return m, [os.path.join(d, n) for n in m.get("attachments", [])]


def safe_name(n):
    return ("".join(c if (c.isalnum() or c in "-_.() ") else "_" for c in n).strip() or "file")[:120]


# ======================================================================= fetch
def fetch():
    go_live = store.kv_get("go_live_ms")
    if go_live is None:
        go_live = now_ms()
        store.kv_set("go_live_ms", go_live)
        log("First run: mail older than now is listed as backlog and not acted on.")
    lookback = now_ms() - config.INITIAL_LOOKBACK_DAYS * 86400000
    for name in ("info", "alan"):
        box = Mailbox(name)
        key = f"since:{name}:inbox"
        since = store.kv_get(key, lookback)
        newest = since
        for m in box.list_since("inbox", since):
            mid, fid = str(m["messageId"]), m["_folderId"]
            row_id = f"{name}:{mid}"
            rec = int(m.get("receivedTime", 0))
            newest = max(newest, rec)
            if store.message(row_id):
                continue
            d = mail_dir(row_id)
            os.makedirs(d, exist_ok=True)
            files = []
            try:
                html = box.content(fid, mid)
            except Exception as e:
                html = ""
                log(f"{row_id}: content failed: {e}")
            if str(m.get("hasAttachment", "0")) in ("1", "true", "True"):
                try:
                    for an, blob in box.attachments(fid, mid):
                        an = safe_name(an)
                        with open(os.path.join(d, an), "wb") as f:
                            f.write(blob)
                        files.append(an)
                except Exception as e:
                    log(f"{row_id}: attachments failed: {e}")
            with open(os.path.join(d, "message.json"), "w", encoding="utf-8") as f:
                json.dump({"from": m.get("fromAddress"), "sender": m.get("sender"), "to": m.get("toAddress"),
                           "cc": m.get("ccAddress"), "subject": m.get("subject"), "received_ms": rec,
                           "html": html, "attachments": files, "folder_id": fid, "thread_id": m.get("threadId")},
                          f, ensure_ascii=False)
            store.add_message({"id": row_id, "mailbox": name, "folder": "inbox", "message_id": mid,
                               "thread_id": m.get("threadId"), "from_addr": (m.get("fromAddress") or "").lower(),
                               "to_addr": m.get("toAddress"), "subject": m.get("subject"), "received_ms": rec,
                               "summary": (m.get("summary") or "")[:400], "dir": "in",
                               "handled": 0 if rec >= go_live else 2})
        store.kv_set(key, newest)

    # alan@ Sent: headers only, to notice mail Allan sends himself
    box = Mailbox("alan")
    key = "since:alan:sent"
    since = store.kv_get(key, lookback)
    newest = since
    for m in box.list_since("sent", since):
        rec = int(m.get("receivedTime", 0))
        newest = max(newest, rec)
        store.add_message({"id": f"alan:{m['messageId']}", "mailbox": "alan", "folder": "sent",
                           "message_id": str(m["messageId"]), "thread_id": m.get("threadId"),
                           "from_addr": (m.get("fromAddress") or "").lower(), "to_addr": m.get("toAddress"),
                           "subject": m.get("subject"), "received_ms": rec, "summary": (m.get("summary") or "")[:400],
                           "dir": "out", "handled": 0 if rec >= go_live else 2})
    store.kv_set(key, newest)


# ======================================================================= sort incoming mail
def new_lead_from(t, row, subject):
    email = (t.get("email") or row["from_addr"] or "").lower().strip()
    lead = {
        "id": store.unique_lead_id(t.get("company") or email.split("@")[-1].split(".")[0]),
        "company": t.get("company") or "", "contact_name": t.get("contact_name") or "",
        "email": email, "other_emails": [], "phone": t.get("phone") or "", "website": t.get("website") or "",
        "standards": t.get("standards") or [], "service": t.get("service") or "",
        "summary": t.get("summary") or "", "source": f"{row['mailbox']}@ " + (
            "website form" if "noreply" in (row["from_addr"] or "") or "no-reply" in (row["from_addr"] or "")
            else "email"),
        "stage": "new", "received": store.now(), "message_rows": [row["id"]], "first_subject": subject,
        "enough_to_quote": bool(t.get("enough_to_quote")), "paused": False, "followups": [], "attempts": 0,
    }
    store.event(lead, f"New enquiry via {row['mailbox']}@: {subject}")
    return lead


def process_incoming():
    for row in store.unhandled_messages():
        if row["folder"] == "sent":
            process_sent(row)
            continue
        try:
            if row["from_addr"] in config.OWN_ADDRESSES:
                store.mark_message(row["id"], note="own address")
                continue
            m, files = load_mail(row["id"])
            text = llm.html_to_text(m.get("html", "")) or row.get("summary") or ""
            known = store.lead_by_email(row["from_addr"])
            t = llm.triage(row, text, [os.path.basename(p) for p in files], known)
            cat = t.get("category")
            forced = store.kv_get("forced_rows", [])
            if row["id"] in forced:
                cat = "client_reply" if known else "new_lead"
                store.kv_set("forced_rows", [r for r in forced if r != row["id"]])
            if cat == "new_lead" and not known:
                known = store.lead_by_email(t.get("email"))
            if cat in ("new_lead", "client_reply") and known:
                handle_reply(known, row, t, m)
            elif cat == "new_lead":
                lead = store.save_lead(new_lead_from(t, row, row.get("subject") or ""))
                store.mark_message(row["id"], lead_id=lead["id"], note="new lead: " + (t.get("reason") or ""))
                log(f"new lead {lead['id']} from {row['from_addr']}")
            else:
                store.mark_message(row["id"], note="ignored: " + (t.get("reason") or ""))
        except Exception as e:
            log(f"sorting {row['id']} failed: {e}")
            store.mark_message(row["id"], handled=0, note=f"error: {e}"[:300])


def handle_reply(lead, row, t, m):
    intent = t.get("reply_intent") or "other"
    # the same enquiry sent to both info@ and alan@
    if lead.get("stage") == "new" and (row.get("subject") or "") == lead.get("first_subject"):
        lead["message_rows"].append(row["id"])
        store.save_lead(lead)
        store.mark_message(row["id"], lead_id=lead["id"], note="duplicate of enquiry")
        return
    lead.setdefault("message_rows", []).append(row["id"])
    store.event(lead, f"Client wrote ({intent}): {row.get('subject')}")
    if intent == "out_of_office":
        store.mark_message(row["id"], lead_id=lead["id"], note="out of office")
        store.save_lead(lead)
        return
    cancel_followups(lead, "client replied")
    for j in store.jobs(status="pending", lead_id=lead["id"]):
        if j["kind"] in ("followup", "form_reminder"):
            store.save_job(j, status="superseded")
    if lead.get("stage") in ("info_requested", "new") and (intent == "form_returned" or t.get("enough_to_quote")):
        lead["stage"] = "new"
        lead["enough_to_quote"] = True
        for k in ("company", "contact_name", "phone", "website"):
            if t.get(k) and not lead.get(k):
                lead[k] = t[k]
        if t.get("standards"):
            lead["standards"] = t["standards"]
        store.event(lead, "Details received, proposal will be prepared")
    else:
        lead["pending_reply"] = row["id"]
        lead["last_intent"] = intent
        if lead.get("stage") not in ("won", "lost"):
            lead["stage"] = "in_discussion"
    store.save_lead(lead)
    store.mark_message(row["id"], lead_id=lead["id"], note=f"client reply ({intent})")


def process_sent(row):
    """A message in alan@ Sent. If the pipeline did not send it, Allan wrote to the client himself."""
    tos = [a.strip().lower() for a in re.split(r"[,;]", row.get("to_addr") or "") if "@" in a]
    tos = [re.sub(r".*<([^>]+)>.*", r"\1", a) for a in tos]
    for addr in tos:
        lead = store.lead_by_email(addr)
        if not lead:
            continue
        ours = any(abs(int(j.get("sent_ms", 0)) - int(row["received_ms"])) < 15 * 60000
                   and j.get("subject") == row.get("subject") for j in store.jobs(status="sent", lead_id=lead["id"]))
        if ours:
            continue
        store.event(lead, f"Allan emailed the client directly: {row.get('subject')}")
        lead["last_outbound_ms"] = row["received_ms"]
        pend = store.jobs(status="pending", lead_id=lead["id"])
        for j in pend:
            store.save_job(dict(j, note="Allan replied from Zoho directly"), status="superseded")
        if any(j["kind"] == "proposal" for j in pend) or lead.get("stage") in ("awaiting_approval", "new"):
            if lead.get("stage") not in ("won", "lost"):
                lead["stage"] = "proposal_sent"
                lead["sent"] = store.now()
                schedule(lead, "followup", config.FOLLOWUP_DAYS, row.get("subject") or "")
        elif lead.get("stage") in ("proposal_sent", "following_up", "in_discussion"):
            cancel_followups(lead, "Allan wrote directly")
            schedule(lead, "followup", [4, 10], row.get("subject") or "")
        lead.pop("pending_reply", None)
        store.save_lead(lead)
    store.mark_message(row["id"], note="in Sent")


# ======================================================================= follow-up schedule
def schedule(lead, kind, days, subject):
    base = datetime.now(timezone.utc)
    lead["followups"] = [f for f in lead.get("followups", []) if f.get("done")]
    n = len(days)
    for i, d in enumerate(days):
        brief = ("first" if i == 0 else "last" if i == n - 1 else "middle")
        if kind == "form_reminder":
            brief = "form_first" if i < n - 1 else "form_last"
        lead["followups"].append({"kind": kind, "day": d, "due": (base + timedelta(days=d)).isoformat(timespec="seconds"),
                                  "done": False, "brief": brief, "subject": subject})
    lead["next_due"] = lead["followups"][-n]["due"] if n else ""


def cancel_followups(lead, why):
    changed = False
    for f in lead.get("followups", []):
        if not f.get("done"):
            f["done"], f["skipped"], changed = True, why, True
    lead["next_due"] = ""
    if changed:
        store.event(lead, f"Follow-ups stopped: {why}")


def run_followups():
    if not in_business_hours():
        return
    now = datetime.now(timezone.utc)
    for lead in store.all_leads():
        if lead.get("paused") or lead.get("stage") in ("won", "lost", "cold"):
            continue
        fl = lead.get("followups", [])
        due = [f for f in fl if not f.get("done") and datetime.fromisoformat(f["due"]) <= now]
        if not due:
            open_ = [f for f in fl if not f.get("done")]
            last = max([f.get("sent_at", "") for f in fl if f.get("sent_at")] or [""])
            if fl and not open_ and last and not lead.get("pending_reply") and lead.get("stage") in (
                    "proposal_sent", "following_up", "info_requested") and \
                    now - datetime.fromisoformat(last) > timedelta(days=config.COLD_AFTER_DAYS - max(config.FOLLOWUP_DAYS)):
                lead["stage"] = "cold"
                store.event(lead, "No reply after all follow-ups: marked cold")
                store.save_lead(lead)
            continue
        if store.jobs(status="pending", lead_id=lead["id"]) or store.jobs(status="approved", lead_id=lead["id"]):
            continue  # something is already waiting to go out
        f = due[0]
        subject, html = llm.compose_followup(lead, f["brief"], f["subject"] or lead.get("first_subject") or "")
        make_job(lead, {"kind": f["kind"], "to": lead["email"], "subject": subject, "html": html,
                        "attachments": [], "notes": f"Day {f['day']} {f['kind'].replace('_', ' ')}"}, None)
        f["done"], f["sent_at"] = True, now.isoformat(timespec="seconds")
        nxt = [x for x in fl if not x.get("done")]
        lead["next_due"] = nxt[0]["due"] if nxt else ""
        if lead["stage"] == "proposal_sent":
            lead["stage"] = "following_up"
        store.event(lead, f"Day {f['day']} follow-up prepared")
        store.save_lead(lead)


# ======================================================================= Claude tasks
def conversation(lead):
    items = []
    for rid in lead.get("message_rows", []):
        m, files = load_mail(rid)
        if not m:
            continue
        items.append({"direction": "client", "from": m.get("from"), "to": m.get("to"), "subject": m.get("subject"),
                      "date": datetime.fromtimestamp(m.get("received_ms", 0) / 1000, config.KAMPALA).isoformat(),
                      "ms": m.get("received_ms", 0),
                      "text": llm.html_to_text(m.get("html", ""), 20000), "files": files, "row_id": rid})
    for j in reversed(store.jobs(lead_id=lead["id"])):
        if j["status"] == "sent":
            items.append({"direction": "iqs", "from": config.MAILBOXES["alan"]["address"], "to": j["to"],
                          "subject": j["subject"], "date": j.get("sent_at", ""), "text": llm.html_to_text(j["html"]),
                          "files": [], "ms": j.get("sent_ms", 0)})
    items.sort(key=lambda x: x.get("ms") or 0)
    return items


def previous_files(lead):
    out = []
    for j in store.jobs(status="sent", lead_id=lead["id"]):
        out += [os.path.join(store.job_dir(j["id"]), a) for a in j.get("attachments", [])]
    return out


def run_claude_tasks(max_tasks=2):
    done = 0
    for lead in store.all_leads():
        if done >= max_tasks:
            break
        if lead.get("paused") or lead.get("attempts", 0) >= 3:
            continue
        if lead.get("pending_task"):
            task = lead["pending_task"]["task"]
            feedback = lead["pending_task"].get("feedback", "")
        elif lead.get("stage") == "new":
            task, feedback = "new_lead", ""
        elif lead.get("pending_reply"):
            task, feedback = "client_reply", ""
        else:
            continue
        if store.jobs(status="pending", lead_id=lead["id"]) and task != "client_reply":
            continue
        done += 1
        prev_stage = lead.get("stage")
        lead["stage"] = "working"
        store.save_lead(lead)
        try:
            inputs = {"messages": conversation(lead), "previous_files": previous_files(lead),
                      "reply_to_row_id": lead.get("pending_reply", ""), "feedback": feedback}
            out, wd, cost = agent.run(lead, task, inputs)
            lead = store.get_lead(lead["id"])
            apply_result(lead, out, wd, task, cost)
            lead.pop("pending_task", None)
            lead.pop("pending_reply", None)
            lead["attempts"] = 0
            store.save_lead(lead)
            log(f"{task} done for {lead['id']} (USD {cost:.2f})")
        except Exception as e:
            lead = store.get_lead(lead["id"])
            lead["stage"] = prev_stage
            lead["attempts"] = lead.get("attempts", 0) + 1
            lead["error"] = str(e)[:500]
            store.event(lead, f"{task} failed (attempt {lead['attempts']}): {str(e)[:200]}")
            store.save_lead(lead)
            log(f"{task} failed for {lead['id']}: {e}\n{traceback.format_exc()}")


LEAD_FIELDS = ("company", "contact_name", "phone", "website", "standards", "service", "fee_usd", "weeks", "ref",
               "summary", "needs_review", "next_action")


def apply_result(lead, out, wd, task, cost):
    upd = out.get("lead") or {}
    for k in LEAD_FIELDS:
        if upd.get(k) not in (None, ""):
            lead[k] = upd[k]
    if upd.get("invoice_no"):
        if int(upd["invoice_no"]) == store.next_invoice_peek():
            lead["invoice_no"] = store.next_invoice_take()
        else:
            lead["invoice_no"] = int(upd["invoice_no"])
            store.event(lead, f"Check: invoice number {upd['invoice_no']} differs from the register")
    if upd.get("stage") in ("won", "lost"):
        lead["stage"] = upd["stage"]
        store.event(lead, f"Marked {upd['stage']} from the client's reply (undo on the dashboard if wrong)")
        cancel_followups(lead, f"lead {upd['stage']}")
    if out.get("notes_for_allan"):
        lead["notes"] = out["notes_for_allan"]
        store.event(lead, "Note: " + out["notes_for_allan"][:300])
    lead["cost_usd"] = round(lead.get("cost_usd", 0) + cost, 2)
    emails = out.get("emails") or []
    for e in emails:
        make_job(lead, e, os.path.join(wd, "out"))
    if not emails:
        store.event(lead, f"{task}: no email needed")
    if lead.get("stage") == "working":
        lead["stage"] = "awaiting_approval" if store.jobs(status="pending", lead_id=lead["id"]) else (
            "in_discussion" if task == "client_reply" else "new")


def clean(s):
    for a, b in DASHES.items():
        s = (s or "").replace(a, b)
    return s


def make_job(lead, e, outdir):
    kind = e.get("kind") if e.get("kind") in CLIENT_KINDS else "reply_complex"
    doc = {"kind": kind, "to": e.get("to") or lead.get("email"), "cc": e.get("cc", ""),
           "subject": clean(e.get("subject")), "html": clean(e.get("html")), "attachments": [],
           "reply_to_row": e.get("reply_to") or "", "needs_review": e.get("needs_review") or "",
           "notes": e.get("notes", ""), "company": lead.get("company"), "edited": False}
    if not doc["to"] or not doc["subject"] or not doc["html"]:
        store.event(lead, "Claude produced an incomplete email; nothing queued")
        return None
    auto = (store.autonomy().get(kind) == "auto" and not doc["needs_review"] and not lead.get("needs_review")
            and not config.KILL_SWITCH)
    job = store.new_job(lead["id"], doc, status="approved" if auto else "pending")
    jd = store.job_dir(job["id"])
    for name in e.get("attachments", []) or []:
        src = os.path.join(outdir or "", name)
        if outdir and os.path.isfile(src):
            shutil.copy(src, os.path.join(jd, os.path.basename(name)))
            job["attachments"].append(os.path.basename(name))
        else:
            job["needs_review"] = (job["needs_review"] + "; " if job["needs_review"] else "") + f"missing file {name}"
    job["auto"] = auto
    store.save_job(job, status="pending" if job["needs_review"] and auto else None)
    store.event(lead, f"{config.EMAIL_KINDS[kind]} {'queued to send' if auto else 'waiting for your approval'}")
    if lead.get("stage") not in ("won", "lost") and not auto and kind == "proposal":
        lead["stage"] = "awaiting_approval"
    return job


# ======================================================================= sending
def dispatch():
    if config.KILL_SWITCH:
        return
    box = None
    for job in reversed(store.jobs(status="approved")):
        manual = job.get("approved_by") == "allan"
        if not manual and not in_business_hours():
            continue
        lead = store.get_lead(job["lead_id"]) or {}
        if lead.get("paused") and not manual:
            continue
        box = box or Mailbox("alan")
        try:
            reply_mid = None
            if job.get("reply_to_row", "").startswith("alan:"):
                reply_mid = job["reply_to_row"].split(":", 1)[1]
            atts = []
            for n in job.get("attachments", []):
                with open(os.path.join(store.job_dir(job["id"]), n), "rb") as f:
                    atts.append((n, f.read()))
            box.send(job["to"], job["subject"], job["html"], cc=job.get("cc", ""), attachments=atts,
                     reply_to_message_id=reply_mid)
            job["sent_at"], job["sent_ms"] = store.now(), now_ms()
            store.save_job(job, status="sent")
            after_send(lead, job)
            log(f"sent {job['kind']} to {job['to']}: {job['subject']}")
        except Exception as e:
            job["tries"] = job.get("tries", 0) + 1
            job["error"] = str(e)[:400]
            store.save_job(job, status="failed" if job["tries"] >= 3 else "approved")
            log(f"send failed {job['id']}: {e}")


def after_send(lead, job):
    if not lead:
        return
    k = job["kind"]
    store.event(lead, f"Sent: {job['subject']}")
    lead["last_outbound_ms"] = job["sent_ms"]
    if k == "proposal":
        lead["stage"], lead["sent"] = "proposal_sent", job["sent_at"]
        schedule(lead, "followup", config.FOLLOWUP_DAYS, job["subject"])
    elif k == "request_form":
        lead["stage"] = "info_requested"
        schedule(lead, "form_reminder", config.FORM_REMINDER_DAYS, job["subject"])
    elif k in ("reply_simple", "reply_complex") and lead.get("stage") not in ("won", "lost"):
        lead["stage"] = "in_discussion"
        schedule(lead, "followup", [4, 10], job["subject"])
    store.save_lead(lead)


# ======================================================================= digest
def digest(force=False):
    t = kampala_now()
    today = t.strftime("%Y-%m-%d")
    if not force and (t.weekday() > 4 or t.hour < config.DIGEST_HOUR or store.kv_get("last_digest") == today):
        return
    leads = store.all_leads()
    pending = store.jobs(status="pending")
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    new = [l for l in leads if (l.get("received") or "") >= since]
    replies = [l for l in leads if l.get("stage") == "in_discussion"]
    sent = [j for j in store.jobs(status="sent") if (j.get("sent_at") or "") >= since]
    costs = store.kv_get("costs", {})
    week_cost = sum(v for k, v in costs.items() if k >= (t - timedelta(days=7)).strftime("%Y-%m-%d"))
    errs = store.kv_get("errors", [])

    def li(items):
        return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"

    parts = [f"<p>Hello Allan,</p><p>IQS lead pipeline for {t.strftime('%A %d %B')}.</p>"]
    if pending:
        parts.append(f"<p><b>Waiting for your approval ({len(pending)})</b></p>" + li(
            f"{j.get('company') or j['to']} ({j['to']}): {config.EMAIL_KINDS[j['kind']]}"
            + (f", review: {j['needs_review']}" if j.get("needs_review") else "") for j in pending))
    if replies:
        parts.append("<p><b>Client conversations open</b></p>" + li(
            f"{l.get('company') or l['email']} ({l['email']}): {l.get('last_intent', '')}" for l in replies))
    if new:
        parts.append("<p><b>New leads (24 hours)</b></p>" + li(
            f"{l.get('company') or 'Unknown company'} ({l['email']}): {l.get('summary', '')}" for l in new))
    if sent:
        parts.append("<p><b>Sent (24 hours)</b></p>" + li(f"{j['to']}: {j['subject']}" for j in sent))
    if errs:
        parts.append("<p><b>Problems</b></p>" + li(errs[-5:]))
    parts.append(f"<p>Claude usage last 7 days (API-equivalent value): USD {week_cost:.2f}. Next invoice number: {store.next_invoice_peek()}.</p>")
    if config.PUBLIC_URL:
        parts.append(f'<p>Dashboard: <a href="{config.PUBLIC_URL}">{config.PUBLIC_URL}</a></p>')
    Mailbox("alan").send(config.OWNER_EMAIL, f"IQS leads: {t.strftime('%d %b %Y')}", "".join(parts))
    store.kv_set("last_digest", today)
    log("digest sent")


# ======================================================================= cycle
def cycle(steps=("fetch", "sort", "claude", "followups", "send", "digest")):
    if not CYCLE_LOCK.acquire(blocking=False):
        return "busy"
    errors = []
    try:
        store.kv_set("cycle_started", store.now())
        for name, fn in (("fetch", fetch), ("sort", process_incoming), ("claude", run_claude_tasks),
                         ("followups", run_followups), ("send", dispatch), ("digest", digest)):
            if name not in steps:
                continue
            try:
                fn()
            except Exception as e:
                errors.append(f"{name}: {str(e)[:300]}")
                log(f"{name} FAILED: {e}\n{traceback.format_exc()}")
        store.kv_set("last_cycle", store.now())
        store.kv_set("errors", errors)
        return "ok" if not errors else "errors"
    finally:
        CYCLE_LOCK.release()


def scheduler_loop():
    time.sleep(5)
    while True:
        try:
            cycle()
        except Exception as e:
            log(f"cycle crashed: {e}")
        time.sleep(config.POLL_MINUTES * 60)
