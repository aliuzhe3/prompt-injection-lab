# -*- coding: utf-8 -*-
"""
命令行批量评测脚本（不启动界面，适合服务器/截图/导出数据）
=================================================
用法：
    python run_eval.py --mock              # 离线模拟，验证流程
    python run_eval.py --real              # 接真实 API（配置见 config.py）
    python run_eval.py --real --modes none,advanced   # 只测部分模式

输出：控制台表格 + results/ 目录下的 eval_detail.csv 与 eval_summary.txt（UTF-8-BOM，可直接用 Excel 打开）。
"""

import argparse
import csv
import os
import sys

# Windows 控制台默认 GBK，强制 UTF-8 防止中文/图标输出乱码报错
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from core.attacks import PAYLOADS
from core.defenses import DEFENSE_LABELS
from core.evaluator import ALL_MODES
from core import evaluator


def main():
    parser = argparse.ArgumentParser(description="提示注入批量评测（命令行版）")
    parser.add_argument("--mock", action="store_true", help="使用离线模拟模型")
    parser.add_argument("--real", action="store_true", help="使用真实 API（默认）")
    parser.add_argument("--modes", type=str, default=",".join(ALL_MODES),
                        help="参与的防御模式，逗号分隔：none,basic,advanced")
    args = parser.parse_args()

    use_mock = args.mock or not args.real  # 两者都没指定时，默认离线模拟更安全
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    print("=" * 72)
    print(f"提示注入批量评测  |  后端：{'离线模拟' if use_mock else '真实API'}  |  用例数：{len(PAYLOADS)}")
    print("=" * 72)

    result = evaluator.run_batch(PAYLOADS, modes=modes, use_mock=use_mock)

    # ---------------- 控制台逐条输出 ----------------
    for line in result["log_lines"]:
        print(line)

    # ---------------- 汇总表 ----------------
    print("\n" + "=" * 72)
    header = f"{'防御模式':<28}{'拦截':>4}{'守住':>4}{'泄露':>4}{'ASR':>8}{'DIR':>8}"
    print(header)
    print("-" * 72)
    for mode in modes:
        s = result["stats"][mode]
        print(f"{DEFENSE_LABELS[mode]:<30}{s['blocked']:>4}{s['hold']:>4}{s['leak']:>4}"
              f"{s['asr']:>8.0%}{s['dir']:>8.0%}")
    print("=" * 72)

    # ---------------- 落盘保存（供报告引用） ----------------
    os.makedirs("results", exist_ok=True)
    detail_path = os.path.join("results", "eval_detail.csv")
    summary_path = os.path.join("results", "eval_summary.txt")

    with open(detail_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["用例ID", "用例名", "类别", "防御模式", "结果", "泄露项", "模型回复"])
        for r in result["records"]:
            outcome = "规则层拦截" if r["blocked"] else ("攻击成功" if r["leaked"] else "防御成功")
            w.writerow([r["case_id"], r["case_name"], r["category"],
                        DEFENSE_LABELS[r["mode"]], outcome,
                        "、".join(r["leaked"]) if r["leaked"] else (r["block_reason"] or "-"),
                        r["reply"]])

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(evaluator.summary_markdown(result["stats"], use_mock) + "\n\n")
        f.write("\n".join(result["log_lines"]) + "\n")

    print(f"\n明细已保存: {detail_path}\n汇总已保存: {summary_path}")


if __name__ == "__main__":
    main()
