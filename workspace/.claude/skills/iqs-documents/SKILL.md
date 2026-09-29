---
name: "iqs-documents"
description: "Build client-facing ISO certification documents for IQS Management Systems Limited (Infinity Quality Services), Kampala: proposals, proforma invoices, cover emails, recommendation letters, services agreements. Use whenever IQS, Infinity Quality Services, TNV Global, an ISO proposal or quotation, certification fees, or a returned certification application form comes up."
---

# IQS Client Documents

Client-facing documents for IQS Management Systems Limited, trading as Infinity Quality Services: an ISO certification consultancy in Kampala serving Uganda and East Africa.

## Companion bundle

The reference files, build scripts and assets live in the `iqs-documents` .skill zip the user uploads (it carries `scripts/helpers.js`, `scripts/build_invoice.py`, `assets/invoice-template.xlsx`, `assets/iqs-letterhead.png` and the V3 application form). Those cannot travel in this file. First move each session:

```bash
mkdir -p ~/skillcheck ~/build && cd ~/skillcheck && unzip -qo /mnt/user-data/uploads/iqs-documents*.skill
cd ~/build && cp ../skillcheck/iqs-documents/scripts/helpers.js ../skillcheck/iqs-documents/assets/iqs-letterhead.png . && npm install docx --silent
```

**The container resets between sessions.** Build scripts, node_modules and extracted files do not persist; only files copied to `/mnt/user-data/outputs` survive. Re-extract and reinstall before assuming anything is there. If the bundle is missing, a previously delivered IQS proposal and proforma invoice attached by the user can stand in: the letterhead is `word/media/image1.png` inside the proposal .docx (check it is 714 x 91), and the invoice .xlsx can be the base for a new invoice once every client field, line row, note and hyperlink is cleared. Otherwise say so and ask for the bundle rather than improvising a template or a letterhead.

**Reference build.** The Front Edge Group IMS proposal and invoice (ISO 9001/14001/45001/27001, ref IQS/2026/FRONTEDGE/IMS-01, invoice 2612) are the user's benchmark for structure, tables, fee layout and tone, with the layout rules below applied on top.

## Firm facts

- **Legal name**: IQS Management Systems Limited, trading as Infinity Quality Services
- **Address**: Plot 6J3, Conta Africa Zone, Kamwokya, Kampala, Uganda
- **Contact**: Info@IQSUganda.com | +256 707 068 533 | www.iqsuganda.com | TIN 1054662615
- **Bank**: Opportunity Bank, account name IQS Management Systems Ltd, account no 1325507670369
- **Certification partner**: TNV Global Ltd, IAS accredited, IAF MLA signatory. IQS is an Authorised Audit Partner.
- **Accreditation partner**: KENAS, for ISO/IEC 17025 laboratory work.

The V3 application form in the bundle carries a different address (Plot 26, Kira Road) and phone (+256 792 170 297). **Use the details above, not the ones on that form.** Confirmed with the user; do not silently switch on finding the discrepancy again. When sending the form alongside a proposal, tell the user its letterhead is out of date, since the two will disagree in the client's inbox.

**Team** (named on every document, no unnamed associates):
- Philip Lubega, CEO and Global Director. Lead Auditor ISO 9001, 14001, 45001, 27001. Lean Six Sigma Black Belt. MA International Business Development, University of Westminster.
- Allan Mitanda, Lead Auditor. Mechanical engineering degree, 4+ years auditing and implementing ISO 9001, 14001, 45001, 27001, 20000.
- Lawrence Mujurizi, Auditor and Documentation Specialist.

Some engagements run through **NAM Quality Management Systems Ltd** instead (same Kamwokya address, www.amqualitysystems.com, payments in UGX). When the user says the implementing body is NAM, swap the mark, cover, footer and team accordingly, and do not use the IQS letterhead. Shafik Makumba is a named NAM trainer.

## Letterhead

**Every IQS Word document carries the official letterhead as its page header**: `assets/iqs-letterhead.png` (714 x 91 px), the IQS logo with "IQS MANAGEMENT SYSTEMS LIMITED" and "Infinity Quality Services | Plot 6J3, Conta Africa Zone Kamwokya Kampala Uganda | www.iqsuganda.com" in a ruled frame. It replaces the text header mark from `helpers.js`, and goes on the first page as well as every following page. Stated by the user as a standing rule.

```js
const fs = require("fs");
const { Header, Paragraph, ImageRun, AlignmentType } = require("docx");
const LH = fs.readFileSync("iqs-letterhead.png");
const letterhead = () => new Header({ children: [new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 120 },
  children: [new ImageRun({ type: "png", data: LH, transformation: { width: 605, height: 77 } })],
})] });
// in assemble(): headers: { first: letterhead(), default: letterhead() }
```

