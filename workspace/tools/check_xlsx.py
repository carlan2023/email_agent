"""Render an .xlsx to PDF and print its text, plus a hyperlink and dash check.
Usage: python tools/check_xlsx.py FILE.xlsx"""
import os
import subprocess
import sys
import tempfile

import openpyxl

path = sys.argv[1]
fail = []
wb = openpyxl.load_workbook(path)
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            if getattr(c.hyperlink, "target", None):
                fail.append(f"hyperlink left at {ws.title}!{c.coordinate}: {c.hyperlink.target}")
            if isinstance(c.value, str) and ("—" in c.value or "–" in c.value):
                fail.append(f"dash at {ws.title}!{c.coordinate}")
out = tempfile.mkdtemp()
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", out, path], capture_output=True, timeout=240)
pdf = os.path.join(out, os.path.splitext(os.path.basename(path))[0] + ".pdf")
if os.path.isfile(pdf):
    print(subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout)
else:
    fail.append("PDF render failed")
print("PASS" if not fail else "FAIL: " + "; ".join(fail))
sys.exit(1 if fail else 0)
