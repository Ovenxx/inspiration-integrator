import streamlit as st
import openai
import json
import re
import os
import random
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量（本地开发用）
load_dotenv()

# 获取 API Key
try:
    api_key = st.secrets.get("DEEPSEEK_API_KEY")
except Exception:
    api_key = None
if not api_key:
    api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    st.error("❌ 未找到 DEEPSEEK_API_KEY，请在 Streamlit Cloud Secrets 或 .env 文件中设置")
    st.stop()

client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

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

# =====================
# 八大灵感游乐项目
# =====================
RIDES = [
    {
        "id": "剧情过山车",
        "emoji": "🎢",
        "name": "剧情过山车",
        "vibe": "反转·戏剧·悬疑",
        "color": "#7c3aed",
        "desc": "跌宕起伏的情节，谁也不知道下一秒会发生什么",
        "角色": [
            "失忆特工", "替身新娘", "卧底警探", "神秘魔术师",
            "双重人格画家", "时空穿越者", "最后一个人类", "会说话的猫"
        ],
        "动作": [
            "在追查", "背叛了", "唤醒了", "伪装成",
            "发现了", "被囚禁在", "在等待", "永远消失了"
        ],
        "场景": [
            "摩天楼顶", "雨夜码头", "旋转餐厅", "废弃歌剧院",
            "午夜列车", "地下赌场", "雪山缆车", "摩洛哥集市"
        ]
    },
    {
        "id": "旋转童话",
        "emoji": "🎠",
        "name": "旋转童话",
        "vibe": "梦幻·甜美·纯真",
        "color": "#ec4899",
        "desc": "像童话书里掉出来的一页，温暖又治愈",
        "角色": [
            "小蘑菇精灵", "星星收集者", "云朵裁缝", "会跳舞的茶壶",
            "彩虹独角兽", "月亮上的兔子", "睡梦编织师", "一只发光的蜗牛"
        ],
        "动作": [
            "在缝制", "守护着", "在寻找", "乘着",
            "在收集", "唤醒了", "在等待", "不小心丢了"
        ],
        "场景": [
            "星光下的森林", "彩虹尽头", "云端城堡", "糖果花园",
            "月光湖面", "蘑菇村落", "永远春天的山谷", "星星坠落的地方"
        ]
    },
    {
        "id": "奇妙马戏团",
        "emoji": "🎪",
        "name": "奇妙马戏团",
        "vibe": "怪诞·幽默·超现实",
        "color": "#f59e0b",
        "desc": "荒诞离奇，在不可能的世界里狂欢",
        "角色": [
            "吞剑诗人", "会飞的企鹅", "气球小丑", "倒立行走的绅士",
            "火焰舞者", "会说话的稻草人", "走钢丝的章鱼", "魔术师的帽子"
        ],
        "动作": [
            "向星星", "在表演", "在追逐", "变出了",
            "从帽子里", "和影子", "在钢丝上", "一口吞下了"
        ],
        "场景": [
            "午夜马戏团帐篷", "飘浮的舞台", "巨大摩天轮顶端", "镜面迷宫",
            "烟花下的广场", "会旋转的观众席", "蒸汽朋克车厢", "云层上的绳索"
        ]
    },
    {
        "id": "自然漂流",
        "emoji": "🌊",
        "name": "自然漂流",
        "vibe": "治愈·壮丽·唯美",
        "color": "#06b6d4",
        "desc": "大自然的鬼斧神工，每一帧都是壁纸",
        "角色": [
            "发光水母", "树灵老者", "雪山雄鹰", "深海人鱼",
            "极光狐狸", "远古巨龟", "花中精灵", "冰川独角兽"
        ],
        "动作": [
            "在深海", "守护着", "穿越了", "在晨光中",
            "随着洋流", "从冰川", "在花海中", "向天空"
        ],
        "场景": [
            "深海裂谷", "极光冰原", "荧光海滩", "火山口湖",
            "红杉巨林", "沙漠绿洲", "海底珊瑚城", "悬空瀑布"
        ]
    },
    {
        "id": "暗黑鬼屋",
        "emoji": "🏚️",
        "name": "暗黑鬼屋",
        "vibe": "神秘·哥特·暗黑",
        "color": "#6b21a8",
        "desc": "黑暗中藏着秘密，令人心跳加速的美",
        "角色": [
            "镜中倒影", "提灯幽灵", "乌鸦信使", "吸血鬼伯爵",
            "稻草新娘", "无脸雕塑", "梦境猎手", "最后一个女巫"
        ],
        "动作": [
            "在废弃剧院", "从镜中", "在午夜", "封印了",
            "在月光下", "在追寻", "被诅咒的", "揭开了"
        ],
        "场景": [
            "废弃剧院舞台", "哥特教堂地下", "迷雾沼泽", "月光墓地",
            "维多利亚古宅", "血月下的塔楼", "黑森林深处的湖", "钟楼顶端"
        ]
    },
    {
        "id": "都市摩天轮",
        "emoji": "🎡",
        "name": "都市摩天轮",
        "vibe": "温暖·烟火·人情",
        "color": "#f97316",
        "desc": "城市角落里那些让人心头一暖的故事",
        "角色": [
            "便利店大叔", "天台少年", "深夜出租车司机", "书店老板娘",
            "地铁卖艺人", "失眠的摄影师", "最后一家报刊亭主", "阳台种花的老奶奶"
        ],
        "动作": [
            "在雨中等", "在深夜", "在清晨", "在摩天轮上",
            "从便利店", "在阳台上", "穿过", "在写一封"
        ],
        "场景": [
            "城市天台", "深夜便利店", "老城小巷", "雨中外滩",
            "末班地铁", "跨江大桥", "旧书店阁楼", "转角咖啡馆"
        ]
    },
    {
        "id": "星际穿梭",
        "emoji": "🚀",
        "name": "星际穿梭",
        "vibe": "科幻·赛博·未来",
        "color": "#10b981",
        "desc": "对抗引力，在霓虹与星空间漫游",
        "角色": [
            "数据幽灵", "仿生人", "太空垃圾回收员", "AI 诗人",
            "反重力赛车手", "脑机接口黑客", "最后的人类宇航员", "全息偶像"
        ],
        "动作": [
            "入侵了", "在霓虹雨", "从空间站", "在数据洪流中",
            "改写了", "在寻找", "对抗着", "在失重中"
        ],
        "场景": [
            "霓虹城市场景", "空间站穹顶", "火星殖民站台", "数据云海",
            "地下黑市", "空中花园", "废弃空间站", "虫洞边缘"
        ]
    },
    {
        "id": "热血道场",
        "emoji": "🥋",
        "name": "热血道场",
        "vibe": "武侠·动作·冒险",
        "color": "#ef4444",
        "desc": "刀光剑影，快意恩仇的热血世界",
        "角色": [
            "独臂刀客", "蒙面女侠", "醉酒僧人", "隐世剑圣",
            "沙漠镖师", "伞中刺客", "机关术传人", "最后的武士"
        ],
        "动作": [
            "在沙漠客栈", "在雨中", "在城楼上", "拔出了",
            "以一敌百", "在瀑布下", "在竹林", "和宿敌"
        ],
        "场景": [
            "沙漠孤城", "雪山之巅", "竹林深处", "瀑布之下",
            "长安夜市", "边关烽火台", "地下武馆", "江上孤舟"
        ]
    },
]

