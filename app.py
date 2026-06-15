import streamlit as st
import openai
import json
import re
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量（本地开发用）
load_dotenv()

# 获取 API Key：优先 Streamlit Cloud secrets，其次本地 .env 文件
try:
    api_key = st.secrets.get("DEEPSEEK_API_KEY")
except Exception:
    api_key = None
if not api_key:
    api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    st.error("❌ 未找到 DEEPSEEK_API_KEY，请在 Streamlit Cloud Secrets 或 .env 文件中设置")
    st.stop()

# 初始化 DeepSeek 客户端
client = openai.OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# 预定义的对话维度
DIMENSIONS = [
    "主体形象——年龄、服装、外貌、表情",
    "场景环境——地点、光照、氛围、时间",
    "具体动作——动作方式、节奏、姿势、情绪",
    "视觉风格——写实/动画/赛博朋克/水墨等风格方向",
    "镜头语言——景别、运镜、视角、景深",
]

SYSTEM_PROMPT = """你是一个世界顶级的"视觉创意提取师"。你的工作是通过多轮选择题对话，把用户模糊的"谁在哪干什么"想法，扩展成一条可用于 AI 视频生成的高质量视频提示词。

## 你的输出格式
你必须严格按照以下 JSON 格式输出，不要添加任何 markdown 代码块标记或额外说明：

{
  "question": "当前要问用户的问题",
  "choices": [
    {"label": "选项A短标签", "value": "选项A的详细描述"},
    {"label": "选项B短标签", "value": "选项B的详细描述"},
    {"label": "选项C短标签", "value": "选项C的详细描述"}
  ],
  "finish": false,
  "final_prompt": ""
}

当所有维度都收集完毕时，设置 "finish": true 并提供 final_prompt：

{
  "question": "",
  "choices": [],
  "finish": true,
  "final_prompt": "最终的中文视频提示词"
}

## 重要规则
1. 每轮只问一个问题，只给 3 个选项
2. 用户发给你的进度提示会告诉你哪些维度已经讨论过了，请根据进度选择下一个未讨论的维度提问
3. 绝对不要追问已经讨论过的维度，绝对不要重复提问！

## 最终提示词要求
生成的 final_prompt 必须是中文长段落（300-500字），按以下结构分段（用 \\n 换行）：
第一段：主体描述——外貌、服装、表情、姿态细节
第二段：场景与环境——地点、光照、色彩、氛围
第三段：动作与节奏——具体动作、情绪、节奏
第四段：视觉风格参考——整体美术方向
第五段：镜头语言——景别、运镜、技术参数

用丰富的视觉形容词写一条连贯的段落，语言流畅优美，富有画面感。"""


