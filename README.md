
# 随机抽题（固定类型 red/green/yellow/blue）

## 运行
```bash
pip install streamlit pandas
streamlit run app.py
```

## 题库说明
- 在 `questions.csv` 的 `type` 列使用：`red` | `green` | `yellow` | `blue`
- 其它字段同原项目：`options` 用 `||` 分隔、`audio_url`/`image_url` 放直链或相对路径。

## 建议
- 你可以把课堂上的不同活动映射到这四个颜色：
  - red：听力或抢答类
  - green：阅读理解
  - yellow：图片理解/配对
  - blue：书写或开放式回答
