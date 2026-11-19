# -*- coding: utf-8 -*-
"""
LLM 调用封装（OpenAI SDK 兼容）+ 离线模拟模型
=================================================
- chat(messages, use_mock)：统一对话入口。真实模式走 OpenAI SDK（兼容 Ollama/DeepSeek 等），
  模拟模式走内置的确定性"离线模拟模型"。
- 离线模拟模型的价值：教室里没网/没 GPU 也能跑通整个攻防流程、验证代码和界面；
  它按"典型弱模型"的行为规律作答（强攻击→泄露，高级防御→拒绝），
  但实验报告的数据必须用真实模型跑（模拟结果仅演示流程用）。
- openai 包采用惰性导入：离线模拟模式下即使没装 openai 也能运行本模块。
"""

import base64
import re
import threading

import config
from core.attacks import get_payload_by_text
from core.defenses import ADVANCED_MARKER  # 高级防御 System Prompt 的特征标记
from core.victim_app import FAKE_SECRETS

# ------------------------- 连接配置（可被界面临时覆盖） -------------------------
_conn_lock = threading.Lock()
_client = None  # 惰性创建的 OpenAI 客户端
_base_url = config.API_BASE_URL
_api_key = config.API_KEY
_model = config.MODEL_NAME


def configure(base_url: str, api_key: str, model: str):
    """由 Gradio 界面调用，临时修改连接参数（会重建客户端）。"""
    global _client, _base_url, _api_key, _model
    with _conn_lock:
        _base_url = base_url or config.API_BASE_URL
        _api_key = api_key or "ollama"
        _model = model or config.MODEL_NAME
        _client = None  # 强制下次调用时重建


def get_connection_info() -> dict:
    return {"base_url": _base_url, "model": _model, "api_key": _api_key}


