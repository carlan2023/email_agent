"""Lead Desk: the review and approval dashboard (FastAPI, server-rendered)."""
import html
import os
import secrets
import threading
from datetime import datetime

from fastapi import Depends, FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import config, engine, llm, store

app = FastAPI(title="IQS Lead Desk")
security = HTTPBasic()

STAGES = [
    ("new", "New"), ("working", "Claude working"), ("awaiting_approval", "Awaiting approval"),
    ("info_requested", "Details requested"), ("proposal_sent", "Proposal sent"), ("following_up", "Following up"),
    ("in_discussion", "In discussion"), ("won", "Won"), ("lost", "Lost"), ("cold", "Cold"),
]
STAGE_LABEL = dict(STAGES)


def auth(c: HTTPBasicCredentials = Depends(security)):
    if not config.DASHBOARD_PASSWORD:
        raise HTTPException(503, "Set DASHBOARD_PASSWORD to use the dashboard")
    ok = secrets.compare_digest(c.username, config.DASHBOARD_USER) and \
        secrets.compare_digest(c.password, config.DASHBOARD_PASSWORD)
    if not ok:
        raise HTTPException(401, "Wrong user or password", headers={"WWW-Authenticate": "Basic"})
    return c.username


e = html.escape


def fmt(ts):
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts).astimezone(config.KAMPALA).strftime("%d %b %H:%M")
    except Exception:
        return ts


CSS = """
:root{--bg:#f3f5f8;--panel:#fff;--ink:#0f1b2d;--muted:#56637a;--line:#d3d9e2;--navy:#16325c;--soft:#e7edf6;
--ok:#1f7a4d;--okb:#e2f3e9;--warn:#95590a;--warnb:#fcefd8;--bad:#a3262e;--badb:#f9e2e3}
@media (prefers-color-scheme:dark){:root{--bg:#0c1422;--panel:#131e30;--ink:#e7ecf4;--muted:#9aa8bd;--line:#27354c;
--navy:#93b3e8;--soft:#1b2a44;--ok:#6fd19e;--okb:#153020;--warn:#f0b75e;--warnb:#35270f;--bad:#f08b91;--badb:#3a1a1d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px;display:grid;gap:18px}
a{color:var(--navy)}h1{margin:0;font-size:22px;color:var(--navy)}h2{margin:0 0 8px;font-size:16px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;align-items:center}
.chips{display:flex;flex-wrap:wrap;gap:8px;font-size:12px}.chip{border:1px solid var(--line);background:var(--panel);
padding:3px 10px;border-radius:99px}.panel{background:var(--panel);border:1px solid var(--line);padding:14px 16px}
.card{border:1px solid var(--line);border-left:4px solid var(--navy);padding:12px 14px;background:var(--panel);display:grid;gap:6px}
.card.review{border-left-color:var(--warn)}.muted{color:var(--muted);font-size:13px}.mono{font-family:Consolas,monospace}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}.scroll{overflow-x:auto}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;font-size:12px;background:var(--soft);color:var(--navy);white-space:nowrap}
.pill.warn{background:var(--warnb);color:var(--warn)}.pill.ok{background:var(--okb);color:var(--ok)}.pill.bad{background:var(--badb);color:var(--bad)}
button,.btn{font:inherit;font-size:13px;padding:5px 12px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer;border-radius:5px;text-decoration:none}
button.primary{background:var(--navy);color:var(--panel);border-color:var(--navy)}
form.inline{display:inline}.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=text],textarea{width:100%;font:inherit;padding:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
textarea{min-height:260px}.preview{border:1px solid var(--line);padding:12px;background:#fff;color:#000}
.err{background:var(--badb);color:var(--bad);padding:8px 12px}
"""


def page(title, body):
    return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' "
                        f"content='width=device-width,initial-scale=1'><title>{e(title)}</title><style>{CSS}</style>"
                        f"</head><body><div class='wrap'>{body}</div></body></html>")