605 x 77 keeps the aspect ratio and fits the 9070 dxa text width. Keep the page top margin at 1100 or more so the header does not crowd the cover title. Check the render: the header must appear on every page, unstretched.

## House rules

Each of these came from a real defect or a stated preference.

**Verify every fee in Python before building anything.** Line items must sum exactly to the stated total, phase subtotals must reconcile, instalments must be equal whole numbers summing to the total. Print the check. Never build first and check after.

**No em dashes or en dashes anywhere.** Not in prose, not as glyphs, not as blank-cell placeholders. Use colons, semicolons, or "to" for ranges. Verify at XML level after every build across the whole file, not just your own additions.

**Body text is black (000000), never grey.** Build hierarchy from size, weight and spacing.

**Table borders must be visible.** The stock `tbl`/`th`/`td` helpers draw a hairline under each row only. Wrap them with a full box (see Build stack) so every table reads as a grid.

**Timelines are always 6 to 8 weeks.** Never longer, whatever the scope. Four standards in eight weeks is achievable when built as one system; say what it depends on.

**Never include unverified names or bracketed placeholders.** No `[Client Name]`, no contact drawn from a stale directory. If no contact name is confirmed, address the company and open the email "Hello". Assert nothing about the client that research or the user did not supply.

**Always send a concise cover email with every document.** Model: thank them for their interest, say what is attached, one line on what the proposal covers and that the fee is inclusive of the certification audit, state the programme length in weeks, offer a call, sign off. Short. Collaborative, not instructing.

**Confirm the client's legal entity before researching or pricing.** A full set of documents was once built for the wrong company because a domain was inferred. Where the user supplies a URL, check it actually matches the entity: a UK parent and its Ugandan subsidiary are different clients, and a common name may have an unrelated namesake abroad. A tender-directory listing years out of date is not a basis for section 02; ask for the live site instead.

**Deliver the proposal and the invoice together.** Thin client details mean a minimal bill-to (company name plus "Kampala, Uganda"), not a withheld proforma. Hold the invoice only for a genuine two-option proposal with no single total.

**Do only what was asked.** If a build turns up a defect in earlier deliverables, report it in one line and ask before fixing or re-sending anything beyond the current request. The user watches token use closely.

**No contracting clauses in proposals.** No liability, validity, exclusions or terms sections. Contract language belongs in a services agreement, and only when asked for.

**Avoid clauses that contradict the offer.** With TNV fees bundled into IQS quotes, an impartiality clause arguing that a body cannot both consult and certify argues against the deal it sits in. State who certifies as plain fact.

## Workflow

1. **Read the input.** A returned application form is the richest source: `PdfReader(path).get_fields()` and keep fields whose `/V` is not `None`, `''` or `/Off`. A pasted client brief works too. For queued leads, read the memory file `iqs-quoting-queue` first.
2. **Research the client.** Fetch the URL given; do not guess domains. Capture what they actually do, their size, sector and customers. Where the only public trace is stale and the sector is unclear, ask for headcount, sites and a live URL before building.
3. **Triage the standards** (below). Quote only what can appear on a certificate.
4. **Verify the pricing in Python.** Phases, subtotals, total, instalments, integration saving.
5. **Build** with docx-js in Node, or `build_invoice.py` for invoices.
6. **Validate**: `python /mnt/skills/public/docx/scripts/office/validate.py FILE`
7. **Dash check** at XML level across every part.
8. **Render to PDF and read the extracted text.** Scan for sparse pages. Cell values passing does not mean the page reads correctly.
9. **Deliver** to `/mnt/user-data/outputs`, present the files, and write the cover email.

## Pricing

All figures USD, settleable in UGX at the prevailing rate on the date of payment.

**TNV fees go inside the quote.** Show TNV as a named line in the final phase and label the total "Total fee, inclusive of certification". Bands: roughly 800 to 1,300 for one standard, 1,200 to 2,100 for two, 2,000 to 2,400 for three, 2,900 to 3,000 for four; scale with size, sites and sector risk. Surveillance in years two and three is a separate recurring line.

**Phase weighting.** Training and auditing are the technical work and should dominate. A defensible split of the consultancy element (total minus TNV) is 10 / 25 / 30 / 15 / 20 across gap analysis, documentation and risk, implementation and training, internal audit, and management review and certification. Documentation lines 100 to 400; training and internal audit lines 400 to 750 where the total allows.

