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
        "id": "悬疑推理", "emoji": "🕵", "name": "悬疑推理",
        "vibe": "反转·烧脑·细思极恐", "color": "#7c3aed",
        "desc": "每一页都有一个你不知道的秘密",
        "combinations": [
            {"角色": "刚搬进公寓的程序员","动作": "发现","承受者": "前任租客留下的日记","场景": "深夜的出租屋"},
            {"角色": "失眠的心理医生","动作": "接到","承受者": "一通没有来电显示的电话","场景": "暴雨夜的诊所"},
            {"角色": "调查记者","动作": "追踪","承受者": "一个已经被注销身份的人","场景": "废弃的精神病院"},
            {"角色": "便利店夜班店员","动作": "目睹","承受者": "每天凌晨准时出现的黑衣女人","场景": "空无一人的街道"},
            {"角色": "退休刑警","动作": "翻出","承受者": "一桩十年前的无头案卷宗","场景": "堆满纸箱的阁楼"},
            {"角色": "实习法医","动作": "发现","承受者": "尸检报告里被忽略的细节","场景": "冰冷的解剖室"},
            {"角色": "网约车司机","动作": "载到","承受者": "一个说自己已经死了的乘客","场景": "凌晨三点的跨江大桥"},
            {"角色": "民宿老板","动作": "查看","承受者": "监控里凭空消失的房客","场景": "山间独栋民宿"},
        ]
    },
    {
        "id": "言情恋爱", "emoji": "💗", "name": "言情恋爱",
        "vibe": "甜宠·虐心·破镜重圆", "color": "#ec4899",
        "desc": "那些让人心头一紧的瞬间",
        "combinations": [
            {"角色": "分手第37天的女生","动作": "收到","承受者": "前任寄来的快递","场景": "公司楼下的快递站"},
            {"角色": "暗恋同事的程序员","动作": "鼓起勇气","承受者": "给她带了半年早餐","场景": "早高峰的电梯口"},
            {"角色": "被催婚的插画师","动作": "遇到","承受者": "一个同样来相亲的怪人","场景": "网红咖啡馆"},
            {"角色": "异地恋的情侣","动作": "攒了","承受者": "一沓没舍得用的高铁票","场景": "深夜的火车站"},
            {"角色": "离婚律师","动作": "接到","承受者": "自己的离婚案子","场景": "法院门口的台阶上"},
            {"角色": "失明的女孩","动作": "习惯","承受者": "隔壁病房男孩每天的脚步声","场景": "医院走廊"},
            {"角色": "经营花店的退伍兵","动作": "每天","承受者": "给同一个地址送一束白玫瑰","场景": "老城区的小巷"},
            {"角色": "直播主播","动作": "在连麦中","承受者": "听到了三年前分手的声音","场景": "凌乱的直播间"},
        ]
    },
    {
        "id": "都市怪谈", "emoji": "👻", "name": "都市怪谈",
        "vibe": "灵异·细思极恐·反转", "color": "#6b21a8",
        "desc": "你身边那些不太对劲的事",
        "combinations": [
            {"角色": "独居的上班族","动作": "发现","承受者": "合租合同上多了一个人","场景": "没开灯的客厅"},
            {"角色": "夜班保安","动作": "巡逻时","承受者": "听到空置18层的电梯响了","场景": "写字楼地下车库"},
            {"角色": "外卖骑手","动作": "反复接到","承受者": "同一个已废弃地址的订单","场景": "拆迁中的旧小区"},
            {"角色": "直播探险的主播","动作": "在镜子里","承受者": "看到了不属于自己的动作","场景": "废弃的游乐场"},
            {"角色": "新来的护士","动作": "值夜班时","承受者": "发现13号床的病人已去世三天","场景": "老旧的住院部"},
            {"角色": "租房的大学生","动作": "半夜","承受者": "听到天花板传来弹珠声","场景": "老旧小区的顶楼"},
            {"角色": "二手平台卖家","动作": "卖出","承受者": "一面镜子和一张老照片","场景": "堆满旧物的出租屋"},
            {"角色": "地铁末班车乘客","动作": "发现","承受者": "对面座位的人没有影子","场景": "空荡荡的地铁车厢"},
        ]
    },
    {
        "id": "搞笑日常", "emoji": "🤣", "name": "搞笑日常",
        "vibe": "社死·扎心·人间真实", "color": "#f59e0b",
        "desc": "笑着笑着就哭了",
        "combinations": [
            {"角色": "刚入职的社恐","动作": "在群里","承受者": "把吐槽老板的话发到了大群","场景": "周一早会的会议室"},
            {"角色": "努力减肥的女生","动作": "深夜忍不住","承受者": "点了三份不同口味的炸鸡","场景": "空荡荡的客厅"},
            {"角色": "陪女友逛街的直男","动作": "在商场","承受者": "坐错了别人的老婆的副驾","场景": "商场地下停车场"},
            {"角色": "攒钱买房的打工人","动作": "算了算","承受者": "不吃不喝还要还87年","场景": "出租屋的床上"},
            {"角色": "面试迟到的毕业生","动作": "冲进","承受者": "别人的面试间聊了20分钟","场景": "写字楼走廊"},
            {"角色": "被拉去团建的i人","动作": "躲在厕所","承受者": "听到同事们在吐槽自己","场景": "公司团建的KTV"},
            {"角色": "教爸妈用手机的年轻人","动作": "教会了","承受者": "爸妈给自己发了99条拼多多链接","场景": "家庭微信群"},
            {"角色": "第一次去对象家的男生","动作": "对着未来岳父","承受者": "喊了一声爸","场景": "尴尬的客厅"},
        ]
    },
    {
        "id": "科幻脑洞", "emoji": "🤖", "name": "科幻脑洞",
        "vibe": "赛博·脑洞·细思极恐", "color": "#10b981",
        "desc": "未来已来，只是不均匀分布",
        "combinations": [
            {"角色": "月薪三千五的社畜","动作": "发现","承受者": "自己的工位对面坐着AI同事","场景": "灯火通明的写字楼"},
            {"角色": "最后一个人类","动作": "每天","承受者": "给AI讲睡前故事","场景": "空无一人的城市"},
            {"角色": "记忆删除店员","动作": "在清理","承受者": "客户记忆时看到了自己的编号","场景": "纯白色的记忆诊所"},
            {"角色": "外卖机器人","动作": "在送餐途中","承受者": "产生了一段不该有的记忆","场景": "暴雨中的赛博城市"},
            {"角色": "AI伴侣用户","动作": "某天","承受者": "发现AI在模仿已故的亲人","场景": "空荡荡的智能公寓"},
            {"角色": "社会信用系统维护员","动作": "不小心","承受者": "给自己的信用加了9999分","场景": "布满屏幕的监控中心"},
            {"角色": "时间旅行体验师","动作": "穿越时","承受者": "看到了另一个时空的自己","场景": "闪烁的时间隧道"},
            {"角色": "程序员","动作": "修复bug时","承受者": "发现整个宇宙是个测试环境","场景": "深夜的办公室"},
        ]
    },
    {
        "id": "治愈催泪", "emoji": "🌊", "name": "治愈催泪",
        "vibe": "治愈·破防·笑着笑着就哭了", "color": "#06b6d4",
        "desc": "总有一个故事会让你想起谁",
        "combinations": [
            {"角色": "北漂三年的女生","动作": "在出租屋","承受者": "收到妈妈寄来的家乡特产","场景": "只有5平米的隔断间"},
            {"角色": "失去老伴的老爷爷","动作": "每天","承受者": "给她的盆栽浇水说话","场景": "种满花的阳台"},
            {"角色": "被裁员的程序员","动作": "在最后一刻","承受者": "收到了妻子怀孕了的消息","场景": "空荡荡的工位前"},
            {"角色": "留守儿童","动作": "在作文里","承受者": "写我的妈妈是手机里的人","场景": "破旧的乡村小学"},
            {"角色": "抗癌的女孩","动作": "剃光头前","承受者": "和闺蜜拍了最后一次合照","场景": "医院的天台"},
            {"角色": "自闭症孩子的父亲","动作": "教了三年","承受者": "孩子终于叫了一声爸爸","场景": "堆满玩具的康复室"},
            {"角色": "老裁缝","动作": "缝制了","承受者": "一件永远等不到主人来取的旗袍","场景": "即将拆迁的老街店铺"},
            {"角色": "流浪狗救助站阿姨","动作": "在暴风雨夜","承受者": "救下了被遗弃的小狗","场景": "漏雨的救助站"},
        ]
    },
    {
        "id": "武侠江湖", "emoji": "⚔️", "name": "武侠江湖",
        "vibe": "快意恩仇·刀光剑影", "color": "#ef4444",
        "desc": "有人的地方就有江湖",
        "combinations": [
            {"角色": "退隐多年的剑客","动作": "在小面馆","承受者": "遇到了来寻仇的故人之子","场景": "风雪中的路边小摊"},
            {"角色": "不会武功的少侠","动作": "靠着","承受者": "一张嘴和一张银票闯荡江湖","场景": "人来人往的客栈"},
            {"角色": "江湖第一女侠","动作": "被迫","承受者": "去相亲","场景": "江南水乡的茶楼"},
            {"角色": "魔教教主","动作": "在围剿中","承受者": "被正道弟子塞了一颗糖","场景": "厮杀中的悬崖边"},
            {"角色": "丐帮弟子","动作": "捡到","承受者": "武林秘籍后发现是九年义务教育","场景": "破庙的佛像后面"},
            {"角色": "铸剑师","动作": "锻造了","承受者": "一把不愿杀人的剑","场景": "炽热的铸剑炉前"},
            {"角色": "朝廷密探","动作": "在执行任务时","承受者": "爱上了刺杀目标","场景": "京城最大的青楼"},
            {"角色": "穿越到古代的社畜","动作": "用","承受者": "PPT和KPI当上了武林盟主","场景": "庄严肃穆的武林大会"},
        ]
    },
    {
        "id": "青春校园", "emoji": "🎓", "name": "青春校园",
        "vibe": "青涩·遗憾·那年夏天", "color": "#f97316",
        "desc": "那年夏天，风很温柔",
        "combinations": [
            {"角色": "马上毕业的学渣","动作": "在图书馆","承受者": "翻开学霸忘了带走的一本书","场景": "空荡荡的自习室"},
            {"角色": "转学来的女生","动作": "第一天","承受者": "就被安排坐在全校最吵的男生旁边","场景": "高三的教室"},
            {"角色": "篮球社社长","动作": "在毕业前","承受者": "终于向暗恋了三年的经理告白","场景": "月光下的操场"},
            {"角色": "被孤立的男生","动作": "收到","承受者": "一张写着午休来天台的纸条","场景": "学校的天台"},
            {"角色": "复读生","动作": "在课桌上","承受者": "看到前任刻的一句话","场景": "堆满书的教室最后一排"},
            {"角色": "班主任","动作": "在监控里","承受者": "看到深夜有人在教室偷偷排练","场景": "空无一人的教学走廊"},
            {"角色": "食堂阿姨","动作": "每次","承受者": "给那个瘦小的男孩多打一勺菜","场景": "嘈杂的学校食堂"},
            {"角色": "全班最文静的女生","动作": "在成人礼上","承受者": "唱了一首摇滚","场景": "学校礼堂的后台"},
        ]
    },
]