def extract_json(raw: str) -> str:
    decoder = json.JSONDecoder()
    match = re.search(r'```(?:json)?\s*\n?(.*?)```', raw, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
    pos = 0
    for ch in ('{', '['):
        pos = 0
        while True:
            start = raw.find(ch, pos)
            if start == -1:
                break
            try:
                obj, end = decoder.raw_decode(raw, start)
                return raw[start:end]
            except json.JSONDecodeError:
                pos = start + 1
                continue
    raise ValueError(f"无法从 AI 响应中提取 JSON。原始内容前 300 字符：{raw[:300].replace(chr(10), ' ')}")

def call_deepseek(messages, model="deepseek-chat", temperature=0.8, max_tokens=1200):
    response = client.chat.completions.create(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens
    )
    raw = response.choices[0].message.content
    st.session_state["_last_raw_response"] = raw
    return json.loads(extract_json(raw))

def build_progress_context() -> str:
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
        lines.append(f"\n🔜 接下来请问下一维度：【{remaining[0]}】")
    else:
        lines.append("\n🎉 所有维度已覆盖完毕，请设置 finish=true 生成最终提示词。")
    return "\n".join(lines)

def random_elements(ride_id):
    """从指定项目中随机抽取一套元素"""
    ride = next(r for r in RIDES if r["id"] == ride_id)
    return {
        "角色": random.choice(ride["角色"]),
        "动作": random.choice(ride["动作"]),
        "场景": random.choice(ride["场景"]),
    }

def synthesize(角色, 动作, 场景):
    """把三个元素合成一句话灵感"""
    # 去掉动作的介词头尾使句式自然
    act = 动作
    # 生成自然的中文句式
    templates = [
        f"{角色}{act}{场景}",
        f"在{场景}，{角色}{act}",
        f"{角色}在{场景}{act}",
    ]
    return random.choice(templates)

# ───────────────────────────────────────
# 页面样式
# ───────────────────────────────────────
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    .stApp { background: #f5f5f0; position: relative; overflow-x: hidden; }
    .stApp::before, .stApp::after { content: ''; position: fixed; border-radius: 50%; pointer-events: none; z-index: 0; opacity: 0.25; }
    .stApp::before { width: 500px; height: 500px; background: radial-gradient(circle, rgba(245, 166, 35, 0.06) 0%, transparent 70%); top: -150px; right: -150px; animation: floatGlow 12s ease-in-out infinite alternate; }
    .stApp::after { width: 400px; height: 400px; background: radial-gradient(circle, rgba(217, 119, 87, 0.06) 0%, transparent 70%); bottom: -100px; left: -100px; animation: floatGlow 15s ease-in-out infinite alternate-reverse; }
    @keyframes floatGlow { 0% { transform: translate(0, 0) scale(1); opacity: 0.2; } 100% { transform: translate(30px, -20px) scale(1.15); opacity: 0.35; } }
    .main .block-container { max-width: 800px; padding-top: 2rem; padding-bottom: 4rem; }
    .app-header { text-align: center; padding-bottom: 2rem; margin-bottom: 1.5rem; border-bottom: 1px solid #e5e5e0; }
    .app-header h1 { font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; color: #1a1a1a; margin-bottom: 0.25rem; }
    .app-header .accent-line { width: 48px; height: 3px; background: linear-gradient(90deg, #d97757, #f5a623); border-radius: 2px; margin: 0.75rem auto; }
    .app-header .subtitle { font-size: 0.9rem; color: #6b6b6b; font-weight: 400; }

    /* ─── 双模式入口 ─── */
    .mode-grid { display: flex; gap: 1.25rem; margin: 2rem auto; max-width: 640px; }
    .mode-card {
        flex: 1; padding: 2rem 1.5rem; border-radius: 18px; text-align: center;
        cursor: pointer; transition: all 0.2s ease; border: 2px solid #e5e5e0;
        background: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .mode-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
    .mode-card .icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
    .mode-card .title { font-size: 1.2rem; font-weight: 600; color: #1a1a1a; margin-bottom: 0.4rem; }
    .mode-card .desc { font-size: 0.85rem; color: #8b8b8b; line-height: 1.5; }
    .mode-card.active { border-color: #d97757; background: #fdf6f3; }
    .mode-card.active .title { color: #d97757; }

    /* ─── 入口描述区 ─── */
    .home-tagline {
        text-align: center; color: #6b6b6b; font-size: 0.95rem; line-height: 1.6;
        max-width: 520px; margin: 0 auto 1.5rem auto;
    }

    /* ─── 游乐园 - 项目选择 ─── */
    .playground-header {
        text-align: center; margin-bottom: 1.5rem;
    }
    .playground-header h2 { font-size: 1.4rem; font-weight: 600; color: #1a1a1a; margin-bottom: 0.25rem; }
    .playground-header p { font-size: 0.85rem; color: #8b8b8b; }

    .ride-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.85rem; max-width: 680px; margin: 0 auto; }
    .ride-card {
        display: flex; align-items: center; gap: 0.85rem;
        padding: 1rem 1.1rem; border-radius: 14px; background: #ffffff;
        border: 1.5px solid #e5e5e0; cursor: pointer; transition: all 0.15s ease;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    }
    .ride-card:hover {
        transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        border-color: #d0d0cb;
    }
    .ride-card .ride-emoji { font-size: 2.2rem; flex-shrink: 0; }
    .ride-card .ride-info { flex: 1; min-width: 0; }
    .ride-card .ride-name { font-size: 1rem; font-weight: 600; color: #1a1a1a; }
    .ride-card .ride-vibe { font-size: 0.75rem; color: #8b8b8b; margin-top: 0.1rem; }
    .ride-card .ride-desc { font-size: 0.78rem; color: #6b6b6b; margin-top: 0.2rem; line-height: 1.3; }

    /* ─── 翻书页 ─── */
    .book-header {
        text-align: center; margin-bottom: 1.5rem;
    }
    .book-header h2 { font-size: 1.3rem; font-weight: 600; color: #1a1a1a; }
    .book-header p { font-size: 0.85rem; color: #8b8b8b; margin-top: 0.15rem; }
    .book-header .back-link {
        display: inline-block; font-size: 0.8rem; color: #d97757;
        cursor: pointer; margin-top: 0.3rem;
    }

    .element-grid {
        display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.85rem;
        max-width: 680px; margin: 0 auto;
    }
    .element-column { display: flex; flex-direction: column; align-items: center; }
    .element-column .category-label {
        font-size: 0.75rem; font-weight: 600; color: #8b8b8b; text-transform: uppercase;
        letter-spacing: 0.05em; margin-bottom: 0.5rem;
    }
    .element-card {
        width: 100%; padding: 1.1rem 0.75rem; border-radius: 16px;
        background: #ffffff; border: 2px solid #ecece5; text-align: center;
        font-size: 0.95rem; font-weight: 500; color: #1a1a1a; line-height: 1.4;
        min-height: 72px; display: flex; align-items: center; justify-content: center;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        position: relative;
        box-shadow: 0 3px 10px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
    }
    .element-card:hover { border-color: #d0d0cb; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.07); }
    .element-card.flipping { animation: cardFlip 0.35s cubic-bezier(0.34, 1.56, 0.64, 1); }
    .element-card.locked {
        border-color: #d97757; background: linear-gradient(135deg, #fdf6f3 0%, #fff8f0 100%);
        box-shadow: 0 0 0 3px rgba(217, 119, 87, 0.12), 0 4px 14px rgba(217, 119, 87, 0.08);
    }
    .element-card .lock-badge {
        position: absolute; top: -7px; right: -7px; font-size: 0.65rem;
        background: #d97757; color: white; width: 22px; height: 22px;
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        box-shadow: 0 2px 6px rgba(217, 119, 87, 0.3);
        animation: lockPop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    @keyframes cardFlip {
        0% { transform: rotateX(-8deg) scale(0.92); opacity: 0.3; }
        100% { transform: rotateX(0) scale(1); opacity: 1; }
    }
    @keyframes lockPop {
        0% { transform: scale(0); }
        70% { transform: scale(1.25); }
        100% { transform: scale(1); }
    }

    .book-actions {
        display: flex; justify-content: center; gap: 0.75rem;
        margin: 1.5rem auto; max-width: 400px;
    }

    /* ─── 灵感预览条 ─── */
    .inspiration-preview {
        max-width: 680px; margin: 1.25rem auto 0 auto;
        padding: 1rem 1.25rem; background: linear-gradient(135deg, #fdf6f3, #fff8f0);
        border-radius: 14px; border: 1.5px solid #f0e0d8;
        text-align: center; position: relative; overflow: hidden;
    }
    .inspiration-preview::before {
        content: ''; position: absolute; inset: 0;
        background: linear-gradient(90deg, transparent, rgba(217,119,87,0.03), transparent);
        animation: shimmer 2.5s ease-in-out infinite;
    }
    @keyframes shimmer {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    .inspiration-preview .label { font-size: 0.75rem; color: #d97757; font-weight: 600; letter-spacing: 0.03em; margin-bottom: 0.3rem; position: relative; z-index: 1; }
    .inspiration-preview .sentence { font-size: 1rem; font-weight: 500; color: #1a1a1a; line-height: 1.5; position: relative; z-index: 1; }

    /* ─── 聊天气泡 ─── */
    .chat-container { display: flex; flex-direction: column; gap: 0.75rem; margin: 1rem 0; }
    .chat-bubble { max-width: 88%; padding: 0.75rem 1rem; border-radius: 14px; font-size: 0.92rem; line-height: 1.55; word-break: break-word; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .chat-bubble.user { align-self: flex-end; background: #1a1a1a; color: #f5f5f0; border-bottom-right-radius: 4px; }
    .chat-bubble.assistant { align-self: flex-start; background: #ffffff; color: #1a1a1a; border: 1px solid #e5e5e0; border-bottom-left-radius: 4px; }

    /* ─── 输入框 ─── */
    .stTextInput > label { display: none !important; }
    .stTextInput > div > div > input { border: 1px solid #e0e0db; border-radius: 10px; padding: 0.75rem 1rem; font-size: 0.95rem; background: #ffffff; transition: border-color 0.2s, box-shadow 0.2s; }
    .stTextInput > div > div > input:focus { border-color: #d97757; box-shadow: 0 0 0 3px rgba(217, 119, 87, 0.12); }
    div[data-testid="stForm"] .stTextInput > div > div > input { border-radius: 8px; padding: 0.6rem 0.85rem; font-size: 0.9rem; }

    /* ─── 按钮 ─── */
    div.stButton button { border-radius: 100px !important; border: 1.5px solid #e0e0db !important; background: #ffffff !important; color: #1a1a1a !important; font-size: 0.9rem !important; font-weight: 500 !important; padding: 0.6rem 1.25rem !important; width: 100%; transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) !important; }
    div.stButton button:hover { border-color: #d97757 !important; background: #fdf6f3 !important; color: #d97757 !important; box-shadow: 0 4px 12px rgba(217, 119, 87, 0.10) !important; transform: translateY(-1px); }
    div.stButton button:active { transform: scale(0.96) !important; }

    /* ─── 进度 ─── */
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #d97757, #f5a623); border-radius: 100px; }
    .stProgress > div > div { background: #e5e5e0; border-radius: 100px; height: 6px; }
    .question-header { font-size: 1.15rem; font-weight: 600; color: #1a1a1a; line-height: 1.5; margin: 1.25rem 0 0.75rem 0; padding: 1rem 1.25rem; background: #ffffff; border-radius: 12px; border: 1px solid #e5e5e0; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
    .stSpinner > div { color: #d97757 !important; }
    .streamlit-expanderHeader { font-size: 0.85rem; color: #6b6b6b; font-weight: 500; border-radius: 8px; }
    .result-card { background: #ffffff; border: 1px solid #e5e5e0; border-radius: 14px; padding: 1.5rem 1.75rem; margin: 1rem 0; box-shadow: 0 2px 8px rgba(0,0,0,0.04); line-height: 1.8; font-size: 0.95rem; color: #2a2a2a; }
    .stage-tag { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.78rem; font-weight: 500; color: #d97757; background: #fdf6f3; padding: 0.25rem 0.7rem; border-radius: 100px; margin-top: 1rem; }
    .stAlert { border-radius: 10px; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .dim-pills { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0; }
    .dim-pill { font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 100px; border: 1px solid #e5e5e0; background: #ffffff; color: #6b6b6b; }
    .dim-pill.active { border-color: #d97757; background: #fdf6f3; color: #d97757; }
    .dim-pill.done { border-color: #b8d4b8; background: #f0f7f0; color: #4a8a4a; }

    /* rides header color accent */
    .ride-color-bar { height: 3px; border-radius: 2px; margin: 0.5rem auto; width: 40px; }
</style>
""", unsafe_allow_html=True)

# ===== 初始化状态 =====
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
if "stage" not in st.session_state:
    st.session_state.stage = "home"
if "current_choices" not in st.session_state:
    st.session_state.current_choices = []
if "max_rounds" not in st.session_state:
    st.session_state.max_rounds = len(DIMENSIONS)
    st.session_state.round = 0
if "covered_dimensions" not in st.session_state:
    st.session_state.covered_dimensions = []
if "current_ride" not in st.session_state:
    st.session_state.current_ride = None
if "locked_elements" not in st.session_state:
    st.session_state.locked_elements = {}
if "flip_count" not in st.session_state:
    st.session_state.flip_count = 0

# ===== 页面头部 =====
st.markdown("""
<div class="app-header">
    <h1>Inspiration Integrator</h1>
    <div class="accent-line"></div>
    <div class="subtitle">把模糊的灵感，变成精准的视频指令</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════
#  HOME — 双模式入口
# ══════════════════════════════════════
if st.session_state.stage == "home":
    st.markdown("""
    <div class="home-tagline">
        你有一个想做的视频，但不知道从哪开始？<br>
        或者只是想随便逛逛，等灵感自己撞上来？
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="mode-card" id="mode-hasidea">
            <div class="icon">✍️</div>
            <div class="title">我有想法</div>
            <div class="desc">脑海里已经有画面的雏形了<br>让 AI 帮你打磨成完整提示词</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✍️ 我有想法", key="btn_has_idea", use_container_width=True):
            st.session_state.stage = "has_idea"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="mode-card" id="mode-playground">
            <div class="icon">🎪</div>
            <div class="title">来找灵感</div>
            <div class="desc">没有想法，随便玩玩<br>让灵感自己来找你</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🎪 来找灵感", key="btn_playground", use_container_width=True):
            st.session_state.stage = "playground"
            st.rerun()

# ══════════════════════════════════════
#  HAS IDEA — 直接输入
# ══════════════════════════════════════
elif st.session_state.stage == "has_idea":
    if st.button("← 返回首页", key="back_home_1"):
        st.session_state.clear()
        st.rerun()

    st.markdown('<div style="text-align:center; color:#6b6b6b; font-size:0.9rem; margin:1rem 0;">输入一个简单的想法，AI 会帮你一步步完善</div>', unsafe_allow_html=True)

    user_seed = st.text_input(
        "谁，在哪，干什么？",
        placeholder="例如：C罗来内马尔家里跳东北大秧歌",
        label_visibility="collapsed"
    )
    if user_seed:
        st.session_state.messages.append({"role": "user", "content": user_seed})
        st.session_state.stage = "choosing"
        st.rerun()

# ══════════════════════════════════════
#  PLAYGROUND — 选项目
# ══════════════════════════════════════
elif st.session_state.stage == "playground":
    st.markdown("""
    <div class="playground-header">
        <h2>🎡 灵感游乐园</h2>
        <p>挑一个你想玩的项目，翻开灵感之书</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← 返回首页", key="back_home_2"):
        st.session_state.clear()
        st.rerun()

    # 8 个项目，2x4 用 st.columns 实现
    for row_idx in range(0, len(RIDES), 2):
        row_rides = RIDES[row_idx:row_idx+2]
        cols = st.columns(2)
        for col_idx, ride in enumerate(row_rides):
            with cols[col_idx]:
                btn_label = f"{ride['emoji']}  {ride['name']}\n{ride['vibe']}\n{ride['desc']}"
                # 每个项目按钮显示 emoji + 名称 + 风格
                if st.button(
                    f"{ride['emoji']}  {ride['name']}",
                    key=f"ride_{ride['id']}",
                    use_container_width=True,
                ):
                    st.session_state.current_ride = ride["id"]
                    st.session_state.locked_elements = {}
                    st.session_state.flip_count = 0
                    elems = random_elements(ride["id"])
                    st.session_state.current_elements = elems
                    st.session_state.stage = "ride_play"
                    st.rerun()
                # 子描述文字
                st.caption(f"{ride['vibe']} · {ride['desc']}")

# ══════════════════════════════════════
#  RIDE PLAY — 翻书排列组合
# ══════════════════════════════════════
elif st.session_state.stage == "ride_play":
    ride = next(r for r in RIDES if r["id"] == st.session_state.current_ride)

    # 返回按钮
    if st.button("← 换个项目", key="back_playground"):
        st.session_state.stage = "playground"
        st.rerun()

    # 当前元素
    elems = st.session_state.get("current_elements", random_elements(ride["id"]))
    locked = st.session_state.get("locked_elements", {})
    categories = ["角色", "动作", "场景"]

    # 书头
    st.markdown(f"""
    <div class="book-header">
        <h2>{ride['emoji']} {ride['name']}</h2>
        <p style="color:{ride['color']}">{ride['vibe']}</p>
        <div class="ride-color-bar" style="background:{ride['color']}"></div>
        <p style="font-size:0.85rem; color:#8b8b8b;">点击元素卡片锁定它，再翻页就不会变了</p>
    </div>
    """, unsafe_allow_html=True)

    # 三列元素
    cols = st.columns(3)
    for idx, cat in enumerate(categories):
        with cols[idx]:
            st.markdown(f'<div class="category-label">{cat}</div>', unsafe_allow_html=True)
            val = elems.get(cat, "")
            is_locked = locked.get(cat, False)
            lock_badge = '<div class="lock-badge">🔒</div>' if is_locked else ""
            lock_class = "locked" if is_locked else ""
            flip_class = " flipping" if st.session_state.get("_just_flipped", False) else ""
            st.markdown(
                f'<div class="element-card {lock_class}{flip_class}" id="card_{cat}">'
                f'{lock_badge}<span>{val}</span></div>',
                unsafe_allow_html=True
            )
            # 锁定/解锁小按钮
            if is_locked:
                if st.button(f"🔓 解锁", key=f"unlock_{cat}"):
                    locked[cat] = False
                    st.session_state.locked_elements = locked
                    st.rerun()
            else:
                if st.button(f"🔒 锁定", key=f"lock_{cat}"):
                    locked[cat] = True
                    st.session_state.locked_elements = locked
                    st.rerun()

    st.session_state["_just_flipped"] = False

    # 操作按钮
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📖 翻一页", key="flip", use_container_width=True):
            # 只重新生成未锁定的
            for cat in categories:
                if not locked.get(cat, False):
                    # 从同项目同类别随机抽取
                    pool = ride[cat]
                    new_val = random.choice(pool)
                    # 确保不和当前一样（如果可能）
                    if len(pool) > 1:
                        while new_val == elems.get(cat):
                            new_val = random.choice(pool)
                    elems[cat] = new_val
            st.session_state.current_elements = elems
            st.session_state.flip_count += 1
            st.session_state["_just_flipped"] = True
            st.rerun()

    with col_b:
        # 合成灵感预览
        sentence = synthesize(elems["角色"], elems["动作"], elems["场景"])
        st.session_state["_sentence"] = sentence
        if st.button("✨ 合成灵感", key="synthesize", use_container_width=True):
            st.session_state.stage = "ride_complete"
            st.session_state.final_inspiration = sentence
            st.session_state.final_inspiration_ride = ride
            st.rerun()

    # 当前合成预览
    st.markdown(f"""
    <div class="inspiration-preview">
        <div class="label">当前组合</div>
        <div class="sentence">{sentence}</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════
#  RIDE COMPLETE — 灵感预览 → 继续完善
# ══════════════════════════════════════
elif st.session_state.stage == "ride_complete":
    ride = st.session_state.final_inspiration_ride
    sentence = st.session_state.final_inspiration

    st.markdown(f"<div class='stage-tag'>✨ 灵感就绪</div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="book-header">
        <h2>{ride['emoji']} 灵感合成</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="inspiration-preview" style="padding:1.5rem 2rem;">
        <div class="label">你的灵感一句话</div>
        <div class="sentence" style="font-size:1.15rem;">{sentence}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("""
    <div style="text-align:center; color:#6b6b6b; font-size:0.9rem; margin-bottom:1rem;">
        要继续把这个灵感完善成完整的视频提示词吗？<br>
        AI 会帮你补充画面细节、风格和镜头语言
    </div>
    """, unsafe_allow_html=True)

    col_a, col_b, _ = st.columns([1, 1, 0.3])
    with col_a:
        if st.button("🎨 继续完善", key="continue_refine", use_container_width=True):
            # 把灵感句子作为初始输入，进入维度对话
            st.session_state.messages.append({"role": "user", "content": sentence})
            st.session_state.stage = "choosing"
            st.rerun()
    with col_b:
        if st.button("🎲 重新玩", key="replay_ride", use_container_width=True):
            st.session_state.stage = "playground"
            st.rerun()


# ══════════════════════════════════════
#  CHOOSING — 维度对话（复用已有逻辑）
# ══════════════════════════════════════
elif st.session_state.stage == "choosing":
    if st.session_state.round >= st.session_state.max_rounds:
        st.session_state.messages.append({"role": "user", "content": "请直接生成最终的视频提示词。"})
        with st.spinner("正在生成最终提示词..."):
            try:
                raw_response = client.chat.completions.create(
                    model="deepseek-chat", messages=st.session_state.messages,
                    temperature=0.7, max_tokens=1200
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
    progress = done_count / total
    st.progress(progress)

    progress_msg = build_progress_context()
    messages_with_progress = st.session_state.messages + [
        {"role": "user", "content": progress_msg}
    ]

    with st.spinner("正在为您构思细节..."):
        try:
            data = call_deepseek(messages_with_progress)
        except ValueError as e:
            st.error("🤖 AI 返回的内容无法解析")
            st.info(e)
            with st.expander("🔍 AI 原始返回（供调试）"):
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

    if data.get("finish"):
        final_prompt = data.get("final_prompt", "")
        if not final_prompt:
            st.error("AI 返回了完成信号但没有 final_prompt，请重试。")
            st.stop()
        st.session_state.stage = "finished"
        st.session_state.final_prompt = final_prompt
        st.rerun()

    question = data.get("question", "请选择以下选项：")
    choices = data.get("choices", [])

    if not choices:
        st.warning("AI 没有提供选项，尝试重新生成...")
        st.session_state.messages.append({
            "role": "user", "content": "请给我选择题（有 label 和 value 的选项），不要直接结束。"
        })
        st.rerun()

    remaining_dim = [d for d in DIMENSIONS if d not in st.session_state.covered_dimensions]
    if remaining_dim:
        st.session_state.covered_dimensions.append(remaining_dim[0])

    ai_raw_json = json.dumps(data, ensure_ascii=False, indent=2)
    st.session_state.messages.append({"role": "assistant", "content": ai_raw_json})

    with st.expander("📜 查看对话记录", expanded=False):
        chat_html = '<div class="chat-container">'
        for msg in st.session_state.messages:
            if msg["role"] == "system":
                continue
            role_class = "user" if msg["role"] == "user" else "assistant"
            content = msg["content"]
            if msg["role"] == "assistant":
                try:
                    json_obj = json.loads(content)
                    if isinstance(json_obj, dict) and "question" in json_obj:
                        q = json_obj.get("question", "")
                        choices_list = json_obj.get("choices", [])
                        if choices_list:
                            choice_parts = [f'  · {c.get("label","")}' for c in choices_list]
                            body_html = f"{q}<br>" + "<br>".join(choice_parts)
                        else:
                            body_html = q
                        chat_html += f'<div class="chat-bubble {role_class}">{body_html}</div>'
                        continue
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
            chat_html += f'<div class="chat-bubble {role_class}">{content}</div>'
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

    st.markdown(f'<div class="question-header">{question}</div>', unsafe_allow_html=True)
    round_prefix = st.session_state.round
    cols = st.columns(len(choices))
    for i, choice in enumerate(choices):
        with cols[i]:
            label = choice.get("label", f"选项{i+1}")
            value = choice.get("value", label)
            if st.button(label, key=f"r{round_prefix}_c{i}", use_container_width=True):
                st.session_state.messages.append({
                    "role": "user", "content": f"我选择：{value}"
                })
                st.rerun()

    with st.expander("✏️ 都不是？自己补充"):
        with st.form("custom_form"):
            custom_input = st.text_input("请输入你的想法", label_visibility="collapsed")
            submitted = st.form_submit_button("提交", use_container_width=True)
            if submitted and custom_input:
                st.session_state.messages.append({
                    "role": "user", "content": custom_input
                })
                st.rerun()

# ══════════════════════════════════════
#  FINISHED — 结果展示
# ══════════════════════════════════════
elif st.session_state.stage == "finished":
    st.markdown('<div class="stage-tag">✨ 生成完成</div>', unsafe_allow_html=True)
    st.markdown("### 您的视频提示词")

    final_text = st.session_state.final_prompt
    display_text = final_text.replace("\\n", "\n")
    paragraphs = [p.strip() for p in display_text.split("\n") if p.strip()]
    para_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    st.markdown(f'<div class="result-card">{para_html}</div>', unsafe_allow_html=True)
    st.divider()
    st.caption("📋 复制完整提示词")
    st.code(final_text, language="markdown")

    col_again, _ = st.columns([1, 3])
    with col_again:
        if st.button("✨ 再创作一个新的", use_container_width=True):
            st.session_state.clear()
            st.rerun()
