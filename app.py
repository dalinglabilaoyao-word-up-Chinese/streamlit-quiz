
import os
import time
import random
import pandas as pd
import streamlit as st

# =====================================
# Page setup
# =====================================
st.set_page_config(page_title="Chinese Words Board Game", page_icon="🀄", layout="centered")

APP_TITLE = "Chinese Words Board Game"
DEFAULT_ALL = "questions_all.csv"   # aggregated from /levels/*.csv
DEFAULT_CSV = "questions.csv"       # alias to ALL
LEVEL_DIR = "levels"
TYPE_OPTIONS = ["all", "red", "green", "yellow", "blue"]
DIFF_MIN, DIFF_MAX = 1, 10
DIFF_ALL = list(range(DIFF_MIN, DIFF_MAX + 1))

# =====================================
# Aggregation helpers
# =====================================
def list_level_files():
    return [os.path.join(LEVEL_DIR, f"questions_level_{i}.csv") for i in range(DIFF_MIN, DIFF_MAX+1)]

def rebuild_all_from_levels(write_to_all=True):
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
    # ensure columns
    for col in ["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"]:
        if col not in df.columns:
            df[col] = ""
    if write_to_all:
        try:
            df.to_csv(DEFAULT_ALL, index=False, encoding="utf-8-sig")
            # also refresh questions.csv as alias
            df.to_csv(DEFAULT_CSV, index=False, encoding="utf-8-sig")
        except Exception as e:
            st.warning(f"写入全量题库失败：{e}")
    return df