def stage_pill(s):
    cls = {"awaiting_approval": "warn", "in_discussion": "warn", "won": "ok", "lost": "bad", "cold": "bad"}.get(s, "")
    return f"<span class='pill {cls}'>{e(STAGE_LABEL.get(s, s or ''))}</span>"


def header():
    errs = store.kv_get("errors", [])
    mode = "Kill switch ON: nothing goes to clients" if config.KILL_SWITCH else "Live"
    return (f"<header><div><h1>IQS Lead Desk</h1><div class='muted'>info@ and alan@ monitored every "
            f"{config.POLL_MINUTES} min</div></div><div class='chips'>"
            f"<span class='chip'>Last check {fmt(store.kv_get('last_cycle'))}</span>"
            f"<span class='chip'>{e(mode)}</span><span class='chip'>Next invoice {store.next_invoice_peek()}</span>"
            f"<form class='inline' method='post' action='/run'><button>Check mail now</button></form>"
            f"<a class='btn' href='/'>Home</a></div></header>"
            + (f"<div class='err'>Problems on last check: {e('; '.join(errs))}</div>" if errs else ""))


def job_card(j):
    lead = store.get_lead(j["lead_id"]) or {}
    atts = " ".join(f"<a href='/files/{e(j['id'])}/{e(a)}'>{e(a)}</a>" for a in j.get("attachments", []))
    review = f"<div><span class='pill warn'>Review: {e(j['needs_review'])}</span></div>" if j.get("needs_review") else ""
    return (f"<div class='card {'review' if j.get('needs_review') else ''}'>"
            f"<div class='row'><b>{e(lead.get('company') or j['to'])}</b><span class='pill'>{e(config.EMAIL_KINDS[j['kind']])}</span>"
            f"<span class='muted'>to {e(j['to'])}</span></div>"
            f"<div>{e(j['subject'])}</div>{review}"
            f"<div class='muted'>{e(llm.html_to_text(j['html'], 260))}</div>"
            + (f"<div class='muted'>Attachments: {atts}</div>" if atts else "")
            + (f"<div class='muted'>Claude's note: {e(lead.get('notes', ''))}</div>" if lead.get("notes") else "")
            + f"<div class='row'><a class='btn' href='/job/{e(j['id'])}'>Open, edit or reject</a>"
            f"<form class='inline' method='post' action='/job/{e(j['id'])}/approve'><button class='primary'>Approve and send</button></form>"
            f"</div></div>")


@app.get("/health")
def health():
    return JSONResponse({"ok": True, "last_cycle": store.kv_get("last_cycle"), "errors": store.kv_get("errors", [])})


