"""Runs Claude (the Claude Code CLI, headless) in a sandboxed work folder that carries the iqs-documents skill.

Tasks:
  new_lead      research, price, build proposal + invoice (or ask for details) and write the cover email
  client_reply  read the client's reply in context and write the right response (may rebuild documents)
"""
import json
import os
import shutil
from datetime import datetime

from . import claude_cli, config, store

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_TEMPLATE = os.path.join(APP_DIR, "workspace")
BUNDLE_DIR = os.path.join(APP_DIR, "skill-bundle")


def _prepare(lead, task, inputs):
    ts = datetime.now(config.KAMPALA).strftime("%Y%m%d-%H%M%S")
    wd = os.path.join(config.DATA_DIR, "work", lead["id"], f"{task}-{ts}")
    shutil.copytree(WORKSPACE_TEMPLATE, wd, dirs_exist_ok=True)
    os.makedirs(os.path.join(wd, "input"), exist_ok=True)
    os.makedirs(os.path.join(wd, "out"), exist_ok=True)
    bl = os.path.join(wd, "bundle")
    if os.path.isdir(BUNDLE_DIR) and not os.path.exists(bl):
        os.symlink(BUNDLE_DIR, bl)
    # conversation so far
    for i, item in enumerate(inputs.get("messages", []), 1):
        d = os.path.join(wd, "input", f"{i:02d}-{item['direction']}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "message.txt"), "w", encoding="utf-8") as f:
            f.write(f"From: {item.get('from')}\nTo: {item.get('to')}\nDate: {item.get('date')}\n"
                    f"Subject: {item.get('subject')}\nMessage row id: {item.get('row_id', '')}\n\n{item.get('text', '')}")
        for p in item.get("files", []):
            if os.path.isfile(p):
                shutil.copy(p, d)
    # documents already sent to this client (for replies)
    prev = os.path.join(wd, "input", "previous-documents")
    for p in inputs.get("previous_files", []):
        if os.path.isfile(p):
            os.makedirs(prev, exist_ok=True)
            shutil.copy(p, prev)
    task_doc = {
        "task": task,
        "today": datetime.now(config.KAMPALA).strftime("%d %B %Y"),
        "next_invoice_number": store.next_invoice_peek(),
        "lead": {k: v for k, v in lead.items() if k not in ("events",)},
        "reply_to_row_id": inputs.get("reply_to_row_id", ""),
        "allan_feedback": inputs.get("feedback", ""),
        "autonomy": store.autonomy(),
    }
    with open(os.path.join(wd, "input", "task.json"), "w", encoding="utf-8") as f:
        json.dump(task_doc, f, indent=2, ensure_ascii=False)
    return wd


PROMPTS = {
    "new_lead": "A new IQS lead has arrived. Read CLAUDE.md, then input/task.json and every file under input/. "
                "Follow CLAUDE.md section 'Task: new_lead' exactly and finish by writing out/result.json.",
    "client_reply": "A client in the IQS pipeline has replied. Read CLAUDE.md, then input/task.json and every file "
                    "under input/ (oldest first). Follow CLAUDE.md section 'Task: client_reply' exactly and finish "
                    "by writing out/result.json.",
}


def run(lead, task, inputs, model=None, budget=None):
    """Returns (result_dict, workdir, cost_usd). Raises on failure."""
    wd = _prepare(lead, task, inputs)
    res = claude_cli.run(PROMPTS[task], wd, model or config.BUILD_MODEL,
                         budget=budget or (config.MAX_BUILD_USD if task == "new_lead" else config.MAX_REPLY_USD),
                         log_path=os.path.join(wd, "agent.log"))
    cost = float(res.get("total_cost_usd") or 0)
    day = datetime.now(config.KAMPALA).strftime("%Y-%m-%d")
    costs = store.kv_get("costs", {})
    costs[day] = round(costs.get(day, 0) + cost, 4)
    store.kv_set("costs", dict(list(costs.items())[-60:]))
    path = os.path.join(wd, "out", "result.json")
    if not os.path.isfile(path):
        detail = str(res.get("result", ""))[:200]
        raise RuntimeError(f"agent wrote no out/result.json ({detail}); see {wd}/agent.log")
    with open(path, encoding="utf-8") as f:
        out = json.load(f)
    return out, wd, cost
