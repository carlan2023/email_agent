"""Recalculate every formula in an .xlsx with LibreOffice so cached values exist (openpyxl drops them on save).
Usage: python tools/recalc.py FILE.xlsx   (rewrites the file in place, then prints any formula errors)"""
import os
import shutil
import subprocess
import sys
import tempfile

import openpyxl

path = os.path.abspath(sys.argv[1])
out = tempfile.mkdtemp()
subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", out, path],
               capture_output=True, timeout=240)
res = os.path.join(out, os.path.basename(path))
if not os.path.isfile(res):
    sys.exit("recalc failed: LibreOffice produced no file")
shutil.copy(res, path)
wb = openpyxl.load_workbook(path, data_only=True)
errors = []
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("#"):
                errors.append(f"{ws.title}!{c.coordinate}={c.value}")
print("recalculated;", "errors: " + ", ".join(errors) if errors else "no formula errors")
sys.exit(1 if errors else 0)
