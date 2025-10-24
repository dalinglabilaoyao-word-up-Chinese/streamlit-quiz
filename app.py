
import os
import time
import random
import pandas as pd
import streamlit as st

# =====================================
# Page setup
# =====================================
st.set_page_config(page_title="抽题游戏（难度1-10·支持多选）", page_icon="🎯", layout="centered")

APP_TITLE = "🎯 随机抽题（支持难度 1–10 多选 / 区间）"
DEFAULT_CSV = "questions.csv"

TYPE_OPTIONS = ["all", "red", "green", "yellow", "blue"]
DIFF_MIN, DIFF_MAX = 1, 10
DIFF_ALL = list(range(DIFF_MIN, DIFF_MAX + 1))

# =====================================
# Data helpers
# =====================================
@st.cache_data
def load_questions(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    # Ensure basic columns exist
    for col in ["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    # Normalize columns
    df["type"] = df["type"].astype(str).str.strip()
    # Coerce difficulty to integer in 1..10 (fallback to 1 if invalid/empty)
    def _to_diff(x):
        try:
            v = int(str(x).strip())
        except Exception:
            v = DIFF_MIN
        if v < DIFF_MIN: v = DIFF_MIN
        if v > DIFF_MAX: v = DIFF_MAX
        return v
    df["difficulty_num"] = df["difficulty"].apply(_to_diff)
    return df

def parse_options(opt_str: str):
    return [o.strip() for o in str(opt_str).split("||") if str(o).strip()]

def filter_df(df, qtype, selected_diffs, tag_query):
    f = df.copy()
    if qtype and qtype != "all":
        f = f[f["type"].str.lower() == qtype.lower()]
    if selected_diffs:
        f = f[f["difficulty_num"].isin(selected_diffs)]
    if tag_query:
        f = f[f["tags"].str.contains(tag_query, case=False, na=False)]
    return f.reset_index(drop=True)

def draw_one(df, avoid_ids):
    pool = df[~df["id"].isin(avoid_ids)]
    if len(pool) == 0:
        return None
    return pool.sample(1).iloc[0].to_dict()

# Media helpers
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
            st.warning(f"音频无法读取：{src} ({e})")

def show_image(src: str):
    if not src: return
    src = str(src).strip()
    if src.startswith("http") or os.path.exists(src):
        st.image(src, use_column_width=True)
    else:
        st.warning(f"图片未找到：{src}")

# =====================================
# State init
# =====================================
def init_state():
    ss = st.session_state
    ss.setdefault("df", load_questions(DEFAULT_CSV))
    ss.setdefault("seen_ids", set())
    ss.setdefault("history", [])
    ss.setdefault("qtype_effective", "all")
    ss.setdefault("diff_selected", DIFF_ALL)  # store as list of ints
    ss.setdefault("tag_query", "")
    ss.setdefault("current", None)
    ss.setdefault("shuffle_opts", True)
    ss.setdefault("no_repeat", True)
    ss.setdefault("shuffled_options", {})

init_state()

# =====================================
# Sidebar (desktop)
# =====================================
with st.sidebar:
    st.header("🧰 设置（侧边栏）")
    uploaded = st.file_uploader("上传题库 CSV（可替换默认题库）", type=["csv"], key="uploader_sb")
    if uploaded is not None:
        st.session_state.df = pd.read_csv(uploaded)
        st.success("已加载上传的题库！")
        st.session_state.shuffled_options = {}
        st.session_state.current = None
        st.session_state.seen_ids = set()

    # 题型
    def on_change_qtype_sb():
        st.session_state.qtype_effective = st.session_state.qtype_sb
    st.selectbox("题型", TYPE_OPTIONS, index=TYPE_OPTIONS.index(st.session_state.qtype_effective),
                 key="qtype_sb", on_change=on_change_qtype_sb)

    # 难度（多选 + 区间联动）
    st.markdown("**难度（1–10）**")
    # Multi-select
    def on_change_diff_multi():
        st.session_state.diff_selected = sorted(set(st.session_state.diff_multi))
        # 同步 slider
        if st.session_state.diff_selected:
            st.session_state.diff_range = [min(st.session_state.diff_selected), max(st.session_state.diff_selected)]
        else:
            st.session_state.diff_range = [DIFF_MIN, DIFF_MAX]
    st.multiselect("选择多个难度", DIFF_ALL, default=st.session_state.diff_selected,
                   key="diff_multi", on_change=on_change_diff_multi)

    # Range slider
    def on_change_diff_range():
        lo, hi = st.session_state.diff_range
        st.session_state.diff_selected = list(range(lo, hi+1))
        st.session_state.diff_multi = st.session_state.diff_selected
    default_range = st.session_state.get("diff_range", [min(st.session_state.diff_selected),
                                                        max(st.session_state.diff_selected)])
    st.slider("选择难度区间", DIFF_MIN, DIFF_MAX, default_range, step=1, key="diff_range", on_change=on_change_diff_range)

    # 标签
    def on_change_tag_sb():
        st.session_state.tag_query = st.session_state.tag_sb
    st.text_input("标签筛选（包含关系）", value=st.session_state.tag_query, key="tag_sb", on_change=on_change_tag_sb)

    st.checkbox("打乱选项顺序", value=st.session_state.shuffle_opts, key="shuffle_opts")
    st.checkbox("抽题不重复（直到重置）", value=st.session_state.no_repeat, key="no_repeat")

    if st.button("🗑️ 重置抽题记录"):
        st.session_state.seen_ids = set()
        st.session_state.history = []
        st.session_state.current = None
        st.session_state.shuffled_options = {}
        st.success("抽题记录已重置。")

    # 导出
    if st.session_state.history:
        hist = pd.DataFrame(st.session_state.history,
                            columns=["time","id","type","question","user_answer","correct_answer","correct"])
        st.download_button("⬇️ 导出作答记录 CSV",
                           hist.to_csv(index=False).encode("utf-8-sig"),
                           file_name="history.csv", mime="text/csv")

# =====================================
# Main UI (mobile quick controls)
# =====================================
st.title(APP_TITLE)
st.caption("提示：手机/iPad 看不到侧边栏时，可在下方直接选择题型与难度。")

st.markdown("### 📱 移动端快速选择")
col1, col2 = st.columns(2)

with col1:
    def on_change_qtype_main():
        st.session_state.qtype_effective = st.session_state.qtype_main
        st.session_state.qtype_sb = st.session_state.qtype_main
    st.selectbox("题型", TYPE_OPTIONS, index=TYPE_OPTIONS.index(st.session_state.qtype_effective),
                 key="qtype_main", on_change=on_change_qtype_main)

with col2:
    def on_change_range_main():
        lo, hi = st.session_state.diff_range_main
        st.session_state.diff_selected = list(range(lo, hi+1))
        st.session_state.diff_multi = st.session_state.diff_selected
        st.session_state.diff_range = [lo, hi]
    # A compact range slider for mobile
    default_range_main = [min(st.session_state.diff_selected), max(st.session_state.diff_selected)]
    st.slider("难度区间", DIFF_MIN, DIFF_MAX, default_range_main, step=1,
              key="diff_range_main", on_change=on_change_range_main)

# Current filters
sel_lo, sel_hi = min(st.session_state.diff_selected), max(st.session_state.diff_selected)
pool = filter_df(st.session_state.df, st.session_state.qtype_effective, st.session_state.diff_selected, st.session_state.tag_query)

st.subheader("🎲 抽题区")
st.caption(f"筛选：类型 **{st.session_state.qtype_effective}** · 难度 **{sel_lo}-{sel_hi}** · 标签包含 **{st.session_state.tag_query or '（无）'}**")
st.caption(f"题目数量：{len(pool)}")

# Draw controls
def get_stable_options(qid: str, raw_options: list) -> list:
    if not raw_options:
        return []
    if not st.session_state.shuffle_opts:
        return raw_options
    cache = st.session_state.shuffled_options
    if qid not in cache or not cache[qid]:
        tmp = raw_options[:]
        random.shuffle(tmp)
        cache[qid] = tmp
    return cache[qid]

if st.button("🎲 抽 1 题", use_container_width=True):
    avoid = st.session_state.seen_ids if st.session_state.no_repeat else set()
    row = draw_one(pool, avoid)
    if row is None:
        st.warning("没有可抽的题目了。请重置抽题记录或更改筛选条件。")
    else:
        st.session_state.current = row
        st.session_state.seen_ids.add(row["id"])
        opts_raw = parse_options(row.get("options",""))
        if opts_raw:
            st.session_state.shuffled_options[row["id"]] = get_stable_options(row["id"], opts_raw)

current = st.session_state.current
if current:
    st.markdown(f"**编号**：`{current['id']}`　**类型**：`{current['type']}`　**难度**：`{current.get('difficulty_num','')}`")
    st.markdown(f"**题目**：{current['question']}")

    if current.get("passage"):
        with st.expander("📖 阅读短文（点击展开）", expanded=True):
            st.write(current["passage"])
    show_image(current.get("image_url",""))
    play_audio(current.get("audio_url",""))

    raw_options = parse_options(current.get("options",""))
    options = get_stable_options(current["id"], raw_options)
    user_answer = None
    if options:
        user_answer = st.radio("请选择你的答案：", options, index=None, key=f"radio_{current['id']}")
    else:
        user_answer = st.text_area("你的答案：", height=120, placeholder="在此输入……（主观题不自动判分）", key=f"text_{current['id']}")

    c1, c2, c3 = st.columns(3)
    if c1.button("✅ 提交答案", use_container_width=True, key=f"submit_{current['id']}"):
        if user_answer is None or (isinstance(user_answer, str) and len(user_answer.strip())==0):
            st.warning("请先作答。")
        else:
            correct_answer = current.get("answer","").strip()
            is_select = bool(options)
            is_correct = (str(user_answer).strip() == correct_answer) if is_select else None
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
        st.info(current.get("answer","（无参考答案）"))

    if c3.button("➡️ 下一题", use_container_width=True, key=f"next_{current['id']}"):
        avoid = st.session_state.seen_ids if st.session_state.no_repeat else set()
        row = draw_one(pool, avoid)
        if row is None:
            st.warning("没有可抽的题目了。请重置抽题记录或更改筛选条件。")
        else:
            st.session_state.current = row
            st.session_state.seen_ids.add(row["id"])
            opts_raw = parse_options(row.get("options",""))
            if opts_raw:
                st.session_state.shuffled_options[row["id"]] = get_stable_options(row["id"], opts_raw)

st.markdown("---")
st.caption("难度范围 1–10 · 支持多选与区间筛选 · 题型 red/green/yellow/blue · 支持音频/图片/短文。")
