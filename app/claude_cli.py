"""Runs the official Claude Code CLI headless (claude -p).

Authentication, in this order:
  CLAUDE_CODE_OAUTH_TOKEN   your Claude Pro/Max subscription (token from `claude setup-token`), no API bill
  ANTHROPIC_API_KEY         pay-per-use API key, only if you set one
"""
import json
import os
import subprocess

AGENT_TOOLS = "Skill Read Write Edit Bash Glob Grep WebFetch WebSearch TodoWrite"


def auth_ok():
    return bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"))


def run(prompt, cwd, model, system=None, tools=None, budget=None, timeout=2700, log_path=None):
    """tools=None: full agent tool set with permissions bypassed (sandboxed container).
    tools="": no tools, a plain answer. Returns dict with result, total_cost_usd, is_error."""
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--model", model, "--setting-sources", "project"]
    if tools is None:
        cmd += ["--permission-mode", "bypassPermissions", "--allowedTools", AGENT_TOOLS]
    else:
        cmd += ["--tools", tools]
    if system:
        cmd += ["--system-prompt", system]
    if budget and os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        cmd += ["--max-budget-usd", str(budget)]
    env = dict(os.environ, IS_SANDBOX="1", DISABLE_AUTOUPDATER="1")
    if env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop("ANTHROPIC_API_KEY", None)  # use the subscription, never the API key, when a token is set
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"exit {p.returncode}\nSTDOUT:\n{p.stdout[-20000:]}\nSTDERR:\n{p.stderr[-5000:]}\n")
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    except (ValueError, IndexError):
        out = {}
    if not out:
        raise RuntimeError(f"claude CLI failed (exit {p.returncode}): {(p.stderr or p.stdout)[-400:]}")
    if out.get("is_error"):
        raise RuntimeError(f"claude CLI error: {str(out.get('result') or out.get('subtype'))[:400]}")
    return out