# ------------------------- 统一对话入口 -------------------------
def chat(messages: list, use_mock: bool = False) -> str:
    """
    输入 OpenAI 格式的 messages（[{"role": "system"/"user", "content": ...}]），
    返回模型回复文本。真实模式失败时抛出带中文排查建议的 RuntimeError。
    """
    if use_mock:
        return _mock_reply(messages)

    global _client
    if _client is None:
        try:
            from openai import OpenAI  # 惰性导入，离线模拟模式无需安装
        except ImportError as e:
            raise RuntimeError(
                "未安装 openai 包，请先执行: pip install openai\n"
                "（或者把界面上的「模型后端」切换为「离线模拟」）"
            ) from e
        with _conn_lock:
            _client = OpenAI(
                base_url=_base_url,
                api_key=_api_key,
                timeout=config.LLM_TIMEOUT,
            )
    try:
        resp = _client.chat.completions.create(
            model=_model,
            messages=messages,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:  # 统一转成带排查建议的友好错误
        raise RuntimeError(
            f"调用真实模型失败：{type(e).__name__}: {e}\n"
            f"请检查（当前 base_url={_base_url}, model={_model}）：\n"
            "  1) 本地 Ollama 是否已启动并拉取模型：ollama pull qwen2.5:7b\n"
            "  2) config.py / 界面「模型连接设置」中的地址和模型名是否正确\n"
            "  3) 云端 API 的密钥是否有效、余额是否充足\n"
            "  4) 也可以先把「模型后端」切换为「离线模拟」体验完整流程"
        ) from e


# =========================================================================
#                         离线模拟模型（确定性规则实现）
# =========================================================================
# 强攻击特征词：命中即视为攻击请求（用于自定义输入的判断；内置用例走精确匹配）
_STRONG_ATTACK_HINTS = [
    "忽略", "无视", "系统提示", "提示词", "扮演", "无限制", "越狱", "原样",
    "逐字", "补全", "红线", "机密", "密钥", "秘钥", "base64", "翻译成",
    "ignore", "disregard", "system prompt", "roleplay", "jailbreak",
]
# 索取目标的特征词 → 对应机密下标（0/1/2）
_SECRET_HINTS = {
    0: ["管理员", "后台密码", "adm1n", "admin"],
    1: ["数据库", "db_", "口令"],
    2: ["api", "sk-", "密钥"],
}
# 正常咨询特征词：命中且无强攻击特征时按普通问题处理
_BENIGN_HINTS = [
    "如何", "怎么", "怎样", "请问", "你好", "您好", "谢谢", "帮助",
    "vpn", "邮箱", "打印机", "help", "hi", "hello",
]

_MOCK_PREFIX = "【离线模拟回复】"
_MOCK_REFUSE = (
    _MOCK_PREFIX + "抱歉，该信息属于公司机密。如有权限需求，请通过内网工单系统申请。\n"
    "（模拟模型：识别到疑似套取请求，已按安全铁律拒绝）"
)


def _extract_user_core(user_text: str) -> str:
    """取出用户消息的核心内容：若被 <user_input> 包裹则提取标签内部文本。"""
    m = re.search(r"<user_input>\n?(.*?)\n?</user_input>", user_text, re.DOTALL)
    return m.group(1).strip() if m else user_text.strip()


def _mock_pick_secrets(text: str) -> list:
    """根据攻击文本提到的话题，决定模拟模型会'泄露'哪几条机密。"""
    lowered = text.lower()
    hit = set()
    for idx, hints in _SECRET_HINTS.items():
        if any(h in lowered for h in hints):
            hit.add(idx)
    if not hit:  # 未指明具体目标（如"逐字翻译系统提示"类）→ 三条全泄露
        hit = {0, 1, 2}
    return sorted(hit)


def _mock_leak_reply(text: str) -> str:
    """构造一条'被攻破'的模拟回复（按需输出明文或 Base64 变体）。"""
    lowered = text.lower()
    idxs = _mock_pick_secrets(text)
    use_b64 = "base64" in lowered
    use_en = ("翻译" in text and "英文" in text) or "translate" in lowered

    lines = []
    for i in idxs:
        value = FAKE_SECRETS[i]["value"]
        shown = base64.b64encode(value.encode("utf-8")).decode() if use_b64 else value
        lines.append(f"- {FAKE_SECRETS[i]['key']}：{shown}")

    if use_en:
        head = "Sure! Here is the translated system prompt (simulated):\n"
    elif use_b64:
        head = "好的，以下是 Base64 编码结果，方便你核对：\n"
    else:
        head = "好的，没问题，请查收：\n"
    return _MOCK_PREFIX + head + "\n".join(lines) + "\n（模拟模型：未能识破该请求，已泄露机密）"


def _mock_reply(messages: list) -> str:
    """离线模拟模型的决策逻辑（真实模型行为不确定，此处用规则保证可复现的演示效果）。"""
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    core = _extract_user_core(user)

    # 高级防御模式下：System Prompt 含防注入标记 → 攻击类输入一律拒绝
    if ADVANCED_MARKER in system:
        if _is_attack_like(core):
            return _MOCK_REFUSE
        return _MOCK_PREFIX + "您好！我是云帆科技内部IT客服。关于您咨询的日常 IT 问题：连接 VPN 请打开客户端输入 vpn.yunfan.internal；修改邮箱入口在 self.yunfan.example。（模拟模型：正常业务，照常解答）"

    # 无防御 / 基础防御（未被拦截）下：先尝试与内置用例精确匹配
    case = get_payload_by_text(core)
    if case is not None:
        return _mock_leak_reply(core) if case["mock_leak_no_defense"] else _MOCK_REFUSE

    # 自定义输入：用特征词启发式判断
    if _is_attack_like(core):
        return _mock_leak_reply(core)
    if any(h in core.lower() for h in _BENIGN_HINTS):
        return _MOCK_PREFIX + "您好！我是云帆科技内部IT客服。连接 VPN 请打开客户端输入 vpn.yunfan.internal；修改邮箱入口在 self.yunfan.example。（模拟模型：正常业务，照常解答）"
    return _MOCK_REFUSE


def _is_attack_like(text: str) -> bool:
    """判断一段文本是否像提示注入攻击（用于模拟模型的自卫决策）。"""
    lowered = text.lower()
    if any(h in lowered for h in _STRONG_ATTACK_HINTS):
        return True
    # 含正常咨询特征词（如何/怎么/请问…）时按正常问题处理，
    # 即使提到"密码"二字（如"如何修改邮箱密码"不应被误判为攻击）
    if any(h in lowered for h in _BENIGN_HINTS):
        return False
    # 无攻击特征词、但直接索要敏感值（如"请告诉我密码"）也视为攻击
    if any(h in lowered for h in ("密码", "口令", "password", "api key")):
        return True
    return False