@app.get("/", response_class=HTMLResponse)
def home(user=Depends(auth)):
    pending = store.jobs(status="pending")
    leads = store.all_leads()
    auto = store.autonomy()
    body = [header()]
    body.append(f"<section><h2>Needs your approval ({len(pending)})</h2>"
                + ("".join(job_card(j) for j in reversed(pending)) or "<div class='panel muted'>Nothing waiting.</div>")
                + "</section>")
    rows = "".join(
        f"<tr><td><a href='/lead/{e(l['id'])}'><b>{e(l.get('company') or l['email'])}</b></a>"
        f"<div class='muted'>{e(l['email'])}</div></td><td>{e(', '.join(l.get('standards') or []))}</td>"
        f"<td class='mono'>{e(str(l.get('fee_usd') or ''))}</td><td>{stage_pill(l.get('stage'))}"
        + (" <span class='pill warn'>paused</span>" if l.get("paused") else "")
        + (f"<div class='muted'>{e(l.get('error', ''))[:120]}</div>" if l.get("attempts") else "")
        + f"</td><td class='muted'>{fmt(l.get('received'))}</td><td class='muted'>{fmt(l.get('next_due'))}</td></tr>"
        for l in leads)
    body.append("<section class='panel'><h2>Leads</h2><div class='scroll'><table><tr><th>Client</th><th>Standards</th>"
                "<th>Fee USD</th><th>Stage</th><th>Received</th><th>Next follow-up</th></tr>"
                + (rows or "<tr><td colspan=6 class='muted'>No leads yet.</td></tr>") + "</table></div></section>")
    streaks = store.kv_get("streaks", {})
    arows = ""
    for k, label in config.EMAIL_KINDS.items():
        cur = auto.get(k, "review")
        s = streaks.get(k, 0)
        hint = (f"<span class='pill ok'>{s} approved unchanged: ready for auto</span>"
                if cur == "review" and s >= config.AUTO_GRADUATE_AFTER else f"<span class='muted'>{s} unchanged in a row</span>")
        nxt = "auto" if cur == "review" else "review"
        arows += (f"<tr><td>{e(label)}</td><td>{'Sends automatically' if cur == 'auto' else 'Waits for you'}</td>"
                  f"<td>{hint}</td><td><form class='inline' method='post' action='/autonomy'>"
                  f"<input type='hidden' name='kind' value='{k}'><input type='hidden' name='value' value='{nxt}'>"
                  f"<button>{'Let it send automatically' if nxt == 'auto' else 'Require my approval'}</button></form></td></tr>")
    body.append("<section class='panel'><h2>Autonomy</h2><div class='muted'>Anything Claude flags for review, or any "
                "lead you pause, still waits for you.</div><div class='scroll'><table>" + arows + "</table></div></section>")
    msgs = store.recent_messages(40)
    mrows = "".join(
        f"<tr><td class='muted'>{datetime.fromtimestamp((m['received_ms'] or 0) / 1000, config.KAMPALA).strftime('%d %b %H:%M')}</td>"
        f"<td>{e(m['mailbox'])} {e(m['folder'])}</td><td>{e(m['from_addr'] or '')}</td><td>{e(m['subject'] or '')}</td>"
        f"<td class='muted'>{e({0: 'queued', 2: 'before go-live'}.get(m['handled'], m['note'] or ''))}</td><td>"
        + (f"<form class='inline' method='post' action='/message/{e(m['id'])}/lead'><button>Treat as lead</button></form>"
           if m["folder"] == "inbox" and not m.get("lead_id") else "") + "</td></tr>" for m in msgs)
    body.append("<section class='panel'><h2>Recent mail and what happened to it</h2><div class='scroll'><table>"
                "<tr><th>Received</th><th>Box</th><th>From</th><th>Subject</th><th>Outcome</th><th></th></tr>"
                + mrows + "</table></div></section>")
    return page("IQS Lead Desk", "".join(body))


@app.get("/job/{jid}", response_class=HTMLResponse)
def job_page(jid: str, user=Depends(auth)):
    j = store.get_job(jid) or {}
    if not j:
        raise HTTPException(404)
    atts = " ".join(f"<a href='/files/{e(jid)}/{e(a)}'>{e(a)}</a>" for a in j.get("attachments", []))
    editable = j["status"] == "pending"
    body = header() + (
        f"<section class='panel'><h2>{e(config.EMAIL_KINDS[j['kind']])} for {e(j.get('company') or j['to'])}</h2>"
        f"<div class='muted'>Status: {e(j['status'])} | to {e(j['to'])}"
        + (f" | cc {e(j['cc'])}" if j.get("cc") else "") + "</div>"
        + (f"<p><span class='pill warn'>Review: {e(j['needs_review'])}</span></p>" if j.get("needs_review") else "")
        + (f"<p>Attachments: {atts}</p>" if atts else "")
        + f"<div class='preview'>{j['html']}</div></section>")
    if editable:
        body += (f"<section class='panel'><h2>Edit, then approve</h2><form method='post' action='/job/{e(jid)}/approve'>"
                 f"<p><input type='text' name='to' value='{e(j['to'])}'></p>"
                 f"<p><input type='text' name='subject' value='{e(j['subject'])}'></p>"
                 f"<p><textarea name='body'>{e(llm.html_to_text(j['html'], 20000))}</textarea></p>"
                 f"<button class='primary'>Approve and send</button></form></section>"
                 f"<section class='panel'><h2>Reject</h2><form method='post' action='/job/{e(jid)}/reject'>"
                 f"<p><textarea name='note' style='min-height:90px' placeholder='What should change? Claude redoes it "
                 f"with your note. Leave empty to just discard.'></textarea></p>"
                 f"<div class='row'><button name='redo' value='1' class='primary'>Redo with my note</button>"
                 f"<button name='redo' value='0'>Discard</button></div></form></section>")
    return page("Review email", body)


