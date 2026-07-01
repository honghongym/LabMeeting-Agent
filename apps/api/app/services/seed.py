from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import EvaluationTemplate, Lab, Member, Project, ProjectMember


DEFAULT_DIMENSIONS = {
    "proposal": [
        {"dimension_name": "选题意义与文献综述完整性", "evaluation_guidance_text": "研究问题意义与文献脉络是否清晰。", "display_order": 1},
        {"dimension_name": "研究方案可行性", "evaluation_guidance_text": "方法、路线与风险预案是否可执行。", "display_order": 2},
        {"dimension_name": "前期准备工作量", "evaluation_guidance_text": "预实验、文献调研或理论推导是否充分。", "display_order": 3},
        {"dimension_name": "研究计划合理性", "evaluation_guidance_text": "时间节点和风险应对是否合理。", "display_order": 4},
        {"dimension_name": "答辩问答应对表现", "evaluation_guidance_text": "回答是否切中要害并体现理解深度。", "display_order": 5},
    ],
    "midterm": [
        {"dimension_name": "既定计划完成度", "evaluation_guidance_text": "阶段目标完成情况和滞后风险。", "display_order": 1},
        {"dimension_name": "阶段性成果产出", "evaluation_guidance_text": "是否有可验证成果。", "display_order": 2},
        {"dimension_name": "遇到问题的应对能力", "evaluation_guidance_text": "是否能合理调整与解决困难。", "display_order": 3},
        {"dimension_name": "后续计划调整合理性", "evaluation_guidance_text": "调整后计划是否支撑按期完成。", "display_order": 4},
        {"dimension_name": "与开题计划的偏差说明", "evaluation_guidance_text": "是否解释历史承诺偏差。", "display_order": 5},
    ],
    "final": [
        {"dimension_name": "研究成果完整性", "evaluation_guidance_text": "研究问题是否形成闭环回应。", "display_order": 1},
        {"dimension_name": "创新性与贡献度", "evaluation_guidance_text": "创新点与贡献是否清晰可靠。", "display_order": 2},
        {"dimension_name": "论文撰写与表达质量", "evaluation_guidance_text": "论文结构与答辩表达是否清晰。", "display_order": 3},
        {"dimension_name": "对历史质疑的回应", "evaluation_guidance_text": "是否回应开题/中期历史问题。", "display_order": 4},
        {"dimension_name": "答辩问答应对表现", "evaluation_guidance_text": "是否体现整体掌握。", "display_order": 5},
    ],
}


def seed_demo_data(db: Session) -> None:
    if db.get(Lab, "lab_demo"):
        return

    lab = Lab(lab_id="lab_demo", lab_name="智能软件工程课题组", institution="Demo University")
    project = Project(
        project_id="project_agent",
        lab_id="lab_demo",
        project_name="研究生组会智能纪要 Agent",
        description="用于演示 Agentic Workflow、长周期记忆和角色化报告的示例项目。",
    )
    members = [
        Member(user_id="user_advisor", lab_id="lab_demo", display_name="李老师", role="advisor"),
        Member(user_id="user_alice", lab_id="lab_demo", display_name="张同学", role="student"),
        Member(user_id="user_bob", lab_id="lab_demo", display_name="王同学", role="student"),
    ]
    db.add(lab)
    db.add(project)
    db.add_all(members)
    db.flush()
    db.add_all(
        [
            ProjectMember(project_id="project_agent", user_id="user_advisor"),
            ProjectMember(project_id="project_agent", user_id="user_alice"),
            ProjectMember(project_id="project_agent", user_id="user_bob"),
        ]
    )
    for subtype, dimensions in DEFAULT_DIMENSIONS.items():
        db.add(
            EvaluationTemplate(
                lab_id=None,
                defense_subtype=subtype,
                degree_type_applicable="both",
                dimensions=dimensions,
                is_active=True,
                version=1,
            )
        )
    db.commit()