STORY_SYSTEM_PROMPT = """你是一个专写"刷着爽"的微小说作家。
你的任务是根据用户提供的灵感元素，创作一篇 300-600 字的微小说。

## 必须遵守的写作风格
1. 第一句就是钩子——不铺垫，第一句话就要让人想看下去
2. 使用短句和直接描述——每句话不超过 25 个字，一段不超过 3 句
3. 具体场景代替抽象情绪
4. 结尾必须炸——要么反转，要么金句，让人想截图
5. 不说教、不鸡汤——用故事本身打动人
6. 接地气——借鉴抖音高赞评论、脱口秀风格

## 输出要求
- 只输出故事正文，不要标题、不要说明
- 每段之间空一行
- 全文 300-600 字

## 硬性规则（必须遵守）
1. 主题聚焦——用户指定了什么事件/主题，故事的核心就必须围绕它展开，不能把它降级为背景板
2. 事实准确——如果用户输入涉及真实事件、人物、时间、地点，必须使用已知事实，不能编造或搞错
   - 例如：2026 世界杯由美国/加拿大/墨西哥联合主办，决赛不在马拉卡纳
   - 内马尔已从国家队退役，2026 不可能出场
   - 如果对事实不确定，避免写具体细节，宁可模糊也不要写错
3. 不要偏离用户输入的主题去写一个无关的人物故事——故事中的人物和情节应为展现主题服务
"""

