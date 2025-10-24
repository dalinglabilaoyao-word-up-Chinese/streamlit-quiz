
import os
import time
import random
import pandas as pd
import streamlit as st

# ===============================
# Page setup
# ===============================
st.set_page_config(page_title="Chinese Words Board Game", page_icon="🏮", layout="centered")

APP_TITLE = "Chinese Words Board Game"
DEFAULT_ALL = "questions_all.csv"   # 聚合自 /levels/*.csv
DEFAULT_CSV = "questions.csv"       # 运行时别名
LEVEL_DIR = "levels"
TYPE_OPTIONS = ["all", "red", "green", "yellow", "blue"]
DIFF_MIN, DIFF_MAX = 1, 10

# ===============================
# 🏮 Red-Gold Chinese Theme (CSS)
# ===============================
THEME_CSS = """
<style>
/* 背景：中式红金渐变 */
[data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 600px at 10% -10%, #8b0000 0%, #7a0000 35%, #4c0000 70%, #2a0000 100%);
  background-attachment: fixed;
}
/* 主内容白色半透明卡片容器 */
[data-testid="stAppViewContainer"] .main {
  background: rgba(255, 255, 255, 0.92);
  border-radius: 18px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.20);
  padding: 1.2rem;
}
/* 侧边栏：暗红背景 + 金色文字 */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #4c0000 0%, #300000 100%);
}
[data-testid="stSidebar"] * {
  color: #f7e9c0 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  color: #ffd166 !important;
}
/* 主区标题与文字 */
h1, h2, h3 { color: #7a1010; letter-spacing: 0.5px; }
p, label, span, div, li { color: #333; }
/* 按钮：红金渐变 */
.stButton > button {
  background: linear-gradient(135deg, #b71c1c 0%, #e53935 40%, #ffb300 100%);
  color: #ffeeca; border: none; border-radius: 12px;
  padding: 0.6rem 0.9rem; font-weight: 700; letter-spacing: 0.3px;
  box-shadow: 0 6px 16px rgba(183,28,28,0.35);
  transition: transform 0.12s ease, box-shadow 0.2s ease, filter 0.2s ease;
}
.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(183,28,28,0.45);
  filter: brightness(1.03);
}
.stButton > button:active { transform: translateY(0px) scale(0.99); }
/* 表格卡片化 */
[data-testid="stDataFrame"] {
  background: rgba(255,255,255,0.95);
  border-radius: 14px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
  padding: 0.4rem;
}
/* 输入控件圆角 + 金色描边 */
.stSelectbox, .stMultiSelect, .stTextInput, .stSlider { border-radius: 12px; }
div[data-baseweb="select"] > div, .stTextInput > div > div > input {
  border-radius: 10px !important;
  box-shadow: inset 0 0 0 1px rgba(255,179,0,0.55) !important;
}
/* 提示/告警样式 */
.stAlert { border-radius: 12px; }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ===============================
# Aggregation helpers
# ===============================
def list_level_files():
    return [os.path.join(LEVEL_DIR, f"questions_level_{i}.csv") for i in range(DIFF_MIN, DIFF_MAX+1)]

def rebuild_all_from_levels(write_to_disk=True):
    frames = []
    for p in list_level_files():
        if os.path.exists(p):
            try:
                frames.append(pd.read_csv(p))
            except Exception as e:
                st.warning(f"读取失败：{p}（{e}）")
    if frames:
        df = pd.concat(frames, ignore_index=True)
    else:
        df = pd.DataFrame(columns=["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"])
    # 补全列
    for col in ["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"]:
        if col not in df.columns:
            df[col] = ""
    if write_to_disk and len(df) > 0:
        df.to_csv(DEFAULT_ALL, index=False, encoding="utf-8-sig")
        df.to_csv(DEFAULT_CSV, index=False, encoding="utf-8-sig")
    return df

# ===============================
# Data helpers
# ===============================
@st.cache_data
def load_questions(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"])
    df = pd.read_csv(path)
    for col in ["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    # 标准化
    df["id"] = df["id"].astype(str)
    df["type"] = df["type"].astype(str).str.strip().str.lower()
    # 难度 1..10
    def _to_diff(x):
        try:
            v = int(str(x).strip())
        except Exception:
            v = 1
        return max(DIFF_MIN, min(DIFF_MAX, v))
    df["difficulty_num"] = df["difficulty"].apply(_to_diff)
    return df

def parse_options(opt_str: str):
    s = str(opt_str or "")
    if not s.strip():
        return []
    return [o.strip() for o in s.split("||") if o.strip()]

def filter_df(df, qtype, selected_diffs, tag_query):
    f = df.copy()
    if qtype and qtype != "all":
        f = f[f["type"] == qtype.lower()]
    if selected_diffs:
        f = f[f["difficulty_num"].isin(selected_diffs)]
    if tag_query:
        f = f[f["tags"].astype(str).str.contains(tag_query, case=False, na=False)]
    return f.reset_index(drop=True)

def draw_one(df, avoid_ids):
    avoid_ids = set(map(str, avoid_ids))
    pool = df[~df["id"].astype(str).isin(avoid_ids)]
    if len(pool) == 0:
        return None
    return pool.sample(1).iloc[0].to_dict()

def play_audio(src: str):
    if not src: return
    src = str(src).strip()
    if src.startswith("http"):
        st.audio(src)
    else:
        try:
            with open(src, "rb") as f:
                st.audio(f.read())
        except Exception as e:
            st.warning(f"音频无法读取：{src}（{e}）")

def show_image(src: str):
    if not src: return
    src = str(src).strip()
    if src.startswith("http") or os.path.exists(src):
        st.image(src, use_column_width=True)
    else:
        st.warning(f"图片未找到：{src}")

def get_stable_options(qid: str, raw_options: list, *, shuffle=True) -> list:
    if not raw_options:
        return []
    cache = st.session_state.shuffled_options
    if qid not in cache or not cache[qid]:
        opts = raw_options[:]
        if shuffle:
            random.shuffle(opts)
        cache[qid] = opts
    return cache[qid]

# ===============================
# State init
# ===============================
def init_state():
    rebuild_all_from_levels(write_to_disk=True)
    st.session_state.setdefault("df", load_questions(DEFAULT_ALL))
    st.session_state.setdefault("seen_ids", set())
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("current", None)
    st.session_state.setdefault("qtype_effective", "all")
    st.session_state.setdefault("diff_selected", list(range(DIFF_MIN, DIFF_MAX+1)))
    st.session_state.setdefault("tag_query", "")
    st.session_state.setdefault("shuffle_opts", True)
    st.session_state.setdefault("no_repeat", True)
    st.session_state.setdefault("shuffled_options", {})

init_state()

# ===============================
# Sidebar
# ===============================
with st.sidebar:
    st.header("🧰 设置（题库/筛选）")

    # 上传分级题库并重建
    with st.expander("📥 上传/替换分级题库（1–10）"):
        for i in range(DIFF_MIN, DIFF_MAX+1):
            up = st.file_uploader(f"等级 {i} 题库 CSV", type=["csv"], key=f"uploader_level_{i}")
            if up is not None:
                os.makedirs(LEVEL_DIR, exist_ok=True)
                path = os.path.join(LEVEL_DIR, f"questions_level_{i}.csv")
                with open(path, "wb") as f:
                    f.write(up.getbuffer())
                st.success(f"已更新：{path}")
        if st.button("🔄 重新构建全量题库"):
            st.session_state.df = rebuild_all_from_levels(write_to_disk=True)
            st.cache_data.clear()
            st.success("已根据分级题库重建全量题库")

    # 题型
    st.session_state.qtype_effective = st.selectbox("题型", TYPE_OPTIONS, index=0, help="选择 red/green/yellow/blue 或 all")

    # 难度（多选）
    selected_diff_sb = st.multiselect("难度（1–10）", list(range(1, 11)), default=list(range(1, 11)))
    st.session_state.diff_selected = selected_diff_sb if selected_diff_sb else list(range(1, 11))

    # 标签
    st.session_state.tag_query = st.text_input("标签筛选（包含关系）", value=st.session_state.tag_query)

    # 选项 & 不重复
    st.session_state.shuffle_opts = st.checkbox("打乱选项顺序", value=st.session_state.shuffle_opts)
    st.session_state.no_repeat = st.checkbox("抽题不重复（直到重置）", value=st.session_state.no_repeat)

    # 侧边栏重置
    if st.button("🗑️ 重置抽题记录（侧边栏）"):
        st.session_state.seen_ids = set()
        st.session_state.history = []
        st.session_state.current = None
        st.session_state.shuffled_options = {}
        st.success("抽题记录已重置。")

    # 导出（侧边栏常驻）
    hist_df_side = pd.DataFrame(st.session_state.history,
                                columns=["time","id","type","question","user_answer","correct_answer","correct"])
    st.download_button("⬇️ 导出作答记录 CSV（侧边栏）",
                       hist_df_side.to_csv(index=False).encode("utf-8-sig"),
                       file_name="history.csv", mime="text/csv")

# ===============================
# Main UI
# ===============================
st.title(APP_TITLE)
st.caption("🏮 红金中式主题 · 分级题库自动汇总 · 移动端优化")

# 当前筛选后的题库
df = st.session_state.df
pool = filter_df(df, st.session_state.qtype_effective, st.session_state.diff_selected, st.session_state.tag_query)

# 统计与工具条
total_count = len(pool)
pool_ids = set(pool["id"].astype(str)) if total_count else set()
seen_count = len(set(map(str, st.session_state.seen_ids)) & pool_ids)
remaining = max(0, total_count - seen_count)

st.subheader("🎲 抽题区")
st.caption(
    f"题目数量：{total_count}　已抽取：{seen_count}　剩余：{remaining}　"
    f"筛选：类型 **{st.session_state.qtype_effective}** · 难度 **{st.session_state.diff_selected or '全部'}** · 标签 **{st.session_state.tag_query or '（无）'}**"
)

col_actions = st.columns([1, 1, 1])
with col_actions[0]:
    if st.button("🎲 抽 1 题", use_container_width=True):
        avoid = st.session_state.seen_ids if st.session_state.no_repeat else set()
        row = draw_one(pool, avoid)
        if row is None:
            st.warning("没有可抽的题目了。请“重置题目”或放宽筛选条件。")
        else:
            st.session_state.current = row
            st.session_state.seen_ids.add(str(row["id"]))
            # 为当前题目固定选项顺序
            opts_raw = parse_options(row.get("options", ""))
            if opts_raw:
                _ = get_stable_options(row["id"], opts_raw, shuffle=st.session_state.shuffle_opts)

with col_actions[1]:
    if st.button("♻️ 重置题目", use_container_width=True):
        st.session_state.seen_ids = set()
        st.session_state.current = None
        st.session_state.shuffled_options = {}
        st.success("已重置抽题状态。")

with col_actions[2]:
    # 主界面导出（常驻）
    hist_df_top = pd.DataFrame(st.session_state.history,
                               columns=["time","id","type","question","user_answer","correct_answer","correct"])
    st.download_button("⬇️ 导出作答记录（主界面）",
                       hist_df_top.to_csv(index=False).encode("utf-8-sig"),
                       file_name="history.csv", mime="text/csv")

# 显示当前题
current = st.session_state.current
if current:
    st.markdown(
        f"**题号**：`{current['id']}`　**类型**：`{current['type']}`　**难度**：`{current.get('difficulty_num', current.get('difficulty',''))}`"
    )
    st.markdown(f"**题目**：{current['question']}")

    if current.get("passage"):
        with st.expander("📖 阅读短文（点击展开）", expanded=True):
            st.write(current["passage"])
    show_image(current.get("image_url", ""))
    play_audio(current.get("audio_url", ""))

    # 答题 UI
    raw_opts = parse_options(current.get("options", ""))
    options = get_stable_options(current["id"], raw_opts, shuffle=st.session_state.shuffle_opts)
    if options:
        user_answer = st.radio("请选择你的答案：", options, index=None, key=f"radio_{current['id']}")
    else:
        user_answer = st.text_area("你的答案（主观题）", height=120, key=f"text_{current['id']}")

    c1, c2, c3 = st.columns(3)
    if c1.button("✅ 提交答案", use_container_width=True, key=f"submit_{current['id']}"):
        if (options and user_answer is None) or (not options and not str(user_answer).strip()):
            st.warning("请先作答。")
        else:
            correct_answer = str(current.get("answer", "")).strip()
            is_correct = (str(user_answer).strip() == correct_answer) if options else None
            if is_correct is True:
                st.success("回答正确！🎉")
            elif is_correct is False:
                st.error(f"回答不正确。正确答案：{correct_answer}")
            else:
                st.info("已记录你的回答（主观题不自动判分）。")
            st.session_state.history.append([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                current["id"],
                current["type"],
                current["question"],
                str(user_answer),
                correct_answer,
                None if is_correct is None else bool(is_correct)
            ])

    if c2.button("👀 显示参考答案", use_container_width=True, key=f"show_{current['id']}"):
        st.info(current.get("answer", "（无参考答案）"))

    if c3.button("➡️ 下一题", use_container_width=True, key=f"next_{current['id']}"):
        avoid = st.session_state.seen_ids if st.session_state.no_repeat else set()
        row = draw_one(pool, avoid)
        if row is None:
            st.warning("没有可抽的题目了。请“重置题目”或放宽筛选条件。")
        else:
            st.session_state.current = row
            st.session_state.seen_ids.add(str(row["id"]))
            # 固定新题选项顺序
            opts_raw = parse_options(row.get("options", ""))
            if opts_raw:
                _ = get_stable_options(row["id"], opts_raw, shuffle=st.session_state.shuffle_opts)

st.markdown("---")

# ===============================
# 📊 实时作答结果（常驻表格）
# ===============================
st.markdown("## 📊 实时作答结果")
hist_cols = ["time","id","type","question","user_answer","correct_answer","correct"]
hist_df = pd.DataFrame(st.session_state.history, columns=hist_cols)

colA, colB, colC = st.columns([1,1,2])
with colA:
    if st.button("🧹 清空记录"):
        st.session_state.history = []
        st.success("已清空！")
with colB:
    st.download_button("⬇️ 导出 CSV",
                       hist_df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="history.csv", mime="text/csv")
with colC:
    total_done = len(hist_df)
    right = int(hist_df["correct"].sum()) if "correct" in hist_df and not hist_df.empty else 0
    accuracy = f"{(right/total_done*100):.1f}%" if total_done else "0%"
    st.caption(f"作答条数：{total_done} · 正确：{right} · 正确率：{accuracy}")

st.dataframe(hist_df, use_container_width=True, height=320)

st.caption("© Chinese Words Board Game · 红金中式主题")