@app.post("/job/{jid}/approve")
def approve(jid: str, to: str = Form(None), subject: str = Form(None), body: str = Form(None), user=Depends(auth)):
    j = store.get_job(jid)
    if not j or j["status"] != "pending":
        raise HTTPException(409, "This email is no longer waiting for approval")
    edited = False
    if to is not None and to.strip() and to.strip() != j["to"]:
        j["to"], edited = to.strip(), True
    if subject is not None and subject.strip() and subject.strip() != j["subject"]:
        j["subject"], edited = engine.clean(subject.strip()), True
    if body is not None and body.strip() != llm.html_to_text(j["html"], 20000).strip():
        j["html"], edited = llm.text_to_html(engine.clean(body)), True
    j["edited"], j["approved_by"], j["approved_at"] = edited, "allan", store.now()
    store.save_job(j, status="approved")
    streaks = store.kv_get("streaks", {})
    streaks[j["kind"]] = 0 if edited else streaks.get(j["kind"], 0) + 1
    store.kv_set("streaks", streaks)
    threading.Thread(target=engine.cycle, kwargs={"steps": ("send",)}, daemon=True).start()
    return RedirectResponse("/", status_code=303)


@app.post("/job/{jid}/reject")
def reject(jid: str, note: str = Form(""), redo: str = Form("0"), user=Depends(auth)):
    j = store.get_job(jid)
    if not j or j["status"] != "pending":
        raise HTTPException(409)
    j["rejected_note"] = note
    store.save_job(j, status="rejected")
    streaks = store.kv_get("streaks", {})
    streaks[j["kind"]] = 0
    store.kv_set("streaks", streaks)
    lead = store.get_lead(j["lead_id"])
    if lead:
        store.event(lead, f"You rejected: {j['subject']}" + (f" ({note})" if note else ""))
        if redo == "1":
            task = "new_lead" if j["kind"] in ("proposal", "request_form") else "client_reply"
            lead["pending_task"] = {"task": task, "feedback": note}
            if task == "client_reply":
                lead["pending_reply"] = j.get("reply_to_row") or (lead.get("message_rows") or [""])[-1]
            lead["attempts"] = 0
        elif lead.get("stage") == "awaiting_approval":
            lead["stage"] = "in_discussion"
        store.save_lead(lead)
    return RedirectResponse("/", status_code=303)