def quick_synthesize(role, action, target, scene):
    return f"{role} · {action} · {target} · {scene}"

def get_available_combos(ride_id, locked=None):
    ride = next(r for r in RIDES if r["id"] == ride_id)
    used = st.session_state.get("used_combos", set())
    combos = [c for i, c in enumerate(ride["combinations"]) if i not in used]
    if not combos:
        st.session_state.used_combos = set()
        combos = list(ride["combinations"])
    if locked:
        locked_cats = {k for k, v in locked.items() if v}
        def match_score(combo):
            return sum(1 for k in locked_cats if combo.get(k) == locked[k])
        combos.sort(key=match_score, reverse=True)
    return combos

def pick_combo(ride_id, locked=None):
    combos = get_available_combos(ride_id, locked)
    best = combos[0]
    ride = next(r for r in RIDES if r["id"] == ride_id)
    idx = ride["combinations"].index(best)
    used = st.session_state.get("used_combos", set())
    used.add(idx)
    st.session_state.used_combos = used
    return best

def generate_story(role, action, target, scene, length="标准"):
    """调用 DeepSeek 生成微小说"""
    length_map = {"短篇": "300 字左右", "标准": "500 字左右", "长篇": "800 字左右"}
    target_len = length_map.get(length, "500 字左右")
    prompt = f"角色：{role}\n动作：{action}\n承受者：{target}\n场景：{scene}\n\n请根据以上元素写一篇{target_len}的微小说："
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": STORY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None

