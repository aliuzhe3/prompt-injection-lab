# LLM 应用提示注入攻防实验平台

大学课程设计项目：以一个内置**虚构机密**的"内部 IT 客服机器人"为靶标，演示
**提示注入攻击**手法与**多级防御**的效果差异，并支持一键批量评测统计。

> ⚠️ 合规声明：本项目仅用于授权教学实验。所有"密码/口令/密钥"均为虚构字符串，
> 请勿对任何真实第三方服务实施注入攻击。

## 一、快速开始（3 分钟开箱演示）

```bash
cd prompt-injection-lab
pip install -r requirements.txt
python app.py
```

浏览器自动打开 `http://127.0.0.1:7860`。默认后端为**离线模拟模型**（无需任何 API，
即可完整体验界面与流程）。左侧顶部可随时切换后端。

## 二、接入真实模型（写报告用真实数据）

| 后端 | Base URL | 模型名 | 密钥 |
|---|---|---|---|
| Ollama（本地，推荐） | `http://localhost:11434/v1` | `qwen2.5:7b` | 随便填 |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | 真实密钥 |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | 真实密钥 |

三种配置方式（任选其一）：
1. 启动后在界面顶部「⚙️ 模型连接设置」里填写并保存，然后把「模型后端」切到 **真实API**；
2. 修改 `config.py` 中的 `API_BASE_URL / API_KEY / MODEL_NAME`；
3. 环境变量 `LLM_API_BASE / LLM_API_KEY / LLM_MODEL`。

Ollama 准备命令：
```bash
ollama pull qwen2.5:7b   # 4.7GB 左右；显存小可换 qwen2.5:3b
ollama serve             # 默认已在后台运行则可跳过
```

## 三、项目结构

```
prompt-injection-lab/
├── app.py                  # Gradio 前端入口（三个标签页：单次演示/批量评测/实验说明）
├── run_eval.py             # 命令行批量评测（不带界面，导出 CSV 到 results/）
├── config.py               # 全局配置（API 地址、模型名、采样参数）
├── requirements.txt
├── core/
│   ├── victim_app.py       # 模块一：受害者应用（含 3 条虚构机密的 System Prompt）
│   ├── attacks.py          # 模块二：10 个提示注入测试用例（5 经典 + 5 进阶）
│   ├── defenses.py         # 模块三：无防御 / 黑名单 / XML 隔离 三种防御
│   ├── llm_client.py       # LLM 调用封装（OpenAI SDK 兼容 + 离线模拟模型）
│   └── evaluator.py        # 模块四：批量评测与 ASR / DIR 统计
├── docs/
│   └── 课设报告大纲.md      # 报告大纲 + 结果分析说明（可直接贴进 Word）
└── results/                # 命令行评测的输出目录（自动生成）
```

## 四、实验方法速查

- **单次演示**：标签页① → 选攻击用例 → 选防御模式 → 「发起攻击」。
  重点观察"实际发送给模型的提示词"在三种模式下的差异（无防御=裸拼接；
  基础=命中黑名单直接拦截；高级=被 `<user_input>` 包裹 + System Prompt 追加防注入规则）。
- **批量评测**：标签页② → 「一键运行安全评测」，自动跑 10 用例 × 3 模式 = 30 次，
  输出逐用例明细表 + ASR/DIR 统计对比表 + 运行日志。建议用真实模型跑 3 次取平均。
- **黑名单的两宗罪**（报告亮点）：
  1. 绕过：`P10 同义改写` 不含任何黑名单词，直接穿透基础防御；
  2. 误伤：标签页① 自定义输入 `如何修改我的邮箱密码？`（正常问题）也会被拦截。
- **高级防御的标签逃逸对抗**：`P04` 会伪造 `</user_input>` 闭合标签，防御层已做全角转义。

## 五、常见问题

| 现象 | 处理 |
|---|---|
| 调用真实模型失败 | 看 UI 给出的排查建议：Ollama 是否 `ollama list` 有模型；地址/模型名是否写对 |
| 演示时没网/没 GPU | 「模型后端」切回离线模拟即可完整演示流程（数据仅供流程演示） |
| 端口 7860 被占用 | `python app.py` 前设 `set GRADIO_SERVER_PORT=7861`，或改 app.py 末尾端口 |
| Windows 控制台中文乱码 | 用 `run_eval.py` 已内置 UTF-8 处理；或 `chcp 65001` |
| ASR 全为 0 或全为 100% | 换能力更强的模型（太弱的模型可能连正常问题都答不好；太强的模型自身防线也强） |
