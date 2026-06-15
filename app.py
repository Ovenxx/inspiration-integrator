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

# 预定义的对话维度（程序硬性追踪，AI 无法跳过或重复）
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


def strip_markdown_json(raw: str) -> str:
    """从可能包含 markdown 代码块的文本中提取 JSON 内容"""
    # 先尝试匹配 ```json ... ```
    match = re.search(r'```json\s*\n?(.*?)```', raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 再尝试匹配 ``` ... ```
    match = re.search(r'```\s*\n?(.*?)```', raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 无代码块标记，直接返回
    return raw.strip()


def call_deepseek(messages, model="deepseek-chat", temperature=0.8, max_tokens=800):
    """调用 DeepSeek API 并返回解析后的 JSON"""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    raw = response.choices[0].message.content
    cleaned = strip_markdown_json(raw)
    return json.loads(cleaned)


def build_progress_context() -> str:
    """构建当前维度的进度上下文，供 AI 知道哪些已经问过了，下一轮该问什么"""
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

st.title("Inspiration Integrator 🎬")
st.caption('把模糊的“谁在哪干什么”变成顶级视频提示词')

# ===== 阶段1：初始输入 =====
if st.session_state.stage == "input":
    user_seed = st.text_input("谁，在哪，干什么？", placeholder="例如：C罗来内马尔家里跳东北大秧歌")
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
                    max_tokens=800
                )
                final_prompt = raw_response.choices[0].message.content
                cleaned = strip_markdown_json(final_prompt)
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

    # ===== 构建带进度上下文的 messages 并调用 API =====
    progress_msg = build_progress_context()
    # 插入进度上下文（作为 user 消息，让 AI 看到）
    messages_with_progress = st.session_state.messages + [
        {"role": "user", "content": progress_msg}
    ]

    with st.spinner("正在为您构思细节..."):
        try:
            data = call_deepseek(messages_with_progress)
        except Exception as e:
            st.error(f"🤖 AI 响应解析失败：{e}")
            st.info("点击下方按钮重试，或修改输入后重新开始。")
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

    # ===== 提取本轮维度并记录 =====
    question = data.get("question", "请选择以下选项：")
    choices = data.get("choices", [])

    if not choices:
        st.warning("AI 没有提供选项，尝试重新生成...")
        st.session_state.messages.append({
            "role": "user",
            "content": "请给我选择题（有 label 和 value 的选项），不要直接结束。"
        })
        st.rerun()

    # 记录已问维度：将剩余的第一个维度标记为已覆盖
    remaining = [d for d in DIMENSIONS if d not in st.session_state.covered_dimensions]
    if remaining:
        st.session_state.covered_dimensions.append(remaining[0])

    # ===== 把 AI 的问题存入对话历史 =====
    ai_question_text = f"[维度{len(st.session_state.covered_dimensions)}] {question}"
    if choices:
        choice_texts = "；".join([f"{c.get('label','')}: {c.get('value','')}" for c in choices])
        ai_question_text += f"\n选项：{choice_texts}"
    st.session_state.messages.append({"role": "assistant", "content": ai_question_text})

    # ===== 显示对话记录 =====
    with st.expander("📜 查看对话记录", expanded=False):
        for i, msg in enumerate(st.session_state.messages):
            if msg["role"] == "system":
                continue
            role_label = "🧑 你" if msg["role"] == "user" else "🤖 AI"
            st.markdown(f"**{role_label}：** {msg['content']}")
            if i < len(st.session_state.messages) - 1:
                st.divider()

    # ===== 显示进度条 =====
    progress = len(st.session_state.covered_dimensions) / len(DIMENSIONS)
    st.progress(progress, text=f"进度 {len(st.session_state.covered_dimensions)}/{len(DIMENSIONS)}")

    # ===== 显示当前问题 + 选项按钮 =====
    st.markdown(f"### {question}")
    st.session_state.current_question = question
    st.session_state.current_choices = choices

    round_prefix = st.session_state.round
    cols = st.columns(len(choices))
    for i, choice in enumerate(choices):
        with cols[i]:
            label = choice.get("label", f"选项{i+1}")
            value = choice.get("value", label)
            if st.button(label, key=f"r{round_prefix}_c{i}"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": f"我选择：{value}"
                })
                st.rerun()

    # 自定义输入
    with st.expander("都不是？自己补充"):
        with st.form("custom_form"):
            custom_input = st.text_input("请输入你的想法")
            submitted = st.form_submit_button("提交")
            if submitted and custom_input:
                st.session_state.messages.append({
                    "role": "user",
                    "content": custom_input
                })
                st.rerun()

# ===== 阶段3：展示结果 =====
elif st.session_state.stage == "finished":
    st.success("✨ 您的专属视频提示词已生成！")
    # 多行展示：用 markdown 渲染，自动换行
    final_text = st.session_state.final_prompt
    st.markdown(final_text)
    st.divider()
    st.caption("一键复制完整的提示词：")
    st.code(final_text, language="markdown")
    if st.button("再创作一个新的"):
        st.session_state.clear()
        st.rerun()
