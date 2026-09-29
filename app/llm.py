"""Small, cheap Claude calls: triage of incoming mail and follow-up wording."""
import html as htmlmod
import json
import re

from . import config

import tempfile

from . import claude_cli

_tmp = tempfile.mkdtemp(prefix="iqs-llm-")


def html_to_text(h, limit=8000):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h or "")
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", h)
    t = htmlmod.unescape(re.sub(r"<[^>]+>", " ", h))
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t).strip()
    return t[:limit]


def text_to_html(t):
    paras = [p.strip() for p in re.split(r"\n\s*\n", t or "") if p.strip()]
    return "".join("<p>" + htmlmod.escape(p).replace("\n", "<br>") + "</p>" for p in paras)


def _json_call(system, user, model=None, max_tokens=1500):
    r = claude_cli.run(user, _tmp, model or config.FAST_MODEL, system=system, tools="", timeout=300)
    text = str(r.get("result") or "")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"model returned no JSON: {text[:200]}")
    return json.loads(m.group(0))


TRIAGE_SYSTEM = """You sort incoming email for IQS Management Systems Limited (Infinity Quality Services), an ISO
certification consultancy in Kampala. IQS sells ISO certification consultancy (9001, 14001, 45001, 27001, 22000,
17025 and others), gap analyses, audits and ISO training. Allan Mitanda is the lead auditor.

Return ONLY a JSON object:
{
 "category": "new_lead" | "client_reply" | "ignore",
 "reason": "one short line",
 "company": "", "contact_name": "", "email": "", "phone": "", "website": "",
 "standards": ["ISO 9001"], "service": "certification|training|audit|gap_analysis|other",
 "summary": "one line on what they want",
 "enough_to_quote": true|false,
 "reply_intent": "question|accept|negotiate|changes|form_returned|not_interested|out_of_office|meeting|other|none",
 "urgency": "normal|high"
}

Rules:
- new_lead: a person or organisation asking about IQS services, a quote, training or certification, a website
  contact-form submission, or a completed IQS application form. For website forms sent from a no-reply address,
  take the client's name, email and phone from the form body; "email" must be the client's own address.
- client_reply: only when KNOWN_LEAD is given, the sender is that lead, and it is a real reply.
  Automatic out-of-office replies are client_reply with reply_intent "out_of_office".
- ignore: newsletters, notifications, marketing, suppliers selling to IQS, job seekers, bounces, invoices from
  vendors, internal mail, anything unrelated to IQS services, and replies in an ongoing conversation about an
  existing engagement when KNOWN_LEAD is absent (Allan handles those himself).
- enough_to_quote: true only if the organisation's name, the standard(s) and at least headcount or a clear
  description of operations are present, or a completed application form is attached.
- Never invent a contact name; leave it empty if not stated. Leave unknown fields empty.
"""


def triage(msg, body_text, attachment_names, known_lead=None):
    user = (f"MAILBOX: {msg['mailbox']}\nFROM: {msg.get('from_addr')}\nTO: {msg.get('to_addr')}\n"
            f"SUBJECT: {msg.get('subject')}\nATTACHMENTS: {', '.join(attachment_names) or 'none'}\n")
    if known_lead:
        user += (f"KNOWN_LEAD: {known_lead.get('company')} | stage {known_lead.get('stage')} | "
                 f"{known_lead.get('summary', '')}\n")
    user += f"\nBODY:\n{body_text[:6000]}"
    return _json_call(TRIAGE_SYSTEM, user)


FOLLOWUP_SYSTEM = """You write short follow-up emails for Allan Mitanda, Lead Auditor at IQS Management Systems
Limited (Infinity Quality Services), Kampala, after a proposal or a request for details went unanswered.
Style: short (under 90 words), warm, collaborative, never pushy or instructing. Open with "Dear <first name>," only
if a confirmed contact name is given, otherwise "Hello,". Never use time-of-day greetings. Never use em dashes or en
dashes. No placeholders or square brackets. Plain paragraphs.
Sign off exactly:
Kind regards,
Allan Mitanda
Lead Auditor, IQS Management Systems Limited
+256 707 068 533 | www.iqsuganda.com
Return ONLY JSON: {"subject": "...", "body": "plain text with blank lines between paragraphs"}"""

FOLLOWUP_BRIEF = {
    "first": "Check the proposal arrived safely and offer a short call to walk through it.",
    "middle": "Add one genuinely useful point relevant to their sector or standard (for example what the first two "
              "weeks involve, or how the certification audit is scheduled), then offer a call.",
    "last": "A brief close-the-loop note: the proposal stays open, no pressure, Allan is happy to help whenever suits.",
    "form_first": "Gently check whether they had a chance to look at the application form, and offer to fill it in "
                  "together over a short call.",
    "form_last": "Brief, friendly last note: happy to prepare a quote whenever they are ready.",
}


def compose_followup(lead, brief_key, original_subject):
    user = (f"Company: {lead.get('company')}\nConfirmed contact name: {lead.get('contact_name') or 'none'}\n"
            f"Standards: {', '.join(lead.get('standards') or [])}\nWhat they asked for: {lead.get('summary')}\n"
            f"Programme length: {lead.get('weeks') or ''} weeks\nOriginal subject: {original_subject}\n"
            f"This follow-up should: {FOLLOWUP_BRIEF[brief_key]}\nSubject must be: Re: {original_subject}")
    try:
        j = _json_call(FOLLOWUP_SYSTEM, user, max_tokens=600)
        subject, body = j["subject"], j["body"]
    except Exception:
        greet = f"Dear {lead['contact_name'].split()[0]}," if lead.get("contact_name") else "Hello,"
        subject = f"Re: {original_subject}"
        body = (f"{greet}\n\nI hope you are well. I wanted to check whether you had a chance to look at what we sent "
                f"and whether a short call would help.\n\nKind regards,\nAllan Mitanda\nLead Auditor, IQS Management "
                f"Systems Limited\n+256 707 068 533 | www.iqsuganda.com")
    body = body.replace("—", ", ").replace("–", " to ")
    return subject, text_to_html(body)
