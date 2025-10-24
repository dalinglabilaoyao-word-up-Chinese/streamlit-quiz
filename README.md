
# Chinese Words Board Game

- 标题已更名为 “Chinese Words Board Game”
- 难度 1–10 的**下拉多选**（可全选/单选/多选）
- 手机界面提供“导出作答记录”按钮
- 题库分为 1–10 十个等级文件，应用启动时会自动汇总到 `questions_all.csv` 并同步到 `questions.csv`。

## 运行
```bash
pip install streamlit pandas
streamlit run app.py
```

## 更新题库
- 修改 `levels/questions_level_1.csv` … `questions_level_10.csv` 任何内容，刷新页面后全量题库会自动更新；
- 或在侧边栏上传某个等级 CSV，点“重新构建全量题库”按钮。
