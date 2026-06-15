# Inspiration Integrator（灵感整合器）开发总结

## 项目简介

将用户模糊的"谁在哪干什么"创作意图，通过交互式选择题对话，逐步补全画面细节、风格与镜头语言，最终输出可直接用于 AI 视频生成的高质量英文提示词。

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **Python 3.11** | 开发语言 |
| **Streamlit** | Web UI 框架 |
| **DeepSeek API**（`deepseek-chat`） | AI 对话引擎（兼容 OpenAI SDK） |
| **python-dotenv** | 本地环境变量管理 |
| **Streamlit Community Cloud** | 云端部署 |

---

## 项目文件结构

```
pythonProject/
├── app.py                    # 主应用（全部逻辑）
├── requirements.txt          # Python 依赖
├── .env                      # 本地 API Key（已 gitignore，不上传）
├── .gitignore
├── .streamlit/
│   └── secrets.toml          # 本地 Streamlit 密钥模板（已 gitignore）
└── DEVELOPMENT_SUMMARY.md    # 本文档
```

---

## 开发历程

### Phase 1 — 项目搭建

- 确定产品定位：**将模糊灵感转化为视频提示词**的交互工具
- 设计交互流程：
  1. 用户输入 "谁在哪干什么"
  2. AI 逐轮出选择题，收集各维度细节
  3. 达到足够信息后生成最终 prompt
- 选择 Streamlit 作为 UI 框架，可快速迭代 MVP
- 使用 DeepSeek API（兼容 OpenAI SDK）驱动对话

### Phase 2 — 核心功能开发

- 实现三段式状态机：`input → choosing → finished`
- 设计 SYSTEM_PROMPT，规定 AI 输出严格的 JSON 格式：
  - `question`：当前轮问题
  - `choices`：选项列表（label + value）
  - `finish`：是否完成收集
  - `final_prompt`：最终生成的视频提示词
- 设定对话策略维度顺序：
  1. 主体视觉细节
  2. 场景环境
  3. 具体动作
  4. 视觉风格
  5. 镜头语言
- 实现选择按钮 + 自定义补充输入

### Phase 3 — Bug 修复（共 12 个）

#### 🔴 严重级别

| # | 问题 | 修复 |
|---|------|------|
| 1 | 自定义输入静态 key 导致无限 rerun 死循环 | 改用 `st.form` 包裹，提交后自动重置 |
| 2 | DeepSeek 输出 markdown 代码块（` ```json `）导致 JSON 解析失败 | 新增 `strip_markdown_json()` 函数，自动剥离代码块标记 |
| 3 | SYSTEM_PROMPT 仅为占位符"（同上）" | 重写完整中文提示词，明确 JSON 结构、轮次策略、最终 prompt 要求 |

#### 🟠 高风险

| # | 问题 | 修复 |
|---|------|------|
| 4 | API 调用无异常捕获，网络波动直接白屏 | 封装 `call_deepseek()`，主流程加 try/except，失败时显示重试/重启按钮 |
| 5 | 按钮 key 每轮相同引发 Streamlit `DuplicateWidgetID` | key 加入轮次前缀 `f"r{round}_c{i}"` |
| 6 | 使用了不存在的模型名 `deepseek-v4-flash` | 统一为官方名称 `deepseek-chat` |

#### 🟡 中等风险

| # | 问题 | 修复 |
|---|------|------|
| 7 | 强制完成路径没处理 JSON 包裹 | 同样调用 `strip_markdown_json()` + 尝试提取 `final_prompt` |
| 8 | 直接使用 `data["question"]` 可能 KeyError | 全部改为 `.get()` 安全访问 |
| 9 | 自定义输入可反复提交相同内容，污染上下文 | `st.form` 提交后自动清理 |
| 10 | 生产代码遗留 `st.write("DEBUG...")` 暴露原始 API 响应 | 已删除 |
| 11 | API Key 为 None 时到 API 调用阶段才崩溃 | 启动时前置检查，为空直接报错并 `st.stop()` |
| 12 | 最大轮次检查在 API 调用之后，浪费配额 | round 检查前置到 API 调用之前 |

### Phase 4 — 云端部署配置

- 修改 `app.py` 同时支持本地 `.env` 和 Streamlit Cloud `st.secrets`
- 创建 `requirements.txt`（streamlit, openai, python-dotenv）
- 配置 `.gitignore` 排除 `.env` 和 `secrets.toml`，防止密钥泄漏
- 初始化 Git 仓库并提交

---

## 部署方式

通过 **Streamlit Community Cloud** 部署：

1. 推送代码到 GitHub 仓库
2. 在 [share.streamlit.io](https://share.streamlit.io) 新建 app
3. 仓库选择 `Ovenxx/inspiration-integrator`，分支 `master`，主文件 `app.py`
4. 在 Settings → Secrets 中配置 `DEEPSEEK_API_KEY`
5. 部署完成后获得公网链接，点开即用

**链接示例：** `https://inspiration-integrator.streamlit.app`

---

## 项目状态

- ✅ MVP 核心交互流程完成
- ✅ DeepSeek API 集成完成
- ✅ JSON 解析稳定性修复完成
- ✅ 依赖和部署配置完成
- ⏳ 待优化：UI 美化、错误提示更友好、支持更多视频风格模板

---

## 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| AI 输出格式 | JSON（非纯文本） | 可程序化解析，稳定渲染选择题按钮 |
| 状态管理 | Streamlit `session_state` | 最简单的方式，无需额外后端 |
| 对话策略 | 固定维度顺序（6轮） | 覆盖面广，用户不会遗漏关键维度 |
| 最终 prompt 语言 | 英文 | 主流通用，适配主流视频生成工具 |
| API 密钥管理 | `st.secrets` + `dotenv` 双模式 | 本地开发和云端部署共用同一份代码 |
