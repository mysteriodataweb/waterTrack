"""Builds the report: English figures, Word document, filled table of contents and PDF.

Usage (from the repository root):  python3 docs/independent-project/scripts/build_all.py
Requires: matplotlib, Pillow, Node.js with the `docx` package, LibreOffice with python3-uno.
Outputs:  docs/independent-project/WaterTracker_IP_2026_Report.docx and .pdf
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT_DIR = HERE.parent
NAME = "WaterTracker_IP_2026_Report"
MAX_PX = 1800  # figures are downscaled to keep the document small; 1800 px ≈ 290 dpi at 6.2 in


def referenced_figures():
    for md in sorted((OUT_DIR / "report").glob("*.md")):
        for line in md.read_text(encoding="utf-8").splitlines():
            if line.startswith("@figure "):
                yield line[8:].split("|")[0].strip()


def main():
    subprocess.run([sys.executable, str(HERE / "make_figures.py")], check=True)
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "figs"
        for rel in set(referenced_figures()):
            src, dst = ROOT / rel, cache / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(src) as im:
                im = im.convert("RGB")
                if im.width > MAX_PX:
                    im = im.resize((MAX_PX, round(im.height * MAX_PX / im.width)), Image.LANCZOS)
                im.save(dst, optimize=True)
                if dst.stat().st_size > 1_500_000:  # photographic map: an adaptive palette divides its size by ~4
                    im.convert("P", palette=Image.ADAPTIVE, colors=256).save(dst, optimize=True)
        raw = Path(tmp) / "raw.docx"
        env = {**os.environ, "FIG_CACHE": str(cache)}
        env.setdefault("NODE_PATH", "/opt/node-tools/node_modules")
        subprocess.run(["node", str(HERE / "build_report.js"), str(raw)], check=True, env=env)
        subprocess.run([sys.executable, str(HERE / "update_fields.py"), str(raw),
                        str(OUT_DIR / f"{NAME}.docx"), str(OUT_DIR / f"{NAME}.pdf")], check=True)


if __name__ == "__main__":
    main()
