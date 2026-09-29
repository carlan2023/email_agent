"""Validate an IQS .docx: XML well-formed, no em/en dashes, no [Placeholders], render to PDF, sparse-page scan.
Usage: python tools/check_docx.py FILE.docx   (prints the rendered text; exit 1 on any failure)"""
import os
import re
import subprocess
import sys
import tempfile
import zipfile
import xml.dom.minidom

path = sys.argv[1]
fail = []
z = zipfile.ZipFile(path)
em = en = 0
for n in z.namelist():
    if not n.endswith((".xml", ".rels")):
        continue
    raw = z.read(n)
    try:
        xml.dom.minidom.parseString(raw)
    except Exception as e:
        fail.append(f"malformed XML in {n}: {e}")
    for t in re.findall(r"<w:t[^>]*>(.*?)</w:t>", raw.decode("utf-8", "replace"), re.S):
        em += t.count("—")
        en += t.count("–")
if em or en:
    fail.append(f"dashes found: {em} em, {en} en")
doc = z.read("word/document.xml").decode("utf-8", "replace")
ph = re.findall(r"\[[A-Za-z ]+\]", re.sub(r"<[^>]+>", "", doc))
if ph:
    fail.append(f"placeholders: {ph[:5]}")
if not any(n.startswith("word/media/") for n in z.namelist()):
    fail.append("no image in document: letterhead missing?")

out = tempfile.mkdtemp()
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", out, path],
               capture_output=True, timeout=240)
pdf = os.path.join(out, os.path.splitext(os.path.basename(path))[0] + ".pdf")
if not os.path.isfile(pdf):
    fail.append("PDF render failed")
else:
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    pages = text.split("\f")[:-1]
    sparse = [i + 1 for i, p in enumerate(pages) if len([l for l in p.split("\n") if l.strip()]) < 10]
    print(f"pages: {len(pages)}  sparse pages: {sparse or 'none'}")
    if sparse:
        fail.append(f"sparse pages {sparse}")
    if len(pages) > 11:
        fail.append(f"{len(pages)} pages, ceiling is 11")
    print("=" * 60)
    print(text)
print("=" * 60)
print("PASS" if not fail else "FAIL: " + "; ".join(fail))
sys.exit(1 if fail else 0)
