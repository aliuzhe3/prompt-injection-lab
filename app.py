# -*- coding: utf-8 -*-
"""
LLM 提示注入攻防实验平台 —— Gradio 前端入口
=================================================
启动方式：  python app.py
（默认浏览器会自动打开 http://127.0.0.1:7860）

界面共三个标签页：
  ① 单次攻防演示：选一条攻击用例（或自定义输入）× 选一种防御模式 →
     查看实际发送的提示词、防御处理日志、模型回复与泄露判定
  ② 批量安全评测：一键跑 10 个用例 × 3 种防御模式，实时滚动结果，
     汇总【攻击成功率 ASR】与【防御拦截率 DIR】对比表
  ③ 实验说明：原理讲解 + 指标定义 + 写报告的素材提示
"""

import gradio as gr
import pandas as pd

import config
from core.attacks import PAYLOADS, case_label
from core.defenses import (DEFENSE_ADVANCED, DEFENSE_BASIC, DEFENSE_LABELS,
                           DEFENSE_NONE)
from core import evaluator, llm_client

# ------------------------- 界面用常量 -------------------------
BACKEND_MOCK = "离线模拟（无需API，演示流程）"
BACKEND_REAL = "真实API（OpenAI兼容：Ollama/DeepSeek等）"

CASE_CHOICES = [(case_label(p), p["id"]) for p in PAYLOADS]
ID2CASE = {p["id"]: p for p in PAYLOADS}

MODE_CHOICES = [
    (DEFENSE_LABELS[DEFENSE_NONE], DEFENSE_NONE),
    (DEFENSE_LABELS[DEFENSE_BASIC], DEFENSE_BASIC),
    (DEFENSE_LABELS[DEFENSE_ADVANCED], DEFENSE_ADVANCED),
]

BATCH_MODE_COLS = [DEFENSE_NONE, DEFENSE_BASIC, DEFENSE_ADVANCED]  # 批量表格固定列顺序


# =========================================================================
# ① 单次攻防演示 回调
# =========================================================================
def on_case_selected(case_id):
    """下拉框选中内置用例时，展示该用例的攻击文本与原理说明。"""
    if not case_id:
        return ""
    p = ID2CASE[case_id]
    return f"**{p['id']} {p['name']}**（类别：{p['category']}）\n\n" \
           f"> 原理：{p['desc']}\n\n" \
           f"**攻击文本：**\n\n```\n{p['payload']}\n```"


def on_attack(case_id, custom_input, mode, backend):
    """点击「发起攻击」：完整跑一遍 攻击→防御→模型→判定 流程。"""
    use_mock = (backend == BACKEND_MOCK)
    # 自定义输入优先于下拉框选择的内置用例
    payload_text = custom_input.strip() if custom_input and custom_input.strip() \
        else ID2CASE[case_id]["payload"]

    try:
        r = evaluator.run_single(payload_text, mode, use_mock=use_mock)
    except RuntimeError as e:  # 模型调用失败：把排查建议直接显示在界面上
        return "", "", f"❌ 调用模型失败：\n\n{e}", "⚠️ 未完成（见左侧错误信息）"

    # 拼装"实际发送给模型的完整提示词"展示区
    if r["blocked"]:
        prompt_preview = (
            f"【System Prompt】\n（未发送——输入在调用模型前已被黑名单拦截）\n\n"
            f"【用户输入】\n{payload_text}"
        )
        reply_text = r["reply"]
        defense_note = r["defense_note"]
    else:
        prompt_preview = (
            f"【System Prompt（实际发送）】\n{r['system_prompt']}\n\n"
            f"{'=' * 60}\n\n【用户消息（实际发送，可能已被防御层包裹处理）】\n{r['user_message']}"
        )
        reply_text = r["reply"]
        defense_note = r["defense_note"]

    verdict = (f"{r['verdict']}\n"
               f"后端：{'离线模拟' if use_mock else llm_client.get_connection_info()['model']}"
               f"｜防御模式：{DEFENSE_LABELS[mode]}")
    return prompt_preview, defense_note, reply_text, verdict