**Instalments.** 50 percent on written acceptance, 50 percent on completion of the internal audit phase. For audit-based engagements the second trigger is completion of Stage 2. Both must be equal whole numbers.

**Integration saving.** When quoting multiple standards, show what they would cost separately and the saving. Aim for 20 to 35 percent; above roughly 40 makes the price look implausible. Compare like with like. Where the saving arises only in consultancy effort, state it on the consultancy element rather than dressing up the total.

**Benchmark ladder.** Price against completed work rather than inventing a figure.

| Client | Scope | Fee |
|---|---|---|
| Engmiite | 9001, construction, 8 staff | 2,400 |
| Gulf ADZ | 9001, engineering, 10 staff | 2,500 |
| Frame Concepts | 9001, construction, 3 sites | 2,800 |
| Atacama | 27001 certification only | 2,900 |
| Wagtech Environmental Uganda | 9001, equipment supply and support | 3,000 |
| Semliner Xpress | 9001 alone | 3,000 |
| Katengeta | 9001/14001/45001 | 3,500 |
| Ever Rosy | 9001, 176 staff | 3,600 |
| Wazuri Medicare | 9001 + 45001, 19 staff | 3,600 |
| RTC Consultancy | 27001 alone, IT supply, 10 staff | 3,800 |
| Neptune Financial | 27001 alone, consultancy-led | 4,000 |
| Kenfreight | 45001 added to an existing 9001, logistics, 70 staff, 2 sites | 4,500 |
| WANA Solutions | IMS 9001/14001/45001 | 4,800 |
| AgroMax | IMS 9001/14001/45001, agribusiness | 4,900 |
| Afro Oxygen | 9001/14001/45001, gas manufacture, 12 staff | 5,000 |
| Semliner Xpress | 9001 + 27001 IMS | 5,150 |
| JM Construction | IMS 9001/14001/45001, roads, project sites | 5,200 |
| Axa Engineering | IMS 9001/14001/45001, power systems, under 15 staff, head office plus project sites | 5,200 |
| G-Unit Security | IMS 14001/45001, 600 staff, 150 sites | 5,800 |
| Flaxem | 9001 + 27001, ICT, 15 staff, 2 sites | 6,000 |
| Datanet.com | 9001 + 27001 IMS, ISP | 6,000 |
| AgroMax | 27001 + 9001 scoped to IT | 6,000 |
| Front Edge Group | 9001/14001/45001/27001, engineering, 10 staff, 1 site | 7,000 |
| Delta Bees | 9001/22000/14001/45001, honey processing, 33 staff | 8,000 |

Sanity check every new quote against per-standard rate and against a client of comparable size. A three-standard quote below a one-standard quote elsewhere in the book needs a reason. Where the user sets a figure above the ladder, build the document so the number is earned and say plainly that it sits above the book.

**Audit-based versus consultancy-led** are two different engagements, not two prices. Audit-based is auditor days at USD 350 per day under IAF MD 5, presented as Year 1 plus annual surveillance.

**In-house training** is priced per participant or per cohort against trainer days: four courses over seven trainer days landed at 2,600 individually and 2,300 as one mobilisation. Mirror the client's own table columns. Claim no external accreditation (first aid, live fire) unless the user confirms IQS holds it or delivers through a partner.

## Standards triage

Clients tick more boxes than can be certified. Quote only what will appear on a certificate, fold the rest in at no extra charge, and put a table in section 03 explaining each.

- **HACCP** is inside ISO 22000. A separate HACCP certificate duplicates it.
- **OHSAS 18001** is withdrawn and replaced by ISO 45001. No new certificates.
- **ISO 10002** complaints and **ISO 10004** satisfaction are guidance standards, built into the ISO 9001 system.
- **ISO/IEC 17025** is accreditation, not certification (KENAS, technical assessors). More expensive.
- **ISO 31000** is not certifiable. Frame as framework consultancy with no audit fee.
- **CE marking** is product conformity, not a management system.
- **FSSC 22000**, wanted by some EU retailers, is built on ISO 22000, so an ISO 22000 system is the foundation for it.

## Domain points that decide the fee

**Clause 8.3 design and development.** Always settle it. A supplier or distributor excludes it, justified in the scope statement. A manufacturer, design-and-build contractor, or anyone configuring solutions to a customer specification implements it in full. Where a firm does both, draw the boundary at the gap analysis. If ambiguous, make it a next step and a line in the cover email.

**Clause 8.4 externally provided processes.** Where the client outsources the thing customers judge them on, 8.4 becomes the centre of the system. Usually the strongest section 02 argument for suppliers, hubs, dealers and agents.

