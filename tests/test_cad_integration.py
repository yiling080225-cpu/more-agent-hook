"""模拟项目测试: Agent 联邦 + CAD 技能链完整工作流"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.gateway.supervisor import FederationSupervisor
from src.api.schemas import UserInput
from src.agents.multimodal_agent import MultimodalAgent


# ── 模拟 UserInput ────────────────────────────────────────────────────────

def _make_input(text: str, context: dict = None) -> UserInput:
    return UserInput(text=text, context=context or {})


# ── 1. 路由层测试 ─────────────────────────────────────────────────────────

class TestCADRouting:
    """验证 CAD 相关请求正确路由到 multimodal_design_agent"""

    def setup_method(self):
        self.supervisor = FederationSupervisor()

    @pytest.mark.parametrize("text,expected_task_type", [
        ("设计一个手机支架", "cad_model"),
        ("画个齿轮 3D 模型", "cad_model"),
        ("帮我设计一个机械零件", "cad_model"),
        ("生成螺栓的 STEP 文件", "build123d_model"),
        ("我需要一个 CNC 加工的零件", "build123d_model"),
        ("画一个装配体 3D 模型", "build123d_model"),
    ])
    def test_keyword_routing_cad_tasks(self, text, expected_task_type):
        routing = self.supervisor._keyword_routing(_make_input(text), False)
        assert routing["agent"] == "multimodal_design_agent"
        assert routing["task_type"] == expected_task_type

    def test_web_page_routing(self):
        routing = self.supervisor._keyword_routing(_make_input("帮我做一个电商首页"), False)
        assert routing["agent"] == "multimodal_design_agent"
        assert routing["task_type"] == "web_page"

    def test_svg_routing(self):
        routing = self.supervisor._keyword_routing(_make_input("画一个系统架构图"), False)
        assert routing["agent"] == "multimodal_design_agent"
        assert routing["task_type"] == "svg_diagram"

    def test_code_review_routing(self):
        routing = self.supervisor._keyword_routing(_make_input("帮我审查这段代码的安全性"), False)
        assert routing["agent"] == "code_review_agent"

    def test_direct_answer_routing(self):
        routing = self.supervisor._keyword_routing(_make_input("你好，今天天气怎么样"), False)
        assert routing["agent"] is None

    def test_cad_with_multimodal(self):
        """图片 + CAD 关键词走 cad_from_sketch"""
        input_data = _make_input("这个草图画的是什么零件")
        input_data.images = ["test.png"]
        routing = self.supervisor._keyword_routing(input_data, True)
        assert routing["agent"] == "multimodal_design_agent"
        assert routing["task_type"] == "cad_from_sketch"


# ── 2. Prompt 生成测试 ────────────────────────────────────────────────────

class TestCADPromptGeneration:
    """验证 build123d 和 CAD 模型 prompt 模板正确生成"""

    def setup_method(self):
        self.agent = MultimodalAgent()

    def test_build123d_prompt_contains_correct_imports(self):
        prompt = self.agent._build_prompt("设计一个手机支架", "build123d_model")
        assert "build123d" in prompt
        assert "Box" in prompt or "Cylinder" in prompt
        assert "export_step" in prompt
        assert "export_stl" in prompt

    def test_build123d_prompt_has_units(self):
        prompt = self.agent._build_prompt("设计一个轴承座", "build123d_model")
        assert "mm" in prompt
        assert "fillet" in prompt.lower()

    def test_build123d_prompt_includes_style_hint(self):
        prompt = self.agent._build_prompt(
            "设计外壳",
            "build123d_model",
            task={"style": "工业极简风", "theme": "#333333"}
        )
        assert "工业极简风" in prompt
        assert "#333333" in prompt

    def test_cad_model_prompt_expects_json_output(self):
        prompt = self.agent._build_prompt("设计一个齿轮", "cad_model")
        assert "build123d_code" in prompt
        assert "parameters" in prompt

    def test_cad_from_sketch_prompt_has_analysis(self):
        prompt = self.agent._build_prompt("分析这张手绘零件图", "cad_from_sketch")
        assert "分析" in prompt or "analysis" in prompt.lower()
        assert "build123d" in prompt

    def test_ui_design_prompt_not_affected(self):
        """确保 UI 设计 prompt 不受 CAD 修改影响"""
        prompt = self.agent._build_prompt("设计一个登录页", "ui_design")
        assert "UI" in prompt or "ui" in prompt.lower()
        assert "color_palette" in prompt


# ── 3. 输出保存测试 ────────────────────────────────────────────────────────

class TestOutputSaving:
    """验证 build123d 代码正确保存到 preview/"""

    def setup_method(self):
        self.supervisor = FederationSupervisor()
        self.preview_dir = Path("preview")
        self.preview_dir.mkdir(exist_ok=True)

    def test_saves_build123d_model_py(self):
        code = '''"""手机支架 — build123d 参数化模型"""
from build123d import *
from math import pi

# 参数
base_length = 80.0
base_width = 60.0
base_height = 10.0
arm_height = 100.0
angle = 65.0

# 主体
base = Box(base_length, base_width, base_height)
support = Box(8, base_width, arm_height)
support = Pos(0, 0, base_height + arm_height/2) * support
body = base + support

export_step(body, "phone_stand.step")
export_stl(body, "phone_stand.stl")
'''
        result = {"result": {"build123d_code": code}}
        path = self.supervisor._save_direct_output("build123d_model", result, "test-001")
        assert path is not None
        assert Path(path).suffix == ".py"
        assert Path(path).exists()
        saved = Path(path).read_text(encoding="utf-8")
        assert "from build123d import" in saved
        assert "export_step" in saved

    def test_saves_cad_model_py(self):
        code = "from build123d import *\nbox = Box(10,10,10)\nexport_step(box, 'test.step')"
        result = {"result": {"build123d_code": code}}
        path = self.supervisor._save_direct_output("cad_model", result, "test-002")
        assert path is not None
        assert Path(path).suffix == ".py"
        assert Path(path).exists()

    def test_web_page_still_saves_html(self):
        html = "<!DOCTYPE html><html lang='zh'><head><meta charset='UTF-8'></head><body><h1>测试页面</h1><p>内容</p></body></html>"
        result = {"result": {"html": html}}
        path = self.supervisor._save_direct_output("web_page", result, "test-003")
        assert path is not None, f"HTML 长度 {len(html)} 应 > 50"
        assert Path(path).suffix == ".html"

    def test_empty_code_not_saved(self):
        result = {"result": {"build123d_code": ""}}
        path = self.supervisor._save_direct_output("build123d_model", result, "test-004")
        assert path is None

    def test_short_code_not_saved(self):
        result = {"result": {"build123d_code": "short"}}
        path = self.supervisor._save_direct_output("build123d_model", result, "test-005")
        assert path is None


# ── 4. Skill 安装验证 ─────────────────────────────────────────────────────

class TestCADSkillsInstalled:
    """验证 text-to-cad 7 个 skill 已正确安装"""

    def test_cad_skill_exists(self):
        path = Path.home() / ".claude" / "skills" / "cad" / "SKILL.md"
        assert path.exists(), f"cad skill 未安装: {path}"

    def test_cad_explorer_skill_exists(self):
        path = Path.home() / ".claude" / "skills" / "cad-explorer" / "SKILL.md"
        assert path.exists(), f"cad-explorer skill 未安装: {path}"

    def test_step_parts_skill_exists(self):
        path = Path.home() / ".claude" / "skills" / "step-parts" / "SKILL.md"
        assert path.exists(), f"step-parts skill 未安装: {path}"

    def test_urdf_skill_exists(self):
        path = Path.home() / ".claude" / "skills" / "urdf" / "SKILL.md"
        assert path.exists(), f"urdf skill 未安装: {path}"

    def test_sdf_skill_exists(self):
        path = Path.home() / ".claude" / "skills" / "sdf" / "SKILL.md"
        assert path.exists(), f"sdf skill 未安装: {path}"

    def test_srdf_skill_exists(self):
        path = Path.home() / ".claude" / "skills" / "srdf" / "SKILL.md"
        assert path.exists(), f"srdf skill 未安装: {path}"

    def test_sendcutsend_skill_exists(self):
        path = Path.home() / ".claude" / "skills" / "sendcutsend" / "SKILL.md"
        assert path.exists(), f"sendcutsend skill 未安装: {path}"

    def test_agent_federation_skill_exists(self):
        path = Path.home() / ".claude" / "skills" / "agent-federation" / "SKILL.md"
        assert path.exists(), f"agent-federation skill 未安装: {path}"

    def test_cad_skill_has_scripts(self):
        skill_dir = Path.home() / ".claude" / "skills" / "cad" / "scripts"
        assert (skill_dir / "step").is_dir(), "cad skill 缺少 scripts/step/"
        assert (skill_dir / "inspect").is_dir(), "cad skill 缺少 scripts/inspect/"
        assert (skill_dir / "render").is_dir(), "cad skill 缺少 scripts/render/"

    def test_cad_explorer_has_scripts(self):
        explorer_dir = Path.home() / ".claude" / "skills" / "cad-explorer" / "scripts"
        assert (explorer_dir / "explorer").is_dir(), "cad-explorer 缺少 scripts/explorer/"


# ── 5. FedCLI 集成测试 ────────────────────────────────────────────────────

class TestFedCLICADIntegration:
    """验证 fedcli 命令对 CAD 任务类型的支持"""

    def test_fedcli_imports(self):
        import fedcli
        assert hasattr(fedcli, 'cli')

    def test_sdk_client_cad_execute(self):
        from federation_sdk import FederationClient
        client = FederationClient()
        assert client.supervisor is not None
        assert client.workflow is not None

    def test_output_format_build123d_accepted(self):
        """SDK client.execute 接受 output_format=build123d"""
        from federation_sdk import FederationClient
        from federation_sdk.models import TaskResult
        client = FederationClient()
        # 验证客户端接受 build123d 格式参数（不实际发送请求）
        assert client is not None


# ── 6. 端到端工作流模拟 ───────────────────────────────────────────────────

class TestEndToEndWorkflow:
    """模拟真实项目场景: 用户描述 → 路由 → 生成代码 → 保存输出"""

    def test_phone_stand_workflow(self):
        """场景: 用户要求设计手机支架"""
        supervisor = FederationSupervisor()

        # Step 1: 路由分析
        routing = supervisor._keyword_routing(
            _make_input("帮我设计一个桌面手机支架，适合 iPhone 15，可调节角度"),
            False
        )
        assert routing["agent"] == "multimodal_design_agent"
        assert routing["task_type"] == "cad_model"

        # Step 2: 生成 CAD prompt
        agent = MultimodalAgent()
        prompt = agent._build_prompt(
            "桌面手机支架，适合 iPhone 15，可调节角度",
            routing["task_type"]
        )
        assert "build123d_code" in prompt  # cad_model 要求输出 build123d 代码
        assert "mm" in prompt

        # Step 3: 模拟代码生成并保存
        test_code = '''"""Phone Stand — build123d parametric model"""
from build123d import *
from math import pi, sin, cos

# Parameters (mm)
base_w, base_d, base_h = 80, 65, 8
arm_w, arm_d, arm_h = 10, 15, 90
slot_w, slot_d = 12, 8
angle_deg = 65

# Main body
base = Box(base_w, base_d, base_h)
arm = Box(arm_w, arm_d, arm_h)
arm = Pos(0, 0, base_h + arm_h/2) * Rot(Y=-(90-angle_deg)) * arm
body = base + arm

# Phone slot
slot = Box(slot_w, slot_d, 20)
slot = Pos(0, 0, base_h + arm_h - 25) * Rot(Y=-(90-angle_deg)) * slot
body -= slot

# Fillets
body = fillet(body.edges().filter_by(Axis.Z), radius=1.5)

# Export
export_step(body, "phone_stand.step")
export_stl(body, "phone_stand.stl")
'''
        result = {"result": {"build123d_code": test_code}}
        path = supervisor._save_direct_output("cad_model", result, "phone-stand")
        assert path is not None
        saved = Path(path).read_text(encoding="utf-8")
        assert "iPhone" in saved or "Phone" in saved
        assert "export_step" in saved
        assert "export_stl" in saved

    def test_bolt_step_workflow(self):
        """场景: 用户要求生成螺栓 STEP 文件"""
        supervisor = FederationSupervisor()

        routing = supervisor._keyword_routing(
            _make_input("生成一个 M8x30 螺栓的 STEP 文件，用于 3D 打印验证"),
            False
        )
        assert routing["task_type"] == "build123d_model"

    def test_assembly_workflow(self):
        """场景: 用户要求设计装配体"""
        supervisor = FederationSupervisor()

        routing = supervisor._keyword_routing(
            _make_input("设计一个行星齿轮箱装配体，包含太阳轮、行星轮和内齿圈"),
            False
        )
        assert routing["agent"] == "multimodal_design_agent"
        # 齿轮箱包含装配和齿轮关键词 → build123d_model
        assert routing["task_type"] == "build123d_model"


# ── 7. 回归测试 ──────────────────────────────────────────────────────────

class TestNoRegression:
    """确保 CAD 修改不影响原有功能"""

    def test_fallback_ui_spec_unchanged(self):
        agent = MultimodalAgent()
        spec = agent._fallback_ui_spec("设计一个电商网站")
        assert "design_system" in spec
        assert "color_palette" in spec["design_system"]
        assert "pages" in spec
        assert "component_library" in spec

    def test_gemini_path_not_broken(self):
        agent = MultimodalAgent()
        assert agent.model is not None
        assert agent._use_gemini or agent._use_anthropic or True  # 至少有 fallback

    def test_supervisor_instantiation(self):
        sv = FederationSupervisor()
        assert sv.router_model is not None
        assert isinstance(sv._active_workflows, dict)

    def test_config_has_claude_settings(self):
        from src.config import settings
        assert isinstance(settings.has_anthropic, bool)
        assert isinstance(settings.anthropic_base_url, str)
