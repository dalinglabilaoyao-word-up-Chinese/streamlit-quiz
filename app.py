
import os
import time
import random
import pandas as pd
import streamlit as st

# ===============================
# Page setup (mobile friendly)
# ===============================
st.set_page_config(page_title="抽题游戏（移动端优化）", page_icon="🎲", layout="centered")

APP_TITLE = "🎯 随机抽题小游戏（移动端优化 · 支持 red/green/yellow/blue）"
DEFAULT_CSV = "questions.csv"

TYPE_OPTIONS = ["all", "red", "green", "yellow", "blue"]
DIFF_OPTIONS = ["all", "easy", "medium", "hard"]

# ===============================
# Data helpers
# ===============================
@st.cache_data
def load_questions(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    # ensure required columns exist
    for col in ["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    # normalize
    df["type"] = df["type"].astype(str).str.strip()
    df["difficulty"] = df["difficulty"].astype(str).str.strip().str.lower()
    return df

def parse_options(opt_str: str):
    return [o.strip() for o in str(opt_str).split("||") if str(o).strip()]

def filter_df(df, qtype, diff, tag_query):
    f = df.copy()
    if qtype and qtype != "all":
        f = f[f["type"].str.lower() == qtype.lower()]
    if diff and diff != "all":
        f = f[f["difficulty"].str.lower() == diff.lower()]
    if tag_query:
        f = f[f["tags"].str.contains(tag_query, case=False, na=False)]
    return f.reset_index(drop=True)

def draw_one(df, avoid_ids):
    pool = df[~df["id"].isin(avoid_ids)]
    if len(pool) == 0:
        return None
    return pool.sample(1).iloc[0].to_dict()

# Media helpers: support URL or local file
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

# ===============================
# State init
# ===============================
def init_state():
    ss = st.session_state
    ss.setdefault("df", load_questions(DEFAULT_CSV))
    ss.setdefault("seen_ids", set())
    ss.setdefault("history", [])  # [time,id,type,question,user_answer,correct_answer,correct]
    # effective filters
    ss.setdefault("qtype_effective", "all")
    ss.setdefault("diff_effective", "all")
    ss.setdefault("tag_query", "")
    ss.setdefault("current", None)
    ss.setdefault("shuffle_opts", True)
    ss.setdefault("no_repeat", True)

init_state()

# ===============================
# Sidebar controls (desktop)
# ===============================
with st.sidebar:
    st.header("🧰 设置（侧边栏）")
    uploaded = st.file_uploader("上传题库 CSV（可替换默认题库）", type=["csv"], key="uploader_sb")
    if uploaded is not None:
        st.session_state.df = pd.read_csv(uploaded)
        st.success("已加载上传的题库！")

    # callbacks keep effective filters in sync
    def on_change_qtype_sb():
        st.session_state.qtype_effective = st.session_state.qtype_sb

    def on_change_diff_sb():
        st.session_state.diff_effective = st.session_state.diff_sb

    def on_change_tag_sb():
        st.session_state.tag_query = st.session_state.tag_sb

    st.selectbox("题型", TYPE_OPTIONS, index=TYPE_OPTIONS.index(st.session_state.qtype_effective),
                 key="qtype_sb", on_change=on_change_qtype_sb)
    st.selectbox("难度", DIFF_OPTIONS, index=DIFF_OPTIONS.index(st.session_state.diff_effective),
                 key="diff_sb", on_change=on_change_diff_sb)
    st.text_input("标签筛选（包含关系）", value=st.session_state.tag_query, key="tag_sb", on_change=on_change_tag_sb)

    st.checkbox("打乱选项顺序", value=st.session_state.shuffle_opts, key="shuffle_opts")
    st.checkbox("抽题不重复（直到重置）", value=st.session_state.no_repeat, key="no_repeat")

    if st.button("🗑️ 重置抽题记录"):
        st.session_state.seen_ids = set()
        st.session_state.history = []
        st.session_state.current = None
        st.success("抽题记录已重置。")

    # Export
    if st.session_state.history:
        hist = pd.DataFrame(st.session_state.history,
                            columns=["time","id","type","question","user_answer","correct_answer","correct"])
        st.download_button("⬇️ 导出作答记录 CSV",
                           hist.to_csv(index=False).encode("utf-8-sig"),
                           file_name="history.csv", mime="text/csv")

# ===============================
# Main UI (mobile quick controls + quiz area)
# ===============================
st.title(APP_TITLE)
st.caption("提示：手机 / iPad 上如果看不到侧边栏，可以在下方使用“移动端快速选择”。")

# ---- Mobile quick controls (center of page) ----
st.markdown("### 📱 移动端快速选择")
col_a, col_b, col_c = st.columns([1,1,1])
with col_a:
    def on_change_qtype_main():
        st.session_state.qtype_effective = st.session_state.qtype_main
        st.session_state.qtype_sb = st.session_state.qtype_main  # keep sidebar synced
    st.selectbox("题型", TYPE_OPTIONS,
                 index=TYPE_OPTIONS.index(st.session_state.qtype_effective),
                 key="qtype_main", on_change=on_change_qtype_main)
with col_b:
    def on_change_diff_main():
        st.session_state.diff_effective = st.session_state.diff_main
        st.session_state.diff_sb = st.session_state.diff_main
    st.selectbox("难度", DIFF_OPTIONS,
                 index=DIFF_OPTIONS.index(st.session_state.diff_effective),
                 key="diff_main", on_change=on_change_diff_main)
with col_c:
    def on_change_tag_main():
        st.session_state.tag_query = st.session_state.tag_main
        st.session_state.tag_sb = st.session_state.tag_main
    st.text_input("标签", value=st.session_state.tag_query, key="tag_main", on_change=on_change_tag_main)

st.divider()

# Filtered pool based on effective filters
pool = filter_df(st.session_state.df,
                 st.session_state.qtype_effective,
                 st.session_state.diff_effective,
                 st.session_state.tag_query)

st.subheader("🎲 抽题区")
st.caption(f"当前筛选：类型 **{st.session_state.qtype_effective}** · 难度 **{st.session_state.diff_effective}** · 标签包含 **{st.session_state.tag_query or '（无）'}**")
st.caption(f"题目数量：{len(pool)}")

# Draw / show current
if st.button("🎲 抽 1 题", use_container_width=True):
    avoid = st.session_state.seen_ids if st.session_state.no_repeat else set()
    row = draw_one(pool, avoid)
    if row is None:
        st.warning("没有可抽的题目了。请重置抽题记录或更改筛选条件。")
    else:
        st.session_state.current = row
        st.session_state.seen_ids.add(row["id"])

current = st.session_state.current
if current:
    st.markdown(f"**编号**：`{current['id']}`　**类型**：`{current['type']}`　**难度**：`{current.get('difficulty','')}`")
    st.markdown(f"**题目**：{current['question']}")

    # Passage / image / audio
    if current.get("passage"):
        with st.expander("📖 阅读短文（点击展开）", expanded=True):
            st.write(current["passage"])
    show_image(current.get("image_url",""))
    play_audio(current.get("audio_url",""))

    # Answer UI
    options = parse_options(current.get("options",""))
    user_answer = None
    if options:
        if st.session_state.shuffle_opts:
            random.shuffle(options)
        user_answer = st.radio("请选择你的答案：", options, index=None)
    else:
        # open-ended
        placeholder = "在此输入……（主观题不自动判分）"
        user_answer = st.text_area("你的答案：", height=120, placeholder=placeholder)

    c1, c2, c3 = st.columns(3)
    if c1.button("✅ 提交答案", use_container_width=True):
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

    if c2.button("👀 显示参考答案", use_container_width=True):
        st.info(current.get("answer","（无参考答案）"))

    if c3.button("➡️ 下一题", use_container_width=True):
        avoid = st.session_state.seen_ids if st.session_state.no_repeat else set()
        row = draw_one(pool, avoid)
        if row is None:
            st.warning("没有可抽的题目了。请重置抽题记录或更改筛选条件。")
        else:
            st.session_state.current = row
            st.session_state.seen_ids.add(row["id"])

# Footer
st.markdown("---")
st.caption("移动端优化版本 · 题型支持：red/green/yellow/blue · 支持音频/图片/短文 · 题库 CSV 可通过侧边栏或上方控件筛选。")