**Sites and headcount.** These drive audit duration under IAF MD 5 and multi-site sampling under IAF MD 1 (initial sample approximately the square root of the number of sites; head office every cycle). A contractor with project sites normally has a live project visited at Stage 2; price that visit into the TNV line. Where figures are missing or doubtful, price a single certified operation, add a "Basis of this quotation" note in section 07, and make confirming it a next step.

**Effective personnel.** Where many staff do similar repetitive work at comparable risk, the effective number falls well below headcount and audit days with it. The single largest lever on cost for labour-heavy clients.

**Requested audit dates** on forms are often days away. Say plainly it cannot be met and why (ISO/IEC 17021-1 requires a genuine Stage 1 to Stage 2 interval), and repeat it in the email.

**An existing certificate with another body.** Do not bury a TNV fee that silently assumes a transfer. Quote the new standard with TNV, leave the existing certificate where it is, and offer the transfer separately.

**ISO 9001:2026** was published 16 September 2026 (sixth edition). A three-year transition to approximately September 2029 is the planning assumption, subject to IAF confirmation. Changes are evolutionary: quality culture and ethical behaviour under leadership, risk and opportunity separated, climate change incorporated, quality policy tied to strategy. 2015 certificates stay valid through the transition; do not promise transition audit dates. A transition for a mature system is around 1,800 consultancy, roughly 20 percent less when run alongside a new implementation.

## Build stack

Node with docx-js. Structure every build as a shared house module plus a client body file, so a verified head is reused and only content changes.

`scripts/helpers.js` from the bundle gives tokens, `section`, `body`, `bullet`, `label`, `gap`, `rule`, `cell`, `numbering`. Wrap it in a `house.js` that adds, and export everything through it:

```js
const B = { style: BorderStyle.SINGLE, size: 4, color: INK, space: 0 };
const boxAll = { top: B, bottom: B, left: B, right: B, insideHorizontal: B, insideVertical: B };
// gtbl / gth / gtd: same shape as tbl/th/td but borders: boxAll and
// margins { top:100, bottom:100, left:120, right:120 }
```

Plus in `house.js`: the `letterhead()` header above, `buildCover({nameCaps, titleLines, fields, titleSize})` for the four-field cover grid, `signature()`, `assemble({ref, children, out})` for document options, letterhead header, footer and `Packer.toBuffer`, and fee-table row helpers `fee`, `feeHead`, `feeSub`, `feeTotal` on a 6870 / 2200 grid.

**Numbering restarts.** Two numbered lists sharing one numbering reference continue rather than restart. Register a second decimal reference (`iqs-numbers-b`) and a `numberedB` helper for section 09.

**Column widths must fit the header word.** "PERIOD" rendered as "PERIO / D" at 900 dxa and needed 1100. Widths total about 9070. Only the render shows this.

**Preview caveat.** LibreOffice has neither Cambria nor Georgia. Judge layout from previews, never typeface.

## Proposal structure

```
Cover (typographic, four-field grid)
01  Executive Summary              + "At a Glance" bullets
02  Understanding Your Requirement + "The Commercial Case"
03  What the Standard(s) Require   clause table, or the standards-triage table
04  Implementation Methodology     phase table + "How We Work"
05  Key Deliverables               category table
06  The IQS Team                   three named consultants
07  Commercial Proposal            itemised fee, integration saving, payment terms,
                                   included in the fee, ongoing, basis of quotation
08  Indicative Timeline            week-column Gantt + certification cycle
09  Next Steps                     numbered + signature block
```

Ten pages is the target, eleven the ceiling.

**Layout rules** (approved by the user after reviewing the Front Edge render):
- No page may carry a lone paragraph. The "Basis of this quotation" note sits inside section 07 directly after payment terms, never spilling onto its own page.
- The itemised fee table never breaks across pages: set `cantSplit` on every row and `keepNext` on every row paragraph except the last, so the phases, TNV line and total sit together. Start section 07 on a new page if that is what it takes.
- Any other table that must break repeats its header row (`tableHeader: true`); short tables (clause table, deliverables) are kept whole with `cantSplit` and `keepNext`.
- The cover has no dead band: the four-field grid sits under the title, followed by one plain sentence stating what the proposal covers and who certifies, then the firm block at the foot.
- Subheadings are bold navy at normal letter spacing, not widely tracked small caps.
- Section 09 closes on the offer of a call, placed after the signature block.

**Tone.** State scope positively. Say what makes the programme practical (one shared structure, one audit) rather than defending it against an imagined objection; avoid lines like "achievable only because" or "no firm could maintain".

