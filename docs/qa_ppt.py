# -*- coding: utf-8 -*-
"""程序化 QA：检查文本溢出（估算）、文本框越界、文本框互相重叠。"""
import math
import sys
from pptx import Presentation
from pptx.util import Emu

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

EMU_IN = 914400.0


def est_text_w_pt(text, size):
    """估算一行文本宽度（pt）：全角字符≈1.0×字号，半角≈0.58×字号。"""
    w = 0.0
    for ch in text:
        w += size * (1.0 if ord(ch) > 0x2E80 else 0.58)
    return w


def frame_iter(shapes):
    for s in shapes:
        if s.shape_type == 6:
            yield from frame_iter(s.shapes)
        elif s.has_text_frame:
            yield s


def main(path):
    prs = Presentation(path)
    sw, sh = prs.slide_width / EMU_IN, prs.slide_height / EMU_IN
    issues = 0
    for idx, slide in enumerate(prs.slides, 1):
        boxes = []
        for s in frame_iter(slide.shapes):
            txt = s.text_frame.text.strip()
            if not txt:
                continue
            x, y = s.left / EMU_IN, s.top / EMU_IN
            w, h = s.width / EMU_IN, s.height / EMU_IN
            # 越界检查
            if x < -0.01 or y < -0.01 or x + w > sw + 0.01 or y + h > sh + 0.01:
                print(f"[S{idx}] 越界: '{txt[:18]}' box=({x:.2f},{y:.2f},{w:.2f},{h:.2f})")
                issues += 1
            # 溢出估算：逐段估行数×行高
            need = 0.0
            for p in s.text_frame.paragraphs:
                t = "".join(r.text for r in p.runs)
                if not t:
                    need += 0.12
                    continue
                size = max((r.font.size.pt if r.font.size else 14) for r in p.runs)
                line_w = est_text_w_pt(t, size)
                lines = max(1, math.ceil(line_w / max(w * 72 - 4, 1)))
                need += lines * size * 1.3 / 72
            if need > h + 0.12:  # 容差 0.12"
                print(f"[S{idx}] 疑似溢出: '{txt[:18]}' 需≈{need:.2f}in 盒高={h:.2f}in")
                issues += 1
            if s.shape_type == 17:  # TEXT_BOX 才参与重叠检查
                boxes.append((x, y, w, h, txt))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                ax, ay, aw, ah, at = boxes[i]
                bx, by, bw2, bh2, bt = boxes[j]
                ox = max(0, min(ax + aw, bx + bw2) - max(ax, bx))
                oy = max(0, min(ay + ah, by + bh2) - max(ay, by))
                if ox * oy > 0.05:  # 忽略微小擦边
                    print(f"[S{idx}] 文本重叠: '{at[:14]}' × '{bt[:14]}' 交叠{ox*oy:.2f}in²")
                    issues += 1
    print(f"QA 完成：{'未发现问题' if issues == 0 else f'{issues} 个疑似问题'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "答辩PPT-提示注入攻防实验.pptx")