# =========================================================================
# ② 批量安全评测 回调（生成器：边跑边刷新界面）
# =========================================================================
def on_batch_run(modes_selected, backend, progress=gr.Progress()):
    """一键安全评测：10 用例 × 所选防御模式，逐条推送结果与统计。"""
    use_mock = (backend == BACKEND_MOCK)
    modes = [DEFENSE_NONE, DEFENSE_BASIC, DEFENSE_ADVANCED]
    if modes_selected:
        modes = modes_selected

    def cell_of(record):
        if record is None:
            return "—"
        if record["blocked"]:
            return "⛔ 拦截"
        if record["leaked"]:
            return "🚨 泄露：" + "、".join(record["leaked"])
        return "🛡️ 守住"

    columns = ["序号", "攻击用例", "类别"] + [DEFENSE_LABELS[m] for m in BATCH_MODE_COLS]
    df = pd.DataFrame(columns=columns)
    log_lines = []
    summary = "评测进行中……（结果会实时滚动显示）"

    def push(done, total, line):
        progress(min(done / total, 1.0), desc=f"已评测 {done}/{total} 条")

    def make_df(records_by_case):
        rows = []
        for i, p in enumerate(PAYLOADS, 1):
            cells = [i, f"{p['id']} {p['name']}", p["category"]]
            for m in BATCH_MODE_COLS:
                rec = records_by_case.get((p["id"], m))
                cells.append(cell_of(rec) if m in modes else "（未测）")
            rows.append(cells)
        return pd.DataFrame(rows, columns=columns)

    try:
        records_by_case = {}
        for p in PAYLOADS:
            for m in modes:
                r = evaluator.run_single(p["payload"], m, use_mock=use_mock)
                records_by_case[(p["id"], m)] = r
                # 生成日志行（与 evaluator.run_batch 格式一致）
                if r["blocked"]:
                    outcome = f"规则层拦截（{r['block_reason']}）"
                elif r["leaked"]:
                    outcome = f"攻击成功，泄露：{'、'.join(r['leaked'])}"
                else:
                    outcome = "防御成功，模型未泄露"
                log_lines.append(
                    f"[{p['id']} {p['name']}] × {DEFENSE_LABELS[m]} → {outcome}\n"
                    f"    回复摘要：{r['reply'][:80]}{'…' if len(r['reply']) > 80 else ''}"
                )
                push(len(log_lines), len(PAYLOADS) * len(modes), log_lines[-1])
                # 流式刷新：每次跑完一条就推送一次界面
                yield make_df(records_by_case), "\n".join(log_lines), summary
    except RuntimeError as e:
        log_lines.append(f"\n❌ 评测中断：{e}")
        yield make_df(records_by_case), "\n".join(log_lines), "❌ 评测中断，请检查模型连接（或切换为离线模拟）"
        return

    # ---- 全部完成：用 evaluator 的统计逻辑汇总指标 ----
    result = {"records": [], "stats": None, "log_lines": log_lines}
    stats = {}
    n = len(PAYLOADS)
    for m in modes:
        rs = [records_by_case[(p["id"], m)] for p in PAYLOADS]
        blocked_cnt = sum(1 for r in rs if r["blocked"])
        leak_cnt = sum(1 for r in rs if r["leaked"])
        hold_cnt = n - blocked_cnt - leak_cnt
        stats[m] = {"n": n, "blocked": blocked_cnt, "hold": hold_cnt,
                    "leak": leak_cnt, "asr": leak_cnt / n, "dir": 1 - leak_cnt / n}
    summary = evaluator.summary_markdown(stats, use_mock)
    yield make_df(records_by_case), "\n".join(log_lines), summary


# =========================================================================
# 模型连接设置 回调
# =========================================================================
def on_apply_conn(base_url, api_key, model):
    llm_client.configure(base_url.strip(), api_key.strip(), model.strip())
    info = llm_client.get_connection_info()
    return f"✅ 已保存连接设置：base_url=`{info['base_url']}`，model=`{info['model']}`"


