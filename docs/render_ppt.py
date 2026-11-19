# -*- coding: utf-8 -*-
"""把 PPTX 渲染为逐页 PNG：LibreOffice 转 PDF，再用 PyMuPDF 栅格化。"""
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.exe"


def main(pptx_path: str, out_dir: str):
    pptx = Path(pptx_path).resolve()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # ① pptx → pdf（LibreOffice 无头模式）
    subprocess.run([SOFFICE, "--headless", "--convert-to", "pdf",
                    "--outdir", str(out), str(pptx)],
                   check=True, capture_output=True, timeout=300)
    pdf = out / (pptx.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError("PDF 转换失败")
    # ② pdf → png
    import fitz  # PyMuPDF
    doc = fitz.open(pdf)
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(dpi=110)
        pix.save(str(out / f"slide-{i:02d}.png"))
    doc.close()
    print(f"rendered {len(list(out.glob('slide-*.png')))} pages -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "答辩PPT-提示注入攻防实验.pptx",
         sys.argv[2] if len(sys.argv) > 2 else "render")
