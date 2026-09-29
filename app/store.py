"""SQLite state on the persistent volume. Leads and jobs are JSON documents for flexibility."""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from . import config

_lock = threading.RLock()
_conn = None


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn():
    global _conn
    if _conn is None:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(os.path.join(config.DATA_DIR, "pipeline.db"), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages(
            id TEXT PRIMARY KEY, mailbox TEXT, folder TEXT, message_id TEXT, thread_id TEXT,
            from_addr TEXT, to_addr TEXT, subject TEXT, received_ms INTEGER, summary TEXT,
            dir TEXT, handled INTEGER DEFAULT 0, lead_id TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS leads(id TEXT PRIMARY KEY, doc TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, lead_id TEXT, status TEXT, doc TEXT, created TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT);
        CREATE INDEX IF NOT EXISTS ix_msg_handled ON messages(handled);
        CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);
        """)
        _conn.commit()
    return _conn


# ------------------------------------------------------------------ kv
def kv_get(key, default=None):
    with _lock:
        r = conn().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


def kv_set(key, value):
    with _lock:
        conn().execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value)))
        conn().commit()


def next_invoice_peek():
    return kv_get("next_invoice", config.START_INVOICE)


def next_invoice_take():
    with _lock:
        n = next_invoice_peek()
        kv_set("next_invoice", n + 1)
        return n


def autonomy():
    a = dict(config.DEFAULT_AUTONOMY)
    a.update(kv_get("autonomy", {}))
    return a


# ------------------------------------------------------------------ messages
def add_message(m):
    with _lock:
        try:
            conn().execute("""INSERT INTO messages(id,mailbox,folder,message_id,thread_id,from_addr,to_addr,subject,
                              received_ms,summary,dir,handled) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (m["id"], m["mailbox"], m["folder"], m["message_id"], m.get("thread_id"), m.get("from_addr"),
                            m.get("to_addr"), m.get("subject"), m.get("received_ms", 0), m.get("summary"),
                            m.get("dir"), m.get("handled", 0)))
            conn().commit()
            return True
        except sqlite3.IntegrityError:
            return False


def unhandled_messages():
    with _lock:
        return [dict(r) for r in conn().execute(
            "SELECT * FROM messages WHERE handled=0 ORDER BY received_ms").fetchall()]


def mark_message(mid, handled=1, lead_id=None, note=None):
    with _lock:
        conn().execute("UPDATE messages SET handled=?, lead_id=COALESCE(?,lead_id), note=COALESCE(?,note) WHERE id=?",
                       (handled, lead_id, note, mid))
        conn().commit()


def message(mid):
    with _lock:
        r = conn().execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    return dict(r) if r else None


def recent_messages(limit=60):
    with _lock:
        return [dict(r) for r in conn().execute(
            "SELECT * FROM messages ORDER BY received_ms DESC LIMIT ?", (limit,)).fetchall()]


# ------------------------------------------------------------------ leads
def save_lead(lead):
    lead["updated"] = now()
    with _lock:
        conn().execute("INSERT INTO leads(id,doc,updated) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET "
                       "doc=excluded.doc, updated=excluded.updated", (lead["id"], json.dumps(lead), lead["updated"]))
        conn().commit()
    return lead


def get_lead(lid):
    with _lock:
        r = conn().execute("SELECT doc FROM leads WHERE id=?", (lid,)).fetchone()
    return json.loads(r["doc"]) if r else None


def all_leads():
    with _lock:
        return [json.loads(r["doc"]) for r in conn().execute("SELECT doc FROM leads ORDER BY updated DESC")]


def lead_by_email(addr):
    addr = (addr or "").lower().strip()
    if not addr:
        return None
    for l in all_leads():
        emails = {e.lower() for e in ([l.get("email")] + l.get("other_emails", [])) if e}
        if addr in emails:
            return l
    return None


def unique_lead_id(base):
    base = "".join(c if c.isalnum() else "-" for c in base.lower()).strip("-")[:40] or "lead"
    while "--" in base:
        base = base.replace("--", "-")
    lid, i = base, 2
    while get_lead(lid):
        lid, i = f"{base}-{i}", i + 1
    return lid


def event(lead, what):
    lead.setdefault("events", []).append({"t": now(), "what": what})


# ------------------------------------------------------------------ jobs (outgoing emails)
def job_dir(jid):
    d = os.path.join(config.DATA_DIR, "jobs", jid)
    os.makedirs(d, exist_ok=True)
    return d


def new_job(lead_id, doc, status="pending"):
    jid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    doc = dict(doc, id=jid, lead_id=lead_id)
    with _lock:
        conn().execute("INSERT INTO jobs(id,lead_id,status,doc,created,updated) VALUES(?,?,?,?,?,?)",
                       (jid, lead_id, status, json.dumps(doc), now(), now()))
        conn().commit()
    job_dir(jid)
    return doc


def save_job(doc, status=None):
    with _lock:
        if status:
            conn().execute("UPDATE jobs SET status=?, doc=?, updated=? WHERE id=?",
                           (status, json.dumps(doc), now(), doc["id"]))
        else:
            conn().execute("UPDATE jobs SET doc=?, updated=? WHERE id=?", (json.dumps(doc), now(), doc["id"]))
        conn().commit()


def get_job(jid):
    with _lock:
        r = conn().execute("SELECT status, doc FROM jobs WHERE id=?", (jid,)).fetchone()
    if not r:
        return None
    d = json.loads(r["doc"])
    d["status"] = r["status"]
    return d


def jobs(status=None, lead_id=None, limit=200):
    q, a = "SELECT status, doc FROM jobs WHERE 1=1", []
    if status:
        q += " AND status=?"
        a.append(status)
    if lead_id:
        q += " AND lead_id=?"
        a.append(lead_id)
    q += " ORDER BY created DESC LIMIT ?"
    a.append(limit)
    with _lock:
        out = []
        for r in conn().execute(q, a):
            d = json.loads(r["doc"])
            d["status"] = r["status"]
            out.append(d)
    return out
