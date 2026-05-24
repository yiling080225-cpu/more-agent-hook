import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_agent_card_data():
    return {
        "multimodal": {
            "name": "multimodal_design_agent",
            "description": "处理图像、文本的多模态理解与 UI 设计规范生成",
            "version": "1.0.0",
            "capabilities": {
                "input": ["text", "image", "audio"],
                "output": ["text", "json"],
                "skills": [
                    "ui_design_spec_generation",
                    "visual_element_extraction",
                    "handwritten_sketch_interpretation",
                    "color_palette_extraction",
                    "layout_analysis",
                ],
            },
            "endpoint": "http://127.0.0.1:8001/a2a",
        },
        "code": {
            "name": "secure_code_agent",
            "description": "复杂代码生成、类型安全的后端/前端开发",
            "version": "1.0.0",
            "capabilities": {
                "input": ["text", "code", "json"],
                "output": ["code", "json"],
                "skills": [
                    "fastapi_backend",
                    "nextjs_frontend",
                    "postgresql_schema",
                    "api_design",
                    "type_safe_code",
                    "security_best_practices",
                ],
            },
            "endpoint": "http://127.0.0.1:8002/a2a",
        },
        "review": {
            "name": "code_review_agent",
            "description": "对话式代码审查，多轮辩论，安全漏洞检测",
            "version": "1.0.0",
            "capabilities": {
                "input": ["text", "code", "diff"],
                "output": ["review_comment", "approval_status", "json"],
                "skills": [
                    "code_review",
                    "security_vulnerability_detection",
                    "performance_analysis",
                    "multi_round_debate",
                    "best_practice_enforcement",
                ],
            },
            "endpoint": "http://127.0.0.1:8003/a2a",
            "max_review_rounds": 3,
            "token_budget_per_review": 50000,
        },
    }


@pytest.fixture
def valid_a2a_request():
    from src.api.schemas import A2ATaskRequest
    return A2ATaskRequest(
        task_id="task-001",
        agent_name="secure_code_agent",
        task={"type": "backend", "spec": {"endpoints": ["GET /users"]}},
    )


@pytest.fixture
def valid_user_input():
    from src.api.schemas import UserInput
    return UserInput(
        text="创建一个电商网站",
        images=[],
        context={"style": "modern"},
    )
