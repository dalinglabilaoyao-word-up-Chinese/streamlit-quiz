import os
import time
import random
import pandas as pd
import streamlit as st

# 页面设置
st.set_page_config(page_title="Chinese Words Board Game", page_icon="🀄", layout="centered")

APP_TITLE = "Chinese Words Board Game"
DEFAULT_ALL = "questions_all.csv"
DEFAULT_CSV = "questions.csv"
LEVEL_DIR = "levels"
TYPE_OPTIONS = ["all", "red", "green", "yellow", "blue"]
DIFF_MIN, DIFF_MAX = 1, 10

# ========== 聚合分级题库 ==========
def list_level_files():
    return [os.path.join(LEVEL_DIR, f"questions_level_{i}.csv") for i in range(DIFF_MIN, DIFF_MAX + 1)]

def rebuild_all_from_levels():
    frames = []
    for p in list_level_files():
        if os.path.exists(p):
            try:
                frames.append(pd.read_csv(p))
            except Exception as e:
                st.warning(f"读取失败：{p} ({e})")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not df.empty:
        df.to_csv(DEFAULT_ALL, index=False, encoding="utf-8-sig")
        df.to_csv(DEFAULT_CSV, index=False, encoding="utf-8-sig")
    return df

# ========== 数据加载 ==========
@st.cache_data
def load_questions(path: str):
    if not os.path.exists(path):
        return pd.DataFrame(columns=["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"])
    df = pd.read_csv(path)
    if "difficulty" not in df.columns:
        df["difficulty"] = 1
    df["difficulty_num"] = df["difficulty"].apply(lambda x: int(x) if str(x).isdigit() else 1)
    return df

# ========== 初始化状态 ==========
def init_state():
    rebuild_all_from_levels()
    st.session_state.setdefault("df", load_questions(DEFAULT_ALL))
    st.session_state.setdefault("seen_ids", set())
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("current", None)
    st.session_state.setdefault("qtype_effective", "all")
    st.session_state.setdefault("diff_selected", list(range(DIFF_MIN, DIFF_MAX + 1)))

init_state()

# ========== 主体 ==========
st.title(APP_TITLE)

# 题型 & 难度选择
col1, col2 = st.columns(2)
with col1:
    st.session_state.qtype_effective = st.selectbox("题型", TYPE_OPTIONS, index=0)
with col2:
    selected_diff = st.multiselect("难度（1-10）", list(range(1, 11)), default=list(range(1, 11)))
    st.session_state.diff_selected = selected_diff if selected_diff else list(range(1, 11))

# 过滤题库
df = st.session_state.df
if not df.empty:
    filtered = df[(df["type"].isin([st.session_state.qtype_effective]) if st.session_state.qtype_effective != "all" else True) &
                  (df["difficulty_num"].isin(st.session_state.diff_selected))]
else:
    filtered = df

# 统计
total = len(filtered)
seen = len(st.session_state.seen_ids & set(filtered["id"]))
remain = max(0, total - seen)
st.caption(f"题目数量：{total}　已抽取：{seen}　剩余：{remain}")

# 抽题与重置
c1, c2 = st.columns([1, 1])
with c1:
    if st.button("🎲 抽 1 题", use_container_width=True):
        pool = filtered[~filtered["id"].isin(st.session_state.seen_ids)]
        if len(pool) == 0:
            st.warning("没有可抽的题目了！请重置。")
        else:
            q = pool.sample(1).iloc[0]
            st.session_state.current = q
            st.session_state.seen_ids.add(q["id"])
with c2:
    if st.button("♻️ 重置题目", use_container_width=True):
        st.session_state.seen_ids = set()
        st.session_state.current = None
        st.success("已重置题目！")

# 显示题目
if st.session_state.current is not None:
    q = st.session_state.current
    st.markdown(f"**题号**：{q['id']}　**类型**：{q['type']}　**难度**：{q['difficulty']}")
    st.markdown(f"**题目**：{q['question']}")
    options = str(q.get("options", "")).split("||")
    if len(options) > 1:
        ans = st.radio("请选择答案：", options, key=f"ans_{q['id']}")
    else:
        ans = st.text_input("请输入答案：", key=f"txt_{q['id']}")
    if st.button("✅ 提交答案", use_container_width=True):
        correct = q["answer"]
        st.session_state.history.append({
            "时间": time.strftime("%Y-%m-%d %H:%M:%S"),
            "题号": q["id"],
            "类型": q["type"],
            "题目": q["question"],
            "我的答案": ans,
            "正确答案": correct,
            "是否正确": ans.strip() == str(correct).strip()
        })
        st.success("已提交答案！")

# 实时作答结果表格
st.markdown("## 📊 实时作答结果")
hist_df = pd.DataFrame(st.session_state.history)
if not hist_df.empty:
    hist_df.insert(0, "编号", range(1, len(hist_df)+1))
else:
    hist_df = pd.DataFrame(columns=["编号","时间","题号","类型","题目","我的答案","正确答案","是否正确"])

colA, colB = st.columns([1, 1])
with colA:
    if st.button("🧹 清空记录"):
        st.session_state.history = []
        st.success("已清空！")
with colB:
    st.download_button("⬇️ 导出 CSV", hist_df.to_csv(index=False).encode("utf-8-sig"), "history.csv", "text/csv")

st.dataframe(hist_df, use_container_width=True, height=300)
