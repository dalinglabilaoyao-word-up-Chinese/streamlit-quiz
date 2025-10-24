
import random
import io
import time
import os
import pandas as pd
import streamlit as st

APP_TITLE = "🎯 随机抽题小游戏（按类型：red · green · yellow · blue）"
DEFAULT_CSV = "questions.csv"

st.set_page_config(page_title="随机抽题", page_icon="🎲", layout="wide")

# ---------- Helpers ----------
@st.cache_data
def load_questions(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    # normalize columns
    for col in ["options","audio_url","image_url","passage","difficulty","tags","type","id","question","answer"]:
        if col not in df.columns:
            df[col] = ""
    # ensure str
    for col in df.columns:
        df[col] = df[col].fillna("")
    # normalize type (strip spaces)
    df["type"] = df["type"].astype(str).str.strip()
    return df

def parse_options(opt_str: str):
    opts = [o.strip() for o in str(opt_str).split("||") if str(o).strip()]
    return opts

def filter_df(df, qtype, diff, tag_query):
    f = df.copy()
    if qtype != "all":
        f = f[f["type"].str.lower() == qtype.lower()]
    if diff != "all":
        f = f[f["difficulty"].str.lower() == diff]
    if tag_query:
        f = f[f["tags"].str.contains(tag_query, case=False, na=False)]
    return f.reset_index(drop=True)

def draw_one(df, avoid_ids):
    pool = df[~df["id"].isin(avoid_ids)]
    if len(pool) == 0:
        return None
    row = pool.sample(1).iloc[0].to_dict()
    return row

def init_state():
    if "history" not in st.session_state:
        st.session_state.history = []  # list of (timestamp, id, user_answer, correct)
    if "seen_ids" not in st.session_state:
        st.session_state.seen_ids = set()
    if "current" not in st.session_state:
        st.session_state.current = None
    if "df" not in st.session_state:
        st.session_state.df = load_questions(DEFAULT_CSV)

def export_history_csv():
    if not st.session_state.history:
        st.warning("暂无历史记录可导出。")
        return
    df = pd.DataFrame(st.session_state.history, columns=["time","id","type","question","user_answer","correct_answer","correct"])
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ 导出作答记录 CSV", csv, file_name="history.csv", mime="text/csv")

# Helpers to show local/remote media
def play_audio(src: str):
    if not src:
        return
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
    if not src:
        return
    src = str(src).strip()
    if src.startswith("http") or os.path.exists(src):
        st.image(src, use_column_width=True)
    else:
        st.warning(f"图片未找到：{src}")

# ---------- UI ----------
init_state()

st.title(APP_TITLE)

with st.sidebar:
    st.header("🧰 设置")
    uploaded = st.file_uploader("上传题库 CSV（可替换默认题库）", type=["csv"])
    if uploaded is not None:
        st.session_state.df = pd.read_csv(uploaded)
        st.success("已加载上传的题库！")

    # 固定的四种题型
    type_options = ["all","red","green","yellow","blue"]
    default_index = 0
    qtype = st.selectbox("题型", type_options, index=default_index)

    diff = st.selectbox("难度", ["all","easy","medium","hard"], index=0)
    tag_query = st.text_input("标签筛选（包含关系）", "")

    shuffle_opts = st.checkbox("打乱选项顺序", value=True)
    no_repeat = st.checkbox("抽题不重复（直到重置）", value=True)

    if st.button("🗑️ 重置抽题记录"):
        st.session_state.seen_ids = set()
        st.session_state.history = []
        st.session_state.current = None
        st.success("抽题记录已重置。")

    export_history_csv()

# Filtered pool
pool = filter_df(st.session_state.df, qtype, diff, tag_query)

colL, colR = st.columns([3,2])

with st.container():
    with colL:
        st.subheader("🎲 抽题区")
        st.caption(f"当前题库筛选后共有 {len(pool)} 题。")

        if st.button("🎲 抽 1 题", use_container_width=True):
            avoid = st.session_state.seen_ids if no_repeat else set()
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

            # passage / image / audio
            if current.get("passage"):
                with st.expander("📖 阅读短文（点击展开）", expanded=True):
                    st.write(current["passage"])

            show_image(current.get("image_url",""))
            play_audio(current.get("audio_url",""))

            # answer UI
            user_answer = None
            options = parse_options(current.get("options",""))
            if options:
                user_answer = st.radio("请选择你的答案：", options, index=None)
            elif current.get("type","").lower() == "blue":
                user_answer = st.text_area("请输入你的回答：", height=120, placeholder="在此输入……")
            else:
                user_answer = st.text_input("你的答案：", "")

            c1, c2, c3 = st.columns([1,1,1])
            if c1.button("✅ 提交答案"):
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
                        st.info("已记录你的回答。该题为主观题或非选择题，不进行自动判分。")
                    st.session_state.history.append([
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        current["id"],
                        current["type"],
                        current["question"],
                        str(user_answer),
                        correct_answer,
                        None if is_correct is None else bool(is_correct)
                    ])

            if c2.button("👀 显示参考答案"):
                st.info(current.get("answer","（无参考答案）"))

            if c3.button("➡️ 下一题"):
                avoid = st.session_state.seen_ids if no_repeat else set()
                row = draw_one(pool, avoid)
                if row is None:
                    st.warning("没有可抽的题目了。请重置抽题记录或更改筛选条件。")
                else:
                    st.session_state.current = row
                    st.session_state.seen_ids.add(row["id"])

    with colR:
        st.subheader("🧾 历史记录")
        if st.session_state.history:
            hist_df = pd.DataFrame(st.session_state.history, columns=["时间","编号","类型","题目","我的答案","参考答案","是否正确"])
            st.dataframe(hist_df, use_container_width=True, height=420)
        else:
            st.caption("暂无记录。点击左侧抽题并提交答案后会出现在这里。")

st.markdown("---")
st.caption("说明：本版固定题型为 red/green/yellow/blue；请在 CSV 的 type 列中使用这些名称来分类。支持音频/图片/短文。")
