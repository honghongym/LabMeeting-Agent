# 简历项目描述

## 中文版

研究生组会智能纪要 Agentic Workflow 系统  
基于 FastAPI、Celery、PostgreSQL、React Extension 实现多租户组会纪要 Agent。负责从 0 到 1 设计并实现长文本语义分段、Map-Reduce 并发抽取、Rolling State 工作记忆、Token 预算控制、人工确认状态机、长期结构化记忆库与角色化报告渲染；支持 Mock/通义千问模型适配，Docker Compose 一键复现。

可展开亮点：

- 设计 `Lab -> Project -> Member` 多租户隔离模型，避免跨课题组数据污染。
- 将会议处理拆成 `queued -> segmenting -> extracting -> reducing -> awaiting_confirmation -> confirmed` 状态机，前端轮询展示进度。
- 实现 `draft_result/confirmed_result` 分离，长期记忆只消费人工确认数据。
- 使用结构化 ActionTracker 支持跨会议承诺追踪，形成长周期记忆闭环。
- 对答辩评估加入枚举校验与报告措辞防护，避免模型输出二元裁定。

## English Version

Graduate Meeting Minutes Agentic Workflow System  
Built a full-stack multi-tenant meeting-minutes Agent with FastAPI, Celery, PostgreSQL, and a React browser extension. Implemented semantic transcript chunking, concurrent Map-Reduce extraction, Rolling State memory propagation, token budget control, human-in-the-loop confirmation, long-term structured memory, and role-based report rendering. The project supports a mock LLM for reproducible demos and a Tongyi/Qwen provider adapter for real model integration.

