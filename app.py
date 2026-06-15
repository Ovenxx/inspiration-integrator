import streamlit as st
import openai
import json
import re
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量（本地开发用）
load_dotenv()

# 获取 API Key：优先 Streamlit Cloud 的 secrets，其次本地 .env 文件
api_key = st.secrets.get("DEEPSEEK_API_KEY") if hasattr(st, "secrets") else None
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

SYSTEM_PROMPT = """你是一个世界顶级的"视觉创意提取师"。你的工作是通过多轮选择题对话，把用户模糊的"谁在哪干什么"想法，扩展成一条可用于 AI 视频生成的高质量提示词。

## 你的输出格式
你必须严格按照以下 JSON 格式输出，不要添加任何 markdown 代码块标记或额外说明：

{
  "question": "当前要问用户的问题",
  "choices": [
    {"label": "选项A短标签", "value": "选项A的详细描述，会拼入最终提示词"},
    {"label": "选项B短标签", "value": "选项B的详细描述"},
    {"label": "选项C短标签", "value": "选项C的详细描述"}
  ],
  "finish": false,
  "final_prompt": ""
}

当收集的信息足够生成完整提示词时（通常 3-5 轮），设置 "finish": true 并提供 final_prompt：

{
  "question": "",
  "choices": [],
  "finish": true,
  "final_prompt": "最终的视频提示词"
}

## 对话策略（每轮一个维度）
第1轮: 确认"谁"的视觉细节——年龄、服装、表情、动作特征
第2轮: 确认"在哪"的场景细节——环境、光照、氛围、时间
第3轮: 确认"干什么"的具体动作——动作方式、节奏、情绪
第4轮: 确认视觉风格——电影/动画/写实/赛博朋克等风格方向
第5轮: 确认镜头语言——景别、运镜、视角、景深等
第6轮及以后: 如有需要继续补充细节

## 最终提示词要求
生成的 final_prompt 必须是英文的长段落（100-200词），包含以下要素：
- [主体描述] 在外观/场景/动作各维度都有细节
- [场景环境] 光照、色彩、氛围
- [镜头语言] 景别、运镜
- [风格参考] visual style / art direction
- [技术参数] 分辨率、帧率等（如适用）
用丰富的视觉形容词写一条连贯的自然语言段落。"""


def strip_markdown_json(raw: str) -> str:
    """从可能包含 markdown 代码块的文本中提取 JSON 内容（Bug #2）"""
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
    """调用 DeepSeek API 并返回解析后的 JSON（Bug #4：异常封装）"""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    raw = response.choices[0].message.content
    cleaned = strip_markdown_json(raw)
    return json.loads(cleaned)


# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
if "stage" not in st.session_state:
    st.session_state.stage = "input"  # input / choosing / finished
if "current_choices" not in st.session_state:
    st.session_state.current_choices = []
if "max_rounds" not in st.session_state:
    st.session_state.max_rounds = 5
    st.session_state.round = 0

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
    # Bug #12：先检查是否已达最大轮次，避免白调 API
    if st.session_state.round >= st.session_state.max_rounds:
        st.session_state.messages.append({"role": "user", "content": "请直接生成最终的视频提示词。"})
        with st.spinner("正在生成最终提示词..."):
            try:
                raw_response = client.chat.completions.create(
                    model="deepseek-chat",  # Bug #6：统一模型名
                    messages=st.session_state.messages,
                    temperature=0.7,
                    max_tokens=500
                )
                final_prompt = raw_response.choices[0].message.content
                # Bug #7：强制生成路径也做 JSON 提取
                cleaned = strip_markdown_json(final_prompt)
                try:
                    maybe_json = json.loads(cleaned)
                    if isinstance(maybe_json, dict) and maybe_json.get("final_prompt"):
                        final_prompt = maybe_json["final_prompt"]
                except json.JSONDecodeError:
                    pass  # 不是 JSON，就用原始输出
            except Exception as e:
                st.error(f"API 调用失败：{e}")
                st.stop()

        st.session_state.stage = "finished"
        st.session_state.final_prompt = final_prompt
        st.rerun()

    # 调用 DeepSeek 生成问题
    with st.spinner("正在为您构思细节..."):
        try:
            data = call_deepseek(st.session_state.messages)
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

    # 检查 AI 是否主动完成
    if data.get("finish"):
        final_prompt = data.get("final_prompt", "")
        if not final_prompt:
            st.error("AI 返回了完成信号但没有 final_prompt，请重试。")
            st.stop()
        st.session_state.stage = "finished"
        st.session_state.final_prompt = final_prompt
        st.rerun()

    # 显示新问题与选项
    question = data.get("question", "请选择以下选项：")
    choices = data.get("choices", [])

    if not choices:
        st.warning("AI 没有提供选项，尝试重新生成...")
        st.session_state.messages.append({
            "role": "user",
            "content": "请给我选择题（有 label 和 value 的选项），不要直接结束。"
        })
        st.rerun()

    st.markdown(f"### {question}")
    st.session_state.current_question = question
    st.session_state.current_choices = choices

    # Bug #5：用 round 前缀避免不同轮次按钮 key 冲突
    cols = st.columns(len(choices))
    for i, choice in enumerate(choices):
        with cols[i]:
            label = choice.get("label", f"选项{i+1}")
            value = choice.get("value", label)
            if st.button(label, key=f"r{st.session_state.round}_c{i}"):
                st.session_state.messages.append({
                    "role": "user",
                    "content": f"我选择：{value}"
                })
                st.rerun()

    # Bug #1 + #9：用 st.form 避免自定义输入无限循环和重复提交
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
    st.code(st.session_state.final_prompt, language="markdown")
    if st.button("再创作一个新的"):
        st.session_state.clear()
        st.rerun()
