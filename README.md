
# streamlit_random_quiz_rgby

移动端友好的 Streamlit 抽题小游戏，题型固定为 **red/green/yellow/blue**，难度支持 **1–10** 多选与区间筛选。
内置示例题库 `questions.csv`（即 `questions_all_1_10.csv`），并附带分段题库：
- `questions_easy_1_3.csv`
- `questions_medium_4_7.csv`
- `questions_hard_8_10.csv`

## 运行
```bash
pip install streamlit pandas
streamlit run app.py
```

## 题库 CSV 字段
- 必填：`id, type, question, answer, difficulty`
- 可选：`options`（用 `||` 分隔）、`audio_url`、`image_url`、`passage`、`tags`
- 难度 `difficulty` 请使用 1–10 的整数。

## 提示
- 手机 / iPad 上可直接用页面中部的“移动端快速选择”筛选类型与难度。
- 侧边栏包含 CSV 上传、历史导出、不重复抽题、打乱选项等设置。
