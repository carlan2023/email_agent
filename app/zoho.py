"""Minimal Zoho Mail API client (OAuth refresh-token flow, standard library only)."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

DC = {
    "com": ("https://accounts.zoho.com", "https://mail.zoho.com"),
    "eu": ("https://accounts.zoho.eu", "https://mail.zoho.eu"),
    "in": ("https://accounts.zoho.in", "https://mail.zoho.in"),
    "com.au": ("https://accounts.zoho.com.au", "https://mail.zoho.com.au"),
    "jp": ("https://accounts.zoho.jp", "https://mail.zoho.jp"),
    "ca": ("https://accounts.zohocloud.ca", "https://mail.zohocloud.ca"),
    "sa": ("https://accounts.zoho.sa", "https://mail.zoho.sa"),
}


class ZohoError(RuntimeError):
    pass


class Mailbox:
    def __init__(self, name):
        self.name = name
        self.box = config.MAILBOXES[name]
        self.address = self.box["address"]
        self.accounts_url, self.api = DC[config.ZOHO_DC]
        self.token, self.token_exp = None, 0
        self.account_id = self.box.get("account_id")
        self._folders = None

    # ------------------------------------------------------------ auth + http
    def _refresh(self):
        for k in ("client_id", "client_secret", "refresh_token"):
            if not self.box.get(k):
                raise ZohoError(f"{self.name}: missing {k} (set ZOHO_{self.name.upper()}_{k.upper()})")
        q = urllib.parse.urlencode({
            "refresh_token": self.box["refresh_token"], "client_id": self.box["client_id"],
            "client_secret": self.box["client_secret"], "grant_type": "refresh_token",
        })
        req = urllib.request.Request(f"{self.accounts_url}/oauth/v2/token?{q}", data=b"", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                j = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise ZohoError(f"{self.name}: token refresh HTTP {e.code}: {e.read()[:300]!r}")
        if "access_token" not in j:
            raise ZohoError(f"{self.name}: token refresh failed: {j}")
        self.token = j["access_token"]
        self.token_exp = time.time() + int(j.get("expires_in", 3600)) - 120

    def call(self, method, path, params=None, body=None, raw=None, binary=False):
        if not self.token or time.time() > self.token_exp:
            self._refresh()
        url = self.api + path + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {"Authorization": "Zoho-oauthtoken " + self.token, "Accept": "application/json"}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        elif raw is not None:
            data, headers["Content-Type"] = raw, "application/octet-stream"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                content = r.read()
        except urllib.error.HTTPError as e:
            raise ZohoError(f"{self.name}: {method} {path} HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")
        if binary:
            return content
        return json.loads(content.decode() or "{}")

    # ------------------------------------------------------------ reads
    def ensure_account(self):
        if self.account_id:
            return self.account_id
        j = self.call("GET", "/api/accounts")
        want = self.address.lower()
        for a in j.get("data", []) or []:
            addrs = [str(a.get("primaryEmailAddress", "")).lower()] + [
                str(x.get("mailId", "")).lower() for x in (a.get("emailAddress") or [])]
            if want in addrs:
                self.account_id = str(a["accountId"])
        if not self.account_id and j.get("data"):
            self.account_id = str(j["data"][0]["accountId"])
        if not self.account_id:
            raise ZohoError(f"{self.name}: no mail account found")
        return self.account_id

    def folder_id(self, key):
        if self._folders is None:
            j = self.call("GET", f"/api/accounts/{self.ensure_account()}/folders")
            self._folders = {}
            for f in j.get("data", []) or []:
                self._folders.setdefault(str(f.get("folderName", "")).lower(), str(f["folderId"]))
                if f.get("folderType"):
                    self._folders.setdefault("type:" + str(f["folderType"]).lower(), str(f["folderId"]))
        return self._folders.get(key) or self._folders.get("type:" + key)

    def list_since(self, folder_key, since_ms, limit=50, max_pages=6):
        """Messages newer than since_ms, oldest first."""
        fid = self.folder_id(folder_key)
        if not fid:
            return []
        out, start = [], 1
        for _ in range(max_pages):
            j = self.call("GET", f"/api/accounts/{self.ensure_account()}/messages/view", params={
                "folderId": fid, "start": start, "limit": limit, "sortorder": "false", "includeto": "true"})
            batch = j.get("data", []) or []
            stop = False
            for m in batch:
                if int(m.get("receivedTime", 0)) <= since_ms:
                    stop = True
                    break
                m["_folderId"] = fid
                out.append(m)
            if stop or len(batch) < limit:
                break
            start += limit
        return list(reversed(out))

    def content(self, folder_id, message_id):
        j = self.call("GET", f"/api/accounts/{self.ensure_account()}/folders/{folder_id}/messages/{message_id}/content")
        return (j.get("data") or {}).get("content", "")

    def attachments(self, folder_id, message_id):
        """Yields (name, bytes)."""
        aid = self.ensure_account()
        info = self.call("GET", f"/api/accounts/{aid}/folders/{folder_id}/messages/{message_id}/attachmentinfo")
        for a in ((info.get("data") or {}).get("attachments") or []):
            blob = self.call("GET", f"/api/accounts/{aid}/folders/{folder_id}/messages/{message_id}/attachments/"
                                    f"{a['attachmentId']}", binary=True)
            yield a.get("attachmentName", "attachment"), blob

    # ------------------------------------------------------------ writes
    def upload(self, name, data):
        up = self.call("POST", f"/api/accounts/{self.ensure_account()}/messages/attachments",
                       params={"fileName": name}, raw=data)
        d = up.get("data")
        d = d[0] if isinstance(d, list) else d
        return {"storeName": d["storeName"], "attachmentPath": d["attachmentPath"],
                "attachmentName": d.get("attachmentName", name)}

    def send(self, to, subject, html, cc="", attachments=(), reply_to_message_id=None, draft=False):
        """attachments: list of (name, bytes). Replies in-thread when reply_to_message_id is an id in this mailbox."""
        body = {"fromAddress": self.address, "toAddress": to, "subject": subject,
                "content": html, "mailFormat": "html"}
        if cc:
            body["ccAddress"] = cc
        if attachments:
            body["attachments"] = [self.upload(n, b) for n, b in attachments]
        if draft:
            body["mode"] = "draft"
        aid = self.ensure_account()
        if reply_to_message_id and not draft:
            try:
                return self.call("POST", f"/api/accounts/{aid}/messages/{reply_to_message_id}",
                                 body=dict(body, action="reply"))
            except ZohoError:
                pass  # fall back to a new message with Re: subject
        return self.call("POST", f"/api/accounts/{aid}/messages", body=body)