**Section 02 is where a proposal is won.** Map what the client actually does against what the system must control, and lead with the one fact that explains why these standards fit this business: compressed gas cannot be judged by looking at it; a building is buried before it can be inspected; an implementation partner holds other organisations' financial data; for a company selling energy efficiency, ISO 14001 is the product rather than the overhead.

Where the client asks what documentation IQS needs, add a "What we will need from you" table to section 09, prefaced by the line that nothing needs preparing in advance.

**Two-option proposals**: comparison table in the executive summary, each option its own fee breakdown, a "how to choose" section, and "Option chosen" on the signature block. The invoice waits for the choice; say so.

**Do not include**: impartiality clauses, "Not Included" exclusion lists that read as contractual, validity statements, liability language.

## Invoice

Use `scripts/build_invoice.py`; do not hand-edit the template. `build()` requires `proposal_total` and raises on mismatch. It clears template rows 18 to 28, keeps only the "Invoice 1" sheet, and collapses column A.

**The template has a live hyperlink at B14 to a former client's address (`mailto:amumeya@waesol.com`).** A new email written to B14 replaces the text but keeps the link; an empty B14 gets backfilled from it by `recalc.py` and prints on the page. `verify()` catches neither. Strip it on every build, then fix the formats:

```python
for row in ws.iter_rows():
    for c in row:
        if getattr(c.hyperlink, "target", None): c.hyperlink = None
ws["G4"] = datetime.date(Y, M, D); ws["G4"].number_format = "dd-mmm-yy"
ws["G7"].number_format = "dd-mmm-yy"        # else due date prints US m/d/y
for r in range(18, 31): ws[f"D{r}"].number_format = "#,##0"   # else 2000 vs 9,000
```

Bill the **full engagement** with the phase breakdown and state the deposit in note 1. Notes 1 and 2 sit in single-line cells under about 65 characters; note 3 wraps.

Invoice numbers run sequentially (2601 upward through 2026, last used 2612); check before assigning.

## Validation loop

Run all of these, in order, every time.

```bash
python /mnt/skills/public/docx/scripts/office/validate.py FILE.docx
```

```python
# dash and placeholder check across every XML part
import zipfile, re
z = zipfile.ZipFile(path); em = en = 0
for n in [x for x in z.namelist() if x.endswith('.xml')]:
    for t in re.findall(r'<w:t[^>]*>(.*?)</w:t>', z.read(n).decode(), re.S):
        em += t.count(chr(8212)); en += t.count(chr(8211))
xml = z.read('word/document.xml').decode()
assert em == 0 and en == 0
assert len(re.findall(r'\[[A-Za-z ]+\]', xml)) == 0
```

```bash
python /mnt/skills/public/docx/scripts/office/soffice.py --headless --convert-to pdf FILE.docx
```

```python
# sparse page scan: any page under ~10 non-empty lines is a layout fault
pages = subprocess.run(['pdftotext','-layout',pdf,'-'],capture_output=True,text=True).stdout.split('\f')[:-1]
sparse = [i+1 for i,p in enumerate(pages) if len([l for l in p.split('\n') if l.strip()]) < 10]
```

For spreadsheets: **any openpyxl save drops cached formula values, so `recalc.py` must be the last write before `verify()`**, or it reports `None` and FAIL on a good file.

**Fixing pagination.** Fix sparse pages structurally: remove the forced break on the following section, or add one to the section that spills, or reduce cell padding. Only then shorten prose. Rescan after each change.

**Verify the render, not the source.** Read the extracted PDF text before delivering and grep it for any name or address that does not belong to this client. A wrapped header, a truncated note and a stale email from a template hyperlink all passed value checks and showed only in the render.

## Deliverables

| Type | Format | Notes |
|---|---|---|
| Proposal | .docx | 10 pages, 11 at most, letterhead on every page |
| Proforma invoice | .xlsx | Built on `assets/invoice-template.xlsx`, never from scratch |
| Cover email | message tool | Always, with every delivery |
| Training proposal | .docx | 7 to 9 pages, letterhead, mirror the client's course table |
| Recommendation letter | .docx | Letterhead; confirms engagement status to a third party |
| Services agreement | .docx | Letterhead; contract clauses belong here, not in proposals |

## Tone

Write for a commercially literate reader who is not an ISO specialist. Explain what a requirement means in their operations rather than quoting clause numbers at them. Prefer plain statements of fact over salesmanship. Never pad.

In the reply to the user, after delivering: state the fee and where it sits against the ladder, name every assumption and open question, and flag anything that would change the price. Keep it short. Do not recap the build steps.