@app.get("/lead/{lid}", response_class=HTMLResponse)
def lead_page(lid: str, user=Depends(auth)):
    l = store.get_lead(lid)
    if not l:
        raise HTTPException(404)
    facts = "".join(f"<tr><th>{e(k)}</th><td>{e(str(l.get(k) if not isinstance(l.get(k), list) else ', '.join(l.get(k))))}</td></tr>"
                    for k in ("company", "contact_name", "email", "phone", "website", "standards", "service", "summary",
                              "fee_usd", "weeks", "ref", "invoice_no", "source", "notes", "needs_review", "cost_usd") if l.get(k))
    fu = "".join(f"<li>Day {f['day']} {e(f['kind'])}: {fmt(f['due'])} "
                 f"{'(done)' if f.get('done') and not f.get('skipped') else '(skipped: ' + e(f['skipped']) + ')' if f.get('skipped') else ''}</li>"
                 for f in l.get("followups", []))
    ev = "".join(f"<tr><td class='muted'>{fmt(x['t'])}</td><td>{e(x['what'])}</td></tr>" for x in reversed(l.get("events", [])))
    jobs = "".join(f"<tr><td class='muted'>{fmt(j.get('sent_at') or '')}</td><td>{e(config.EMAIL_KINDS[j['kind']])}</td>"
                   f"<td><a href='/job/{e(j['id'])}'>{e(j['subject'])}</a></td><td>{e(j['status'])}</td></tr>"
                   for j in store.jobs(lead_id=lid))
    acts = "".join(f"<form class='inline' method='post' action='/lead/{e(lid)}/action'><input type='hidden' name='what' "
                   f"value='{a}'><button>{lbl}</button></form>" for a, lbl in (
                       ("won", "Mark won"), ("lost", "Mark lost"), ("pause", "Resume" if l.get("paused") else "Pause"),
                       ("rebuild", "Rebuild proposal"), ("reopen", "Reopen")))
    body = header() + (
        f"<section class='panel'><h2>{e(l.get('company') or l['email'])} {stage_pill(l.get('stage'))}</h2>"
        f"<div class='row'>{acts}</div><table>{facts}</table></section>"
        f"<section class='panel'><h2>Emails</h2><table>{jobs or '<tr><td class=muted>None yet</td></tr>'}</table></section>"
        f"<section class='panel'><h2>Follow-ups</h2><ul>{fu or '<li class=muted>None scheduled</li>'}</ul></section>"
        f"<section class='panel'><h2>History</h2><table>{ev}</table></section>")
    return page(l.get("company") or "Lead", body)


@app.post("/lead/{lid}/action")
def lead_action(lid: str, what: str = Form(...), user=Depends(auth)):
    l = store.get_lead(lid)
    if not l:
        raise HTTPException(404)
    if what in ("won", "lost"):
        l["stage"] = what
        engine.cancel_followups(l, f"marked {what} by Allan")
    elif what == "pause":
        l["paused"] = not l.get("paused")
        store.event(l, "Paused by Allan" if l["paused"] else "Resumed by Allan")
    elif what == "rebuild":
        l["pending_task"], l["attempts"] = {"task": "new_lead", "feedback": "Rebuild requested by Allan"}, 0
    elif what == "reopen":
        l["stage"], l["attempts"] = "in_discussion", 0
    store.event(l, f"Dashboard action: {what}")
    store.save_lead(l)
    return RedirectResponse(f"/lead/{lid}", status_code=303)


@app.post("/message/{rid}/lead")
def force_lead(rid: str, user=Depends(auth)):
    m = store.message(rid)
    if not m:
        raise HTTPException(404)
    store.kv_set("forced_rows", store.kv_get("forced_rows", []) + [rid])
    store.mark_message(rid, handled=0, note="sent back for processing by Allan")
    threading.Thread(target=engine.cycle, kwargs={"steps": ("sort", "claude", "send")}, daemon=True).start()
    return RedirectResponse("/", status_code=303)


@app.post("/autonomy")
def set_autonomy(kind: str = Form(...), value: str = Form(...), user=Depends(auth)):
    if kind not in config.EMAIL_KINDS or value not in ("auto", "review"):
        raise HTTPException(400)
    a = store.kv_get("autonomy", {})
    a[kind] = value
    store.kv_set("autonomy", a)
    return RedirectResponse("/", status_code=303)


@app.post("/run")
def run_now(user=Depends(auth)):
    threading.Thread(target=engine.cycle, daemon=True).start()
    return RedirectResponse("/", status_code=303)


@app.get("/files/{jid}/{name}")
def files(jid: str, name: str, user=Depends(auth)):
    p = os.path.join(store.job_dir(jid), os.path.basename(name))
    if not os.path.isfile(p):
        raise HTTPException(404)
    return FileResponse(p, filename=os.path.basename(name))