# =====================================
# Data helpers
# =====================================
@st.cache_data
def load_questions(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["id","type","question","answer","options","audio_url","image_url","passage","difficulty","tags"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    # normalize
    df["type"] = df["type"].astype(str).str.strip()
    # difficulty to int 1..10
    def _to_diff(x):
        try:
            v = int(str(x).strip())
        except Exception:
            v = 1
        return max(DIFF_MIN, min(DIFF_MAX, v))
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

# stable shuffled options per question id
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

# A small helper to normalize multiselect "all" logic
def normalize_diff_selection(selection, *, all_label="all"):
    """Rules:
    - empty -> select ALL
    - if 'all' selected together with numbers -> drop 'all' and keep numbers
    - if only 'all' -> select ALL
    Return list[int] in DIFF_MIN..DIFF_MAX and a canonical UI list[str] for the widget.
    """
    if not selection:
        ints = list(range(DIFF_MIN, DIFF_MAX+1))
        ui = [all_label]
        return ints, ui
    sel_set = set(selection)
    if all_label in sel_set and len(sel_set) > 1:
        sel_set.discard(all_label)  # prefer explicit numbers
    if sel_set == {all_label}:
        ints = list(range(DIFF_MIN, DIFF_MAX+1))
        ui = [all_label]
        return ints, ui
    # keep numbers only
    nums = []
    for s in sel_set:
        try:
            nums.append(int(s))
        except:
            pass
    nums = [n for n in nums if DIFF_MIN <= n <= DIFF_MAX]
    nums.sort()
    if not nums:
        ints = list(range(DIFF_MIN, DIFF_MAX+1))
        ui = [all_label]
    else:
        ints = nums
        ui = [str(n) for n in nums]
    return ints, ui

# =====================================
# State init
# =====================================
def init_state():
    ss = st.session_state
    # always rebuild ALL from levels at startup to keep in sync
    rebuild_all_from_levels(write_to_all=True)
    ss.setdefault("df", load_questions(DEFAULT_ALL))
    ss.setdefault("seen_ids", set())
    ss.setdefault("history", [])
    ss.setdefault("qtype_effective", "all")
    ss.setdefault("diff_selected", list(range(DIFF_MIN, DIFF_MAX+1)))
    ss.setdefault("diff_ui_sb", ["all"])
    ss.setdefault("diff_ui_main", ["all"])
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
    st.header("🧰 设置")
    # Upload level files (optional)
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
            st.session_state.df = rebuild_all_from_levels(write_to_all=True)
            st.cache_data.clear()
            st.success("已根据分级题库重建全量题库")

    # Type select
    def on_change_qtype_sb():
        st.session_state.qtype_effective = st.session_state.qtype_sb
    st.selectbox("题型", TYPE_OPTIONS, index=TYPE_OPTIONS.index(st.session_state.qtype_effective),
                 key="qtype_sb", on_change=on_change_qtype_sb)

    # Difficulty dropdown (multiselect with 'all'), fixed logic
    mult_opts = ["all"] + [str(i) for i in range(DIFF_MIN, DIFF_MAX+1)]
    def on_change_diff_multi_sb():
        ints, ui = normalize_diff_selection(st.session_state.diff_multi_sb, all_label="all")
        st.session_state.diff_selected = ints
        st.session_state.diff_ui_sb = ui
        st.session_state.diff_ui_main = ui
    st.multiselect("难度（下拉多选）", mult_opts, default=st.session_state.diff_ui_sb,
                   key="diff_multi_sb", on_change=on_change_diff_multi_sb, help="可选“all”，或勾选任意多个难度")

    # Tag filter
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

    # Desktop export
    if st.session_state.history:
        hist = pd.DataFrame(st.session_state.history,
                            columns=["time","id","type","question","user_answer","correct_answer","correct"])
        st.download_button("⬇️ 导出作答记录 CSV（桌面）",
                           hist.to_csv(index=False).encode("utf-8-sig"),
                           file_name="history.csv", mime="text/csv")

# =====================================
# Main UI (mobile quick controls)
# =====================================
st.title(APP_TITLE)
st.caption("说明：支持分级题库自动汇总；手机端也可导出作答记录。")

st.markdown("### 📱 移动端快速选择")
col1, col2 = st.columns(2)

with col1:
    def on_change_qtype_main():
        st.session_state.qtype_effective = st.session_state.qtype_main
        st.session_state.qtype_sb = st.session_state.qtype_main
    st.selectbox("题型", TYPE_OPTIONS, index=TYPE_OPTIONS.index(st.session_state.qtype_effective),
                 key="qtype_main", on_change=on_change_qtype_main)

with col2:
    mult_opts_m = ["all"] + [str(i) for i in range(DIFF_MIN, DIFF_MAX+1)]
    def on_change_diff_multi_main():
        ints, ui = normalize_diff_selection(st.session_state.diff_multi_main, all_label="all")
        st.session_state.diff_selected = ints
        st.session_state.diff_ui_main = ui
        st.session_state.diff_ui_sb = ui
    st.multiselect("难度（下拉多选）", mult_opts_m, default=st.session_state.diff_ui_main,
                   key="diff_multi_main", on_change=on_change_diff_multi_main)

# Current filters
pool = filter_df(st.session_state.df, st.session_state.qtype_effective, st.session_state.diff_selected, st.session_state.tag_query)
sel_text = "全部" if st.session_state.diff_selected == list(range(DIFF_MIN, DIFF_MAX+1)) else ",".join(map(str, st.session_state.diff_selected))

st.subheader("🎲 抽题区")
st.caption(f"筛选：类型 **{st.session_state.qtype_effective}** · 难度 **{sel_text}** · 标签包含 **{st.session_state.tag_query or '（无）'}**")
st.caption(f"题目数量：{len(pool)}")

# Mobile export button
if st.session_state.history:
    hist = pd.DataFrame(st.session_state.history,
                        columns=["time","id","type","question","user_answer","correct_answer","correct"])
    st.download_button("⬇️ 导出作答记录 CSV（手机端）",
                       hist.to_csv(index=False).encode("utf-8-sig"),
                       file_name="history.csv", mime="text/csv")

# Draw controls
def ensure_stable_options_for(row):
    opts_raw = parse_options(row.get("options",""))
    if opts_raw:
        key = row["id"]
        if key not in st.session_state.shuffled_options or not st.session_state.shuffled_options[key]:
            tmp = opts_raw[:]
            if st.session_state.shuffle_opts:
                random.shuffle(tmp)
            st.session_state.shuffled_options[key] = tmp

if st.button("🎲 抽 1 题", use_container_width=True):
    avoid = st.session_state.seen_ids if st.session_state.no_repeat else set()
    row = draw_one(pool, avoid)
    if row is None:
        st.warning("没有可抽的题目了。请重置抽题记录或更改筛选条件。")
    else:
        st.session_state.current = row
        st.session_state.seen_ids.add(row["id"])
        ensure_stable_options_for(row)

current = st.session_state.current
if current:
    st.markdown(f"**编号**：`{current['id']}`　**类型**：`{current['type']}`　**难度**：`{current.get('difficulty_num', current.get('difficulty',''))}`")
    st.markdown(f"**题目**：{current['question']}")

    if current.get("passage"):
        with st.expander("📖 阅读短文（点击展开）", expanded=True):
            st.write(current["passage"])
    show_image(current.get("image_url",""))
    play_audio(current.get("audio_url",""))

    # Options
    opts = st.session_state.shuffled_options.get(current["id"], parse_options(current.get("options","")))
    user_answer = None
    if opts:
        user_answer = st.radio("请选择你的答案：", opts, index=None, key=f"radio_{current['id']}")
    else:
        user_answer = st.text_area("你的答案：", height=120, placeholder="在此输入……（主观题不自动判分）", key=f"text_{current['id']}")

    c1, c2, c3 = st.columns(3)
    if c1.button("✅ 提交答案", use_container_width=True, key=f"submit_{current['id']}"):
        if user_answer is None or (isinstance(user_answer, str) and len(user_answer.strip())==0):
            st.warning("请先作答。")
        else:
            correct_answer = current.get("answer","").strip()
            is_select = bool(opts)
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
            ensure_stable_options_for(row)

st.markdown("---")
st.caption("题型 red/green/yellow/blue · 难度 1–10 下拉多选（修复“只能选全部”的问题） · 分级题库自动汇总。")
