# IQS Lead Pipeline (hosted)

Runs on Railway around the clock. Your PC can be off.

## What it does

Every 10 minutes it:

1. **Reads new mail** in info@iqsuganda.com and alan.mitanda@iqsuganda.com (full messages and attachments), and
   the headers in alan@ Sent.
2. **Sorts each message** (Claude Haiku): new enquiry, reply from a client already in the pipeline, or ignore
   (newsletters, suppliers, job seekers, and conversations about work already under way that the pipeline did not
   start).
3. **Acts** (Claude Code with your `iqs-documents` skill, in its own container, on your Claude subscription):
   - New enquiry with enough detail: researches the client, prices against the ladder, builds the proposal (.docx)
     and proforma invoice (.xlsx), validates and renders them, and writes the cover email.
   - New enquiry without enough detail: writes a short reply attaching the application form.
   - Client reply: reads the whole conversation and the documents already sent, then writes the answer.
     It rebuilds the proposal when scope or price changes and marks the lead won or lost when the client says so.
4. **Sends from alan@**, or holds the email for your approval, depending on the autonomy settings.
5. **Follows up** on days 3, 7 and 14 after a proposal, and on days 4 and 10 after a form request. It stops as soon
   as the client replies. It marks the lead cold when every follow-up has gone unanswered.
6. **Notices mail you send yourself** from alan@ to a lead. It withdraws anything pending for that lead and starts
   the follow-up clock.
7. **Emails you a digest** every weekday at 07:00 Kampala time, including client email addresses.

Client mail goes out only on weekdays from 08:00 to 18:00 Kampala time. Anything you approve yourself goes out
immediately.

## The dashboard (Lead Desk)

Open your Railway URL and sign in with `DASHBOARD_USER` / `DASHBOARD_PASSWORD`.

- **Needs your approval**: every held email, with a preview and its attachments. You can approve and send, edit
  and send, redo it with a note (Claude rebuilds using your note), or discard it.
- **Leads**: stage, fee, next follow-up. Open a lead for its history, emails and follow-ups, and to mark it
  won or lost, pause it, rebuild the proposal or reopen it.
- **Autonomy**: each kind of email starts as "Waits for you". The panel counts how many you approved unchanged in a
  row. After 5 it shows "ready for auto" and one click lets that kind send on its own. Anything Claude flags for
  review still waits, whatever the setting.
- **Recent mail**: what happened to each message. Click "Treat as lead" if the sorter ignored a real enquiry.

Suggested order for going automatic: holding replies and form requests, then follow-ups, then simple replies,
then proposals. Leave complex replies (price, scope, acceptance) on review.

---

## Setup, step by step (about 45 minutes)

### Step 1. Add your skill bundle

Copy your `iqs-documents.skill` file (the zip you normally upload to Claude) into the `skill-bundle` folder of
this project. The pipeline cannot build documents without it. The skill instructions themselves are already in
`workspace/.claude/skills/iqs-documents/SKILL.md`. When you update the skill in Claude, replace that file too and
redeploy.

### Step 2. Get a Claude token from your subscription

The pipeline runs the official Claude Code tool on the server, signed in with your Claude subscription, so there
is no API bill. Its usage counts against the same limits as your own use of Claude.

1. On your PC, install Claude Code once (needs Node.js from https://nodejs.org):
   `npm install -g @anthropic-ai/claude-code`
2. Run `claude setup-token`. A browser window opens; sign in with the Claude account you pay for and approve.
3. The terminal prints a long token. Copy it. It is valid for one year and is not saved anywhere else.
4. Put it in Railway as `CLAUDE_CODE_OAUTH_TOKEN` (Step 6). Set a reminder to repeat this in a year.

Treat the token like a password: anyone who has it can use your Claude plan.

If you would rather pay per use and keep your plan limits free, set `ANTHROPIC_API_KEY` instead (from
https://console.anthropic.com, Settings > API Keys). About USD 2 to 6 per proposal; `MAX_BUILD_USD` caps it.

### Step 3. Collect your Zoho values

Open `C:\Users\ALLAN\.iqs-pipeline\config.json` in Notepad. For each mailbox you need `client_id`,
`client_secret`, `refresh_token` and `account_id`. If alan@ has no `refresh_token` yet, finish
`py zoho_bridge.py auth alan` first.

### Step 4. Deploy to Railway

With the Railway CLI, which you already have:

```
cd "<this folder>"
railway login
railway init            # create a new project, name it iqs-lead-pipeline
railway up              # uploads and builds (first build takes about 10 minutes)
```

Or through GitHub: push this folder to a private repository, then in Railway choose **New Project > Deploy from
GitHub repo**.

### Step 5. Add a volume (required)

In Railway, open the service, then **Settings > Volumes > Add Volume** (or right-click the service and choose
Attach Volume). Set the mount path to `/data`. Everything the pipeline remembers lives there: leads, emails,
documents and settings.

### Step 6. Set the variables

In the service, open **Variables > Raw Editor** and paste, with your values filled in:

| Variable | Where to get it |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Step 2 |
| `DASHBOARD_USER` | Your choice, for example `allan` |
| `DASHBOARD_PASSWORD` | A long password of your choice |
| `ZOHO_DC` | `com` (the same value as in config.json) |
| `ZOHO_INFO_CLIENT_ID`, `ZOHO_INFO_CLIENT_SECRET`, `ZOHO_INFO_REFRESH_TOKEN`, `ZOHO_INFO_ACCOUNT_ID` | config.json, the `info` block |
| `ZOHO_ALAN_CLIENT_ID`, `ZOHO_ALAN_CLIENT_SECRET`, `ZOHO_ALAN_REFRESH_TOKEN`, `ZOHO_ALAN_ACCOUNT_ID` | config.json, the `alan` block |
| `OWNER_EMAIL` | Where the digest goes: `alan.mitanda@iqsuganda.com` |
| `START_INVOICE` | The next unused invoice number, for example `2613` (this is read once, on the first run) |
| `PUBLIC_URL` | Step 7 |

The optional settings, with their defaults, are listed in `.env.example`. Railway redeploys automatically after
you save.

### Step 7. Give it a web address

Go to **Settings > Networking > Generate Domain**. Copy the address (for example
`https://iqs-lead-pipeline-production.up.railway.app`) into the `PUBLIC_URL` variable. Open it and sign in.

### Step 8. Switch off the PC bridge

The hosted service replaces the program on your PC. In Command Prompt:

```
schtasks /Delete /TN "IQS Mail Bridge" /F
```

### Step 9. Check it works

- `https://<your address>/health` should show `"ok": true`, `last_cycle` filled in, and no errors.
- On the dashboard, **Recent mail** should list your latest messages marked "before go-live". Existing mail is
  never acted on automatically. To process an old enquiry, click "Treat as lead".
- Send a test enquiry from a personal address to info@iqsuganda.com. Within about 15 minutes a proposal or a form
  request should wait under **Needs your approval**.

## Emergency stop

Set the variable `KILL_SWITCH=true`. Nothing goes to clients; mail is still read and drafts still appear on the
dashboard. To stop a single client, open the lead and click **Pause**.

## Where to look when something is off

- The dashboard's red banner shows the last errors.
- Railway: service **Logs**.
- For a lead where Claude failed: the lead page history shows the error. It retries up to 3 times, then stops;
  click **Reopen** or **Rebuild proposal** to try again.
- Claude's work folders stay on the volume at `/data/work/<lead>/`, including `agent.log`.
