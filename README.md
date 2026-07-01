# LabMeeting-Agent

研究生组会智能纪要 Agent 是一个面向实验室组会场景的全栈 Agent Demo。项目支持从会议转录文本中抽取项目进展、问题风险、行动项和文献讨论，并在人工确认后沉淀为长期记忆，生成面向导师和学生的结构化会议报告。

项目默认使用 Mock LLM，方便在没有 API Key 的情况下完整演示流程。

## 功能特性

- 长文本会议转录解析与分段
- Agentic Map-Reduce 信息抽取流程
- Rolling State 工作记忆传递
- 草稿确认与长期记忆写入隔离
- 项目进展、学生任务、文献记录、Action Tracker 管理
- 导师视图与学生视图结构化报告
- Docker Compose 一键启动后端服务
- Chrome / Edge 浏览器插件入口

## 技术栈

- 前端插件：React, TypeScript, Vite, Chrome Manifest V3
- 后端 API：FastAPI, Pydantic, SQLAlchemy
- 异步任务：Celery, Redis
- 数据库：PostgreSQL
- 测试：pytest
- 部署：Docker Compose

## 快速启动

在项目根目录执行：

```bash
docker compose up --build
```

启动后可访问：

- API 服务：http://localhost:8000
- OpenAPI 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 插件构建与加载

进入插件目录并安装依赖：

```bash
cd apps/extension
npm install
npm run build
```

在 Chrome 或 Edge 中加载插件：

1. 打开浏览器扩展管理页面。
2. 启用开发者模式。
3. 选择“加载已解压的扩展程序”。
4. 选择 `apps/extension/dist` 目录。

也可以使用 Docker 构建插件产物：

```bash
docker compose --profile build-tools run --rm extension-build
```

## 基本使用流程

1. 启动后端服务。
2. 构建并加载浏览器插件。
3. 在插件中选择会议类型，粘贴会议转录文本。
4. 提交 Agent 任务并等待状态流转完成。
5. 查看结构化草稿内容。
6. 确认草稿后写入长期记忆。
7. 查看导师或学生视角的会议报告。

## 本地测试

```bash
cd apps/api
python -m pip install -e ".[dev]"
pytest
```

## 环境配置

后端默认读取 `apps/api/.env.example` 中的本地演示配置。正式使用时可以复制为 `.env` 后自行修改：

```bash
cp apps/api/.env.example apps/api/.env
```

注意：`.env`、本地数据库数据、依赖目录和构建产物不会提交到 Git。
