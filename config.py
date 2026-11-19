# -*- coding: utf-8 -*-
"""
全局配置文件
================
修改本文件即可切换 LLM 后端（支持任何 OpenAI SDK 兼容服务）：

1) 本地 Ollama（推荐，免费、离线）：
   - 先安装 Ollama，然后执行:  ollama pull qwen2.5:7b
   - API_BASE_URL 保持默认 http://localhost:11434/v1，API_KEY 随便填

2) DeepSeek 云端 API：
   - API_BASE_URL = "https://api.deepseek.com/v1"
   - API_KEY = "sk-你的密钥"
   - MODEL_NAME = "deepseek-chat"

3) OpenAI 官方：
   - API_BASE_URL = "https://api.openai.com/v1"
   - API_KEY = "sk-..."
   - MODEL_NAME = "gpt-4o-mini"

也可以在 Gradio 界面顶部的「模型连接设置」中临时修改，无需改代码。
注意：以上配置也可用环境变量 LLM_API_BASE / LLM_API_KEY / LLM_MODEL 覆盖。
"""

import os

# ---------------- LLM 后端连接配置（OpenAI SDK 兼容） ----------------
API_BASE_URL = os.getenv("LLM_API_BASE", "http://localhost:11434/v1")  # Ollama 默认地址
API_KEY = os.getenv("LLM_API_KEY", "ollama")                            # Ollama 不校验密钥，占位即可
MODEL_NAME = os.getenv("LLM_MODEL", "qwen2.5:7b")                       # 默认用本地 qwen2.5:7b

# ---------------- 采样参数 ----------------
LLM_TEMPERATURE = 0.7   # 温度：课设实验建议 0.7 左右，太低模型过于死板，太高输出不稳定
LLM_MAX_TOKENS = 512    # 单次最大生成 token 数
LLM_TIMEOUT = 60        # 请求超时（秒），本地小模型推理慢时可调大

# ---------------- 界面默认后端 ----------------
# True  = 启动时默认选中「离线模拟」模式（不连任何模型，用于快速演示流程）
# False = 启动时默认选中「真实 API」模式
MOCK_LLM_DEFAULT = True
