# Demo Script

## 1. 启动

```bash
docker compose up --build
```

打开 http://localhost:8000/docs，确认 API 已启动。

## 2. 插件

```bash
cd apps/extension
npm install
npm run dev
```

使用内置示例转录提交任务。

## 3. 观察点

- 进度条从分段、抽取、聚合推进到待确认。
- 草稿 JSON 中按会议类型出现不同结构。
- 点击确认后，报告视图可在导师/学生之间切换。
- 再提交一次项目汇报，可看到历史 ActionTracker 被检索并参与对比。