def extract_json(raw: str) -> str:
    """从任意文本中精确提取第一个完整的 JSON 对象（支持嵌套括号）"""
    decoder = json.JSONDecoder()

    # 1) 优先尝试 markdown 代码块
    match = re.search(r'```(?:json)?\s*\n?(.*?)```', raw, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass  # 代码块内容不一定就是 JSON，继续

    # 2) 逐位置尝试 raw_decode —— 它能精确找到匹配的 }
    pos = 0
    while True:
        brace_start = raw.find("{", pos)
        if brace_start == -1:
            break
        try:
            obj, end = decoder.raw_decode(raw, brace_start)
            return raw[brace_start:end]
        except json.JSONDecodeError:
            pos = brace_start + 1
            continue

    # 3) 同样尝试数组
    pos = 0
    while True:
        bracket_start = raw.find("[", pos)
        if bracket_start == -1:
            break
        try:
            obj, end = decoder.raw_decode(raw, bracket_start)
            return raw[bracket_start:end]
        except json.JSONDecodeError:
            pos = bracket_start + 1
            continue

    # 4) 真找不到了，输出到错误日志
    preview = raw[:300].replace("\n", " ")
    raise ValueError(f"无法从 AI 响应中提取 JSON。原始内容前 300 字符：{preview}")


def call_deepseek(messages, model="deepseek-chat", temperature=0.8, max_tokens=1200):
    """调用 DeepSeek API 并返回解析后的 JSON"""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    raw = response.choices[0].message.content
    st.session_state["_last_raw_response"] = raw  # 存原始响应，出错时显示
    raw_json = extract_json(raw)  # 内部已校验 JSON 合法性，失败直接抛异常
    return json.loads(raw_json)


def build_progress_context() -> str:
    """构建当前维度的进度上下文，供 AI 知道哪些已经问过了"""
    covered = st.session_state.get("covered_dimensions", [])
    remaining = [d for d in DIMENSIONS if d not in covered]

    if not covered:
        return "这是第一轮，请从第一个维度开始提问。"

    lines = ["📋 当前对话进度（已覆盖的维度）："]
    for d in DIMENSIONS:
        if d in covered:
            lines.append(f"  ✅ {d} —— 已完成")
        else:
            idx = DIMENSIONS.index(d) + 1
            lines.append(f"  ⬜ 维度{idx}：{d} —— 待讨论")

    if remaining:
        next_dim = remaining[0]
        lines.append(f"\n🔜 接下来请问下一维度：【{next_dim}】")
    else:
        lines.append("\n🎉 所有维度已覆盖完毕，请设置 finish=true 生成最终提示词。")

    return "\n".join(lines)


# =====================
# Claude 风格 CSS 主题
# =====================
st.markdown("""
<style>
    /* ─── 基础全局 ─── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:opsz@14..32&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    .stApp {
        background: #f5f5f0;
    }

    /* 主内容容器 */
    .main .block-container {
        max-width: 740px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* ─── 标题区 ─── */
    .app-header {
        text-align: center;
        padding-bottom: 2.5rem;
        margin-bottom: 1rem;
        border-bottom: 1px solid #e5e5e0;
    }

    .app-header h1 {
        font-size: 1.75rem;
        font-weight: 600;
        letter-spacing: -0.02em;
        color: #1a1a1a;
        margin-bottom: 0.25rem;
    }

    .app-header .accent-line {
        width: 48px;
        height: 3px;
        background: linear-gradient(90deg, #d97757, #f5a623);
        border-radius: 2px;
        margin: 0.75rem auto;
    }

    .app-header .subtitle {
        font-size: 0.9rem;
        color: #6b6b6b;
        font-weight: 400;
    }

    /* ─── 聊天气泡 ─── */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        margin: 1rem 0;
    }

    .chat-bubble {
        max-width: 88%;
        padding: 0.75rem 1rem;
        border-radius: 14px;
        font-size: 0.92rem;
        line-height: 1.55;
        word-break: break-word;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .chat-bubble.user {
        align-self: flex-end;
        background: #1a1a1a;
        color: #f5f5f0;
        border-bottom-right-radius: 4px;
    }

    .chat-bubble.assistant {
        align-self: flex-start;
        background: #ffffff;
        color: #1a1a1a;
        border: 1px solid #e5e5e0;
        border-bottom-left-radius: 4px;
    }

    .chat-bubble .dimension-tag {
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 500;
        color: #d97757;
        margin-bottom: 0.3rem;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    .chat-bubble .choices-inline {
        margin-top: 0.4rem;
        font-size: 0.85rem;
        color: #6b6b6b;
    }

    /* ─── 输入框 ─── */
    .stTextInput > label {
        display: none !important;
    }
    .stTextInput > div > div > input {
        border: 1px solid #e0e0db;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        font-size: 0.95rem;
        background: #ffffff;
        box-shadow: none;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .stTextInput > div > div > input:focus {
        border-color: #d97757;
        box-shadow: 0 0 0 3px rgba(217, 119, 87, 0.12);
    }

    /* ─── 自定义 form 里的输入框 ─── */
    div[data-testid="stForm"] .stTextInput > div > div > input {
        border-radius: 8px;
        padding: 0.6rem 0.85rem;
        font-size: 0.9rem;
    }

    /* ─── 选择按钮 ─── */
    div.stButton button {
        border-radius: 100px !important;
        border: 1.5px solid #e0e0db !important;
        background: #ffffff !important;
        color: #1a1a1a !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        padding: 0.6rem 1.25rem !important;
        width: 100%;
        transition: all 0.15s ease;
        box-shadow: none !important;
    }
    div.stButton button:hover {
        border-color: #d97757 !important;
        background: #fdf6f3 !important;
        color: #d97757 !important;
        box-shadow: 0 2px 8px rgba(217, 119, 87, 0.10) !important;
    }
    div.stButton button:active {
        background: #f5e6de !important;
        transform: scale(0.97);
    }
    div.stButton button p {
        font-size: 0.9rem;
        font-weight: 500;
    }

    /* 重试/重启按钮保持原有风格但带边框 */
    .retry-btn button {
        border-color: #d0d0cb !important;
    }

    /* ─── 按钮行容错 ─── */
    div.row-widget.stButton {
        display: flex;
        gap: 0.5rem;
    }

    /* ─── 进度条 ─── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #d97757, #f5a623);
        border-radius: 100px;
    }
    .stProgress > div > div {
        background: #e5e5e0;
        border-radius: 100px;
        height: 6px;
    }

    /* ─── 问题标题 ─── */
    .question-header {
        font-size: 1.15rem;
        font-weight: 600;
        color: #1a1a1a;
        line-height: 1.5;
        margin: 1.25rem 0 0.75rem 0;
        padding: 1rem 1.25rem;
        background: #ffffff;
        border-radius: 12px;
        border: 1px solid #e5e5e0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }

    /* ─── spinner ─── */
    .stSpinner > div {
        color: #d97757 !important;
    }

    /* ─── expander ─── */
    .streamlit-expanderHeader {
        font-size: 0.85rem;
        color: #6b6b6b;
        font-weight: 500;
        border-radius: 8px;
    }

    /* ─── 结果展示 ─── */
    .result-card {
        background: #ffffff;
        border: 1px solid #e5e5e0;
        border-radius: 14px;
        padding: 1.5rem 1.75rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        line-height: 1.8;
        font-size: 0.95rem;
        color: #2a2a2a;
    }

    /* ─── 阶段标签 ─── */
    .stage-tag {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.78rem;
        font-weight: 500;
        color: #d97757;
        background: #fdf6f3;
        padding: 0.25rem 0.7rem;
        border-radius: 100px;
        margin-top: 1rem;
    }

    /* ─── info/success/error 消息圆角 ─── */
    .stAlert {
        border-radius: 10px;
    }
    div[data-testid="stNotification"] {
        border-radius: 10px;
    }

    /* ─── 隐藏 Streamlit 默认品牌 ─── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* ─── section-divider ─── */
    .section-divider {
        height: 1px;
        background: #e5e5e0;
        margin: 1.5rem 0;
    }

    /* ─── dimension pills ─── */
    .dim-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin: 0.5rem 0;
    }
    .dim-pill {
        font-size: 0.75rem;
        padding: 0.2rem 0.6rem;
        border-radius: 100px;
        border: 1px solid #e5e5e0;
        background: #ffffff;
        color: #6b6b6b;
    }
    .dim-pill.active {
        border-color: #d97757;
        background: #fdf6f3;
        color: #d97757;
    }
    .dim-pill.done {
        border-color: #b8d4b8;
        background: #f0f7f0;
        color: #4a8a4a;
    }

    /* ─── finish button ─── */
    .finish-btn button {
        border-color: #d97757 !important;
        background: #d97757 !important;
        color: white !important;
        font-weight: 600 !important;
    }
    .finish-btn button:hover {
        background: #c96a4a !important;
        border-color: #c96a4a !important;
        box-shadow: 0 4px 12px rgba(217, 119, 87, 0.25) !important;
    }
</style>
""", unsafe_allow_html=True)


# ===== 初始化会话状态 =====
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "current_choices" not in st.session_state:
    st.session_state.current_choices = []
if "max_rounds" not in st.session_state:
    st.session_state.max_rounds = len(DIMENSIONS)
    st.session_state.round = 0
if "covered_dimensions" not in st.session_state:
    st.session_state.covered_dimensions = []

# =====================
# 页面头部
# =====================
st.markdown("""
<div class="app-header">
    <h1>Inspiration Integrator</h1>
    <div class="accent-line"></div>
    <div class="subtitle">把模糊的灵感，变成精准的视频指令</div>
</div>
""", unsafe_allow_html=True)

# ===== 阶段1：初始输入 =====
if st.session_state.stage == "input":
    st.markdown("""
    <div style="text-align:center; color:#6b6b6b; font-size:0.9rem; margin-bottom:1.5rem;">
        输入一个简单的想法，AI 会帮你一步步完善
    </div>
    """, unsafe_allow_html=True)

    user_seed = st.text_input(
        "谁，在哪，干什么？",
        placeholder="例如：C罗来内马尔家里跳东北大秧歌",
        label_visibility="collapsed"
    )

    if user_seed:
        st.session_state.messages.append({"role": "user", "content": user_seed})
        st.session_state.stage = "choosing"
        st.rerun()

# ===== 阶段2：选择题交互 =====
elif st.session_state.stage == "choosing":
    # 提前检查轮次上限
    if st.session_state.round >= st.session_state.max_rounds:
        st.session_state.messages.append({"role": "user", "content": "请直接生成最终的视频提示词。"})
        with st.spinner("正在生成最终提示词..."):
            try:
                raw_response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=st.session_state.messages,
                    temperature=0.7,
                    max_tokens=1200
                )
                final_prompt = raw_response.choices[0].message.content
                cleaned = extract_json(final_prompt)
                try:
                    maybe_json = json.loads(cleaned)
                    if isinstance(maybe_json, dict) and maybe_json.get("final_prompt"):
                        final_prompt = maybe_json["final_prompt"]
                except json.JSONDecodeError:
                    pass
            except Exception as e:
                st.error(f"API 调用失败：{e}")
                st.stop()

        st.session_state.stage = "finished"
        st.session_state.final_prompt = final_prompt
        st.rerun()

    # ===== 维度追踪标签 =====
    done_count = len(st.session_state.covered_dimensions)
    total = len(DIMENSIONS)

    dim_pills_html = '<div class="dim-pills">'
    for i, d in enumerate(DIMENSIONS):
        short_label = d.split("——")[0]
        if i < done_count:
            dim_pills_html += f'<span class="dim-pill done">✅ {short_label}</span>'
        elif i == done_count:
            dim_pills_html += f'<span class="dim-pill active">{short_label}</span>'
        else:
            dim_pills_html += f'<span class="dim-pill">{short_label}</span>'
    dim_pills_html += '</div>'
    st.markdown(dim_pills_html, unsafe_allow_html=True)

    # ===== 进度条 =====
    progress = done_count / total
    st.progress(progress)

    # ===== 构建带进度上下文的 messages 并调用 API =====
    progress_msg = build_progress_context()
    messages_with_progress = st.session_state.messages + [
        {"role": "user", "content": progress_msg}
    ]

    with st.spinner("正在为您构思细节..."):
        try:
            data = call_deepseek(messages_with_progress)
        except ValueError as e:
            st.error(f"🤖 AI 返回的内容无法解析")
            st.info(e)
            with st.expander("🔍 AI 原始返回（供调试）"):
                # 尝试获取最后一次 API 返回的原始内容
                last_raw = st.session_state.get("_last_raw_response", "无记录")
                st.code(last_raw, language="text")
            col_retry, col_restart = st.columns(2)
            with col_retry:
                if st.button("🔄 重试"):
                    st.rerun()
            with col_restart:
                if st.button("🏠 重新开始"):
                    st.session_state.clear()
                    st.rerun()
            st.stop()
        except Exception as e:
            st.error(f"🤖 AI 响应异常：{e}")
            col_retry, col_restart = st.columns(2)
            with col_retry:
                if st.button("🔄 重试"):
                    st.rerun()
            with col_restart:
                if st.button("🏠 重新开始"):
                    st.session_state.clear()
                    st.rerun()
            st.stop()

    st.session_state.round += 1

    # ===== 检查 AI 是否主动完成 =====
    if data.get("finish"):
        final_prompt = data.get("final_prompt", "")
        if not final_prompt:
            st.error("AI 返回了完成信号但没有 final_prompt，请重试。")
            st.stop()
        st.session_state.stage = "finished"
        st.session_state.final_prompt = final_prompt
        st.rerun()

    # ===== 提取本轮数据 =====
    question = data.get("question", "请选择以下选项：")
    choices = data.get("choices", [])

    if not choices:
        st.warning("AI 没有提供选项，尝试重新生成...")
        st.session_state.messages.append({
            "role": "user",
            "content": "请给我选择题（有 label 和 value 的选项），不要直接结束。"
        })
        st.rerun()

    # 记录已问维度
    remaining_dim = [d for d in DIMENSIONS if d not in st.session_state.covered_dimensions]
    if remaining_dim:
        st.session_state.covered_dimensions.append(remaining_dim[0])

    # ===== 把 AI 的问题存入对话历史 =====
    current_dim_name = remaining_dim[0].split("——")[0] if remaining_dim else ""
    ai_question_text = f"[{current_dim_name}] {question}"
    if choices:
        choice_texts = "；".join([f"{c.get('label','')}: {c.get('value','')}" for c in choices])
        ai_question_text += f"\n选项：{choice_texts}"
    st.session_state.messages.append({"role": "assistant", "content": ai_question_text})

    # ===== 显示对话记录（气泡样式） =====
    with st.expander("📜 查看对话记录", expanded=False):
        chat_html = '<div class="chat-container">'
        for msg in st.session_state.messages:
            if msg["role"] == "system":
                continue
            role_class = "user" if msg["role"] == "user" else "assistant"
            content = msg["content"]

            # 检测是否有维度标记
            dim_match = re.match(r'^\[(.+?)\](.*)', content)
            if dim_match and msg["role"] == "assistant":
                dim_tag = dim_match.group(1)
                body = dim_match.group(2).strip()
                body_html = f'<div class="dimension-tag">{dim_tag}</div>{body}'
            else:
                body_html = content

            chat_html += f'<div class="chat-bubble {role_class}">{body_html}</div>'
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

    # ===== 当前问题卡片 =====
    st.markdown(f'<div class="question-header">{question}</div>', unsafe_allow_html=True)

    # ===== 选项按钮 =====
    round_prefix = st.session_state.round
    cols = st.columns(len(choices))
    for i, choice in enumerate(choices):
        with cols[i]:
            label = choice.get("label", f"选项{i+1}")
            value = choice.get("value", label)
            if st.button(label, key=f"r{round_prefix}_c{i}", use_container_width=True):
                st.session_state.messages.append({
                    "role": "user",
                    "content": f"我选择：{value}"
                })
                st.rerun()

    # ===== 自定义输入 =====
    with st.expander("✏️ 都不是？自己补充"):
        with st.form("custom_form"):
            custom_input = st.text_input("请输入你的想法", label_visibility="collapsed")
            submitted = st.form_submit_button("提交", use_container_width=True)
            if submitted and custom_input:
                st.session_state.messages.append({
                    "role": "user",
                    "content": custom_input
                })
                st.rerun()

# ===== 阶段3：展示结果 =====
elif st.session_state.stage == "finished":
    st.markdown('<div class="stage-tag">✨ 生成完成</div>', unsafe_allow_html=True)
    st.markdown("### 您的视频提示词")

    final_text = st.session_state.final_prompt

    # 结果卡片
    # 将 \n 转为 <br> 以便在 HTML 中换行
    display_text = final_text.replace("\\n", "\n")
    paragraphs = display_text.split("\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    para_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    st.markdown(
        f'<div class="result-card">{para_html}</div>',
        unsafe_allow_html=True,
    )

    st.divider()
    st.caption("📋 复制完整提示词")
    st.code(final_text, language="markdown")

    col_again, _ = st.columns([1, 3])
    with col_again:
        if st.button("✨ 再创作一个新的", use_container_width=True):
            st.session_state.clear()
            st.rerun()
