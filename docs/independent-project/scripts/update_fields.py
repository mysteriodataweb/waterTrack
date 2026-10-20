"""Fills the table of contents and the lists of figures/tables of a .docx with LibreOffice,
then saves it as .docx and .pdf. Word users can still refresh everything with F9.

Usage: python3 update_fields.py input.docx output.docx output.pdf
Requires LibreOffice and its Python UNO bridge (python3-uno).
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main(src, dst_docx, dst_pdf):
    profile = tempfile.mkdtemp(prefix="lo_profile_")
    pipe = f"wt{os.getpid()}"
    office = subprocess.Popen([
        "soffice", f"-env:UserInstallation={Path(profile).as_uri()}", "--headless", "--invisible",
        "--norestore", f"--accept=pipe,name={pipe};urp;StarOffice.ComponentContext",
    ], env={**os.environ, "SAL_USE_VCLPLUGIN": "svp"})
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(60):
            try:
                ctx = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("LibreOffice did not start")
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(Path(src).resolve().as_uri(), "_blank", 0, (prop("Hidden", True),))
        doc.getTextFields().refresh()
        indexes = doc.getDocumentIndexes()
        for _ in range(2):                      # second pass: page numbers after the lists are filled
            for k in range(indexes.getCount()):
                indexes.getByIndex(k).update()
        doc.storeToURL(Path(dst_docx).resolve().as_uri(), (prop("FilterName", "MS Word 2007 XML"),))
        doc.storeToURL(Path(dst_pdf).resolve().as_uri(), (prop("FilterName", "writer_pdf_Export"),))
        print(f"{indexes.getCount()} indexes updated -> {dst_docx}, {dst_pdf}")
        doc.close(True)
    finally:
        office.terminate()
        office.wait(timeout=30)


if __name__ == "__main__":
    main(*sys.argv[1:4])