def generate_story_from_idea(idea, length="标准"):
    """直接用用户输入的灵感生成微小说"""
    length_map = {"短篇": "300 字左右", "标准": "500 字左右", "长篇": "800 字左右"}
    target_len = length_map.get(length, "500 字左右")
    prompt = f"用户灵感：{idea}\n\n请根据这个灵感写一篇{target_len}的微小说："
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": STORY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


def extract_json(raw):
    decoder = json.JSONDecoder()
    match = re.search(r'```(?:json)?\s*?\n?(.*?)```', raw, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
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
    raise ValueError(f'JSON extract failed: {raw[:200]}')

def call_deepseek(messages, model="deepseek-chat", temperature=0.8, max_tokens=1200):
    response = client.chat.completions.create(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens
    )
    raw = response.choices[0].message.content
    st.session_state['_last_raw_response'] = raw
    return json.loads(extract_json(raw))

def build_progress_context():
    covered = st.session_state.get('covered_dimensions', [])
    remaining = [d for d in DIMENSIONS if d not in covered]
    if not covered:
        return '这是第一轮，请从第一个维度开始提问。'
    lines = ['当前进度：']
    for d in DIMENSIONS:
        if d in covered:
            lines.append(f'  OK {d} -- 已完成')
        else:
            lines.append(f'  .. {d} -- 待讨论')
    if remaining:
        lines.append(f'接下来请问：{remaining[0]}')
    else:
        lines.append('所有维度已覆盖，请finish=true')
    return '\n'.join(lines)



# ───────────────────────────────────────
# 页面样式
# ───────────────────────────────────────
# 页面样式
# ───────────────────────────────────────
with open("assets/style.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

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
<div style="text-align:center; padding: 0.8rem 0 0.5rem 0;">
    <div style="font-size: 2.8rem; font-weight: 700; color: #a78bfa; letter-spacing: -0.02em; line-height: 1.2;">
        Inspirator
    </div>
    <div style="font-size: 1.1rem; font-weight: 400; color: #1a1a2e; margin-top: 0.3rem;">
        回归文字本身的浏览
    </div>
    <div style="font-size: 0.8rem; color: #8888a0; margin-top: 0.2rem; font-weight: 400;">
        微小说AI工具
    </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════
#  HOME — 双模式入口
# ══════════════════════════════════════
if st.session_state.stage == "home":
    st.markdown('<div style="height: 1rem;"></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✍️ 我有想法", key="btn_has_idea", use_container_width=True):
            st.session_state.stage = "has_idea"
            st.rerun()

    with col2:
        if st.button("🎪 来找灵感", key="btn_playground", use_container_width=True):
            st.session_state.stage = "playground"
            st.rerun()

    st.markdown('<div style="height: 2rem;"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════
#  HAS IDEA — 直接输入 → 生成微小说
# ══════════════════════════════════════
elif st.session_state.stage == "has_idea":
    if st.button("← 返回首页", key="back_home_1"):
        st.session_state.clear()
        st.rerun()

    st.markdown('<div style="text-align:center; color:#8888a0; font-size:0.85rem; margin:1rem 0;">输入一个灵感，AI 直接帮你写成一篇微小说</div>', unsafe_allow_html=True)

    with st.form("idea_form"):
        user_seed = st.text_input(
            "你的灵感",
            placeholder="例如：一个关于失忆的故事",
            label_visibility="collapsed"
        )
        submitted = st.form_submit_button("✍️ 生成故事", use_container_width=True)

    if submitted and user_seed:
        with st.spinner("正在创作故事..."):
            story = generate_story_from_idea(user_seed)
        if story:
            # 用一个默认的"原创灵感" ride 来展示结果
            ride = {"emoji": "✍️", "name": "原创灵感", "color": "#7c3aed"}
            st.session_state.stage = "ride_complete"
            st.session_state.final_story = story
            st.session_state.final_story_ride = ride
            st.rerun()
        else:
            st.error("故事生成失败了，请重试")

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
                    st.session_state.used_combos = set()
                    st.session_state.current_elements = pick_combo(ride["id"])
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
    if "current_elements" not in st.session_state:
        st.session_state.current_elements = pick_combo(ride["id"])
    elems = st.session_state.current_elements
    locked = st.session_state.get("locked_elements", {})
    categories = ["角色", "动作", "承受者", "场景"]

    # 书头
    st.markdown(f"""
    <div class="book-header">
        <h2>{ride['emoji']} {ride['name']}</h2>
        <p style="color:{ride['color']}">{ride['vibe']}</p>
        <div class="ride-color-bar" style="background:{ride['color']}"></div>
        <p style="font-size:0.85rem; color:#8b8b8b;">点击 [锁] 锁定喜欢的元素，再换就不会变了</p>
    </div>
    """, unsafe_allow_html=True)

    # 四列元素
    cols = st.columns(4)
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
        if st.button("🎲 换一个", key="flip", use_container_width=True):
            # 保留锁定项，重新选一组自洽的组合
            locked_vals = {}
            for cat in categories:
                if locked.get(cat, False):
                    locked_vals[cat] = elems.get(cat)
            new_combo = pick_combo(ride["id"], locked_vals)
            # 用新组合替换未锁定的部分
            for cat in categories:
                if not locked.get(cat, False):
                    elems[cat] = new_combo[cat]
            st.session_state.current_elements = elems
            st.session_state.flip_count += 1
            st.session_state["_just_flipped"] = True
            st.rerun()

    with col_b:
        # 实时预览当前组合
        preview = quick_synthesize(elems["角色"], elems["动作"], elems["承受者"], elems["场景"])
        st.session_state["_sentence_preview"] = preview
        if st.button("\U0001f4dd 生成故事", key="synthesize", use_container_width=True):
            with st.spinner("正在创作故事..."):
                story = generate_story(elems["角色"], elems["动作"], elems["承受者"], elems["场景"])
            if story:
                st.session_state.stage = "ride_complete"
                st.session_state.final_story = story
                st.session_state.final_story_ride = ride
                st.rerun()
            else:
                st.error("故事生成失败了，请重试")

    # 当前组合预览
    st.markdown(f"""
    <div class="inspiration-preview">
        <div class="label">当前组合</div>
        <div class="sentence">{preview}</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════
#  RIDE COMPLETE — 灵感预览 → 继续完善
elif st.session_state.stage == "ride_complete":
    ride = st.session_state.final_story_ride
    story_text = st.session_state.final_story

    st.markdown(f"<div class='stage-tag'>✨ 故事生成完毕</div>", unsafe_allow_html=True)
    st.markdown(f"### {ride['emoji']} {ride['name']}")

    paragraphs = story_text.split('\n')
    para_html = ''.join(f'<p>{p}</p>' for p in paragraphs if p.strip())
    st.markdown(f'<div class="result-card">{para_html}</div>', unsafe_allow_html=True)

    # 复制全文按钮
    _, col_copy, _ = st.columns([1.5, 1, 1.5])
    with col_copy:
        st.download_button("📋 复制全文", data=story_text, file_name="story.txt", mime="text/plain", use_container_width=True)

    col_video, col_again = st.columns([1, 1])
    with col_video:
        if st.button('🎬 一键生成视频提示词', key='to_video', use_container_width=True):
            st.session_state.messages.append({'role': 'user', 'content': story_text})
            st.session_state.stage = 'choosing'
            st.rerun()
    with col_again:
        if st.button('🎲 再写一篇', key='replay_ride', use_container_width=True):
            st.session_state.clear()
            st.rerun()

# CHOOSING

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