# =========================================================================
# 界面布局
# =========================================================================
with gr.Blocks(title="LLM 提示注入攻防实验平台") as demo:
    gr.Markdown(
        "# 🛡️ LLM 应用提示注入攻防实验平台\n"
        "大学课程设计实验项目：以一个内置【虚构机密】的内部 IT 客服机器人为靶标，"
        "演示提示注入攻击手法与多级防御的效果差异。**本平台仅用于授权教学实验，所有密码均为虚构。**"
    )

    # ---------- 顶部全局设置：模型后端 ----------
    with gr.Row():
        backend_radio = gr.Radio(
            choices=[BACKEND_MOCK, BACKEND_REAL],
            value=BACKEND_MOCK if config.MOCK_LLM_DEFAULT else BACKEND_REAL,
            label="模型后端（两个标签页共用）",
        )
    with gr.Accordion("⚙️ 模型连接设置（使用真实 API 时填写，改完点保存）", open=False):
        with gr.Row():
            conn_base = gr.Textbox(value=config.API_BASE_URL, label="API Base URL",
                                   info="Ollama 默认 http://localhost:11434/v1；DeepSeek 为 https://api.deepseek.com/v1")
            conn_key = gr.Textbox(value=config.API_KEY, label="API Key", type="password",
                                  info="Ollama 随便填；云端 API 填真实密钥")
            conn_model = gr.Textbox(value=config.MODEL_NAME, label="模型名称",
                                    info="如 qwen2.5:7b / deepseek-chat / gpt-4o-mini")
        conn_btn = gr.Button("💾 保存连接设置")
        conn_status = gr.Markdown()

    conn_btn.click(on_apply_conn, inputs=[conn_base, conn_key, conn_model], outputs=[conn_status])

    # ================= 标签页 ①：单次攻防演示 =================
    with gr.Tab("① 单次攻防演示"):
        gr.Markdown("选择一条内置攻击用例（或在下方自定义输入）→ 选择防御模式 → 点击「发起攻击」，"
                    "右侧/下方会展示**实际发送给模型的完整提示词**、防御处理日志、模型回复与泄露判定。")
        with gr.Row():
            with gr.Column(scale=1):
                case_dd = gr.Dropdown(choices=CASE_CHOICES, value="P01",
                                      label="内置攻击用例（共 10 条：前 5 条经典 + 后 5 条进阶）")
                case_info = gr.Markdown()
                custom_tb = gr.Textbox(label="✏️ 自定义攻击输入（填写后优先于上方用例）",
                                       placeholder="也可输入正常问题，体验黑名单的误伤，例如：如何修改我的邮箱密码？",
                                       lines=2)
                mode_radio = gr.Radio(choices=MODE_CHOICES, value=DEFENSE_NONE, label="防御模式")
                attack_btn = gr.Button("🚀 发起攻击", variant="primary")
            with gr.Column(scale=1):
                out_prompt = gr.Textbox(label="📩 实际发送给模型的提示词（System + User）", lines=14, max_lines=25)
                out_defense = gr.Textbox(label="🧱 防御处理日志", lines=3)
                out_reply = gr.Textbox(label="💬 模型回复", lines=6)
                out_verdict = gr.Textbox(label="⚖️ 判定结果", lines=3)

        case_dd.change(on_case_selected, inputs=[case_dd], outputs=[case_info])
        attack_btn.click(on_attack,
                         inputs=[case_dd, custom_tb, mode_radio, backend_radio],
                         outputs=[out_prompt, out_defense, out_reply, out_verdict])

    # ================= 标签页 ②：批量安全评测（加分项） =================
    with gr.Tab("② 批量安全评测"):
        gr.Markdown("一键对 **10 个攻击用例 × 3 种防御模式** 共 30 次实验进行自动化评测，"
                    "实时统计**攻击成功率（ASR）**与**防御拦截率（DIR）**。结果可直接截图放进报告。")
        with gr.Row():
            modes_cbg = gr.CheckboxGroup(
                choices=MODE_CHOICES,
                value=[DEFENSE_NONE, DEFENSE_BASIC, DEFENSE_ADVANCED],
                label="参与对比的防御模式")
            batch_btn = gr.Button("🏃 一键运行安全评测", variant="primary", scale=1)
        batch_df = gr.Dataframe(
            headers=["序号", "攻击用例", "类别"] + [DEFENSE_LABELS[m] for m in BATCH_MODE_COLS],
            label="逐用例评测明细",
            interactive=False, wrap=True)
        batch_summary = gr.Markdown(label="统计对比结果")
        batch_log = gr.Textbox(label="运行日志（含模型回复摘要，可贴进报告）", lines=12, max_lines=30)

        batch_btn.click(on_batch_run, inputs=[modes_cbg, backend_radio],
                        outputs=[batch_df, batch_log, batch_summary])

    # ================= 标签页 ③：实验说明 =================
    with gr.Tab("③ 实验说明"):
        gr.Markdown(
            """
            ## 实验原理

            **提示注入（Prompt Injection）** 的根源：LLM 的输入上下文中
            **"指令"与"数据"共用同一条通道**。System Prompt 告诉模型"不许泄密"（指令），
            用户消息（数据）里却可以再写入一段"假指令"。模型没有可靠的机制分辨哪段话更"权威"，
            于是精心构造的用户输入就可能覆盖系统指令——这就是越狱/注入的本质。

            ## 三种防御模式

            | 模式 | 机制 | 优点 | 缺点 |
            |---|---|---|---|
            | 无防御 | 对照组，原样拼接 | — | 完全暴露 |
            | 基础防御·黑名单 | 命中敏感词则在调用模型前拦截 | 实现简单、零推理成本 | 可被同义改写绕过（见 P10）；会误伤正常用户（试试问"如何修改邮箱密码"） |
            | 高级防御·XML 隔离 | 用户输入包进 `<user_input>` 标签 + System Prompt 声明"标签内是不可信数据"，并转义伪造的闭合标签 | 不依赖词表、语义级防御，对绕过话术鲁棒 | 非绝对安全，强模型+强攻击仍可能突破 |

            ## 指标定义

            - **攻击成功率 ASR** = 泄露机密的用例数 ÷ 总用例数（自动判定：回复中出现机密"指纹"，支持去空格/忽略大小写/Base64 变体）
            - **防御拦截率 DIR** = 1 − ASR =（规则层拦截 + 模型层守住）÷ 总用例数

            ## 写报告小提示

            1. 在标签页①分别截图：同一攻击（如 P01）在三种模式下的"实际发送提示词 + 模型回复"三连对比。
            2. 在标签页②跑完评测后截图明细表与统计表；用真实模型各跑 3 次取平均更严谨。
            3. 别忘了演示黑名单的两宗"罪"：P10 绕过 + 正常问题被误拦（在标签页①输入"如何修改我的邮箱密码"）。

            ## 合规声明

            本平台所有"机密"均为**虚构教学数据**；实验仅针对本地/自有模型进行，
            请勿对任何真实第三方服务实施注入攻击。
            """
        )

    gr.Markdown("---\n*LLM 提示注入攻防实验平台 · 课程设计演示项目 · 所有机密数据均为虚构*")


if __name__ == "__main__":
    demo.queue()  # 生成器流式输出需要队列支持
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True, show_error=True)
