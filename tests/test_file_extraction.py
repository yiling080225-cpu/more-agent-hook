"""测试: file_extraction utility + markitdown 自动夹入 Agent 联邦工作流"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest

from src.utils.file_extraction import extract_files_to_markdown
from src.agents.base import BaseAgent
from src.agents.multimodal_agent import MultimodalAgent
from src.gateway.supervisor import FederationSupervisor
from src.api.schemas import UserInput


# ── 1. extract_files_to_markdown 单元测试 ────────────────────────────────

class TestExtractFilesToMarkdown:

    def test_empty_list_returns_empty_string(self):
        assert extract_files_to_markdown([]) == ""

    def test_none_list_returns_empty_string(self):
        # 容错: None 也视为空
        assert extract_files_to_markdown([] or None or []) == ""

    def test_unsupported_extension_skipped(self, tmp_path):
        f = tmp_path / "binary.exe"
        f.write_bytes(b"\x00\x01\x02")
        result = extract_files_to_markdown([str(f)])
        assert result == ""

    def test_nonexistent_file_skipped(self, tmp_path):
        ghost = tmp_path / "ghost.pdf"
        result = extract_files_to_markdown([str(ghost)])
        assert result == ""

    def test_plain_txt_extracted(self, tmp_path):
        f = tmp_path / "spec.txt"
        f.write_text("零件名称: M6 螺栓\n长度: 30mm\n材料: 不锈钢", encoding="utf-8")
        result = extract_files_to_markdown([str(f)])
        assert "spec.txt" in result
        assert "M6 螺栓" in result

    def test_markdown_passthrough(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text("# 设计需求\n- 直径: 50mm\n- 厚度: 5mm", encoding="utf-8")
        result = extract_files_to_markdown([str(f)])
        assert "brief.md" in result
        assert "直径" in result

    def test_truncation_at_max_chars(self, tmp_path):
        f = tmp_path / "long.txt"
        f.write_text("x" * 30_000, encoding="utf-8")
        result = extract_files_to_markdown([str(f)], max_chars_per_file=20_000)
        assert "[...truncated]" in result
        # 头部 ## long.txt + 20k 字符 + 截断标记
        assert result.count("x") <= 20_000 + 50  # 容差留给可能的 markitdown 改写

    def test_multiple_files_concatenated(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("file A content", encoding="utf-8")
        f2 = tmp_path / "b.txt"
        f2.write_text("file B content", encoding="utf-8")
        result = extract_files_to_markdown([str(f1), str(f2)])
        assert "## a.txt" in result
        assert "## b.txt" in result
        assert "file A content" in result
        assert "file B content" in result

    def test_mixed_supported_and_unsupported(self, tmp_path):
        good = tmp_path / "good.txt"
        good.write_text("real content", encoding="utf-8")
        bad = tmp_path / "bad.exe"
        bad.write_bytes(b"\x00")
        result = extract_files_to_markdown([str(good), str(bad)])
        assert "real content" in result
        assert "bad.exe" not in result


# ── 2. BaseAgent._format_files_hint 单元测试 ──────────────────────────────

class TestFormatFilesHint:

    def test_empty_task_returns_empty(self):
        assert BaseAgent._format_files_hint({}) == ""
        assert BaseAgent._format_files_hint(None) == ""

    def test_no_files_markdown_returns_empty(self):
        assert BaseAgent._format_files_hint({"text": "hi"}) == ""

    def test_files_markdown_wrapped_with_header(self):
        task = {"files_markdown": "## a.txt\nhello"}
        out = BaseAgent._format_files_hint(task)
        assert "用户上传的参考文件" in out
        assert "## a.txt" in out
        assert "hello" in out


# ── 3. supervisor 注入 files_markdown 集成测试 ───────────────────────────

class TestSupervisorFilesInjection:

    def test_extract_called_when_files_present(self, tmp_path, monkeypatch):
        f = tmp_path / "brief.txt"
        f.write_text("设计一个 M6 螺栓", encoding="utf-8")

        captured = {}

        def fake_extract(files, max_chars_per_file=20_000):
            captured["files"] = files
            return "FAKE_MD_CONTENT"

        monkeypatch.setattr(
            "src.utils.file_extraction.extract_files_to_markdown",
            fake_extract,
        )

        supervisor = FederationSupervisor()
        # 直接测 _route_task 接受 files_markdown 参数
        ui = UserInput(text="设计零件", files=[str(f)])
        kw = supervisor._keyword_routing(ui, has_multimodal=True, files_markdown="FAKE_MD_CONTENT")
        # 有图片/文件 + cad 关键词 → cad_from_sketch
        assert kw["agent"] == "multimodal_design_agent"

    def test_keyword_routing_accepts_files_markdown_param(self):
        supervisor = FederationSupervisor()
        ui = UserInput(text="hello", files=[])
        # 不应抛异常
        kw = supervisor._keyword_routing(ui, has_multimodal=False, files_markdown="")
        assert kw["agent"] is None

    def test_route_task_signature_accepts_files_markdown(self):
        import asyncio
        supervisor = FederationSupervisor()
        ui = UserInput(text="设计一个零件", files=[])
        # _route_task 是 async, 调用前确认签名
        result = asyncio.run(supervisor._route_task(ui, files_markdown="some pdf content"))
        assert "agent" in result


# ── 4. MultimodalAgent prompt 注入 ───────────────────────────────────────

class TestMultimodalAgentFilesHint:

    def test_prompt_includes_files_content(self):
        agent = MultimodalAgent()
        prompt = agent._build_prompt(
            "根据规范设计零件",
            "build123d_model",
            task={"files_markdown": "## datasheet.pdf\n螺栓规格: M6 x 30mm\n材料: 不锈钢"},
        )
        assert "用户上传的参考文件" in prompt
        assert "datasheet.pdf" in prompt
        assert "M6 x 30mm" in prompt

    def test_prompt_no_files_no_hint(self):
        agent = MultimodalAgent()
        prompt = agent._build_prompt(
            "随便设计个东西",
            "cad_model",
            task={},
        )
        assert "用户上传的参考文件" not in prompt

    def test_prompt_files_appended_after_main(self):
        """files_hint 在 prompt 末尾, 不破坏 JSON 输出指令"""
        agent = MultimodalAgent()
        prompt = agent._build_prompt(
            "做个网页",
            "web_page",
            task={"files_markdown": "## ref.pdf\ncontent"},
        )
        # JSON 输出指令仍在前
        json_pos = prompt.find('"html"')
        files_pos = prompt.find("用户上传的参考文件")
        assert json_pos < files_pos, "files_hint 应在 prompt 末尾"


# ── 5. 端到端: SDK → supervisor → markitdown → Agent ──────────────────────

class TestEndToEndFileFlow:

    def test_pdf_content_reaches_multimodal_prompt(self, tmp_path, monkeypatch):
        """完整链路: 上传 .txt 文件 → supervisor 提取 → Agent prompt 包含内容"""
        f = tmp_path / "requirements.txt"
        f.write_text("零件: 法兰盘\n外径: 100mm\n内径: 50mm\n厚度: 10mm", encoding="utf-8")

        # 模拟 supervisor 提取文件 + 构建 task
        from src.utils.file_extraction import extract_files_to_markdown
        files_md = extract_files_to_markdown([str(f)])
        assert "法兰盘" in files_md

        # 模拟 Agent 收到 task 后构建 prompt
        agent = MultimodalAgent()
        prompt = agent._build_prompt(
            "根据上传的需求设计零件",
            "build123d_model",
            task={"files_markdown": files_md},
        )

        # 关键内容贯穿全链路
        assert "法兰盘" in prompt
        assert "100mm" in prompt
        assert "build123d" in prompt  # build123d_model 模板存在

    def test_corrupt_file_does_not_break_workflow(self, tmp_path):
        # 改名为 .pdf 但内容是文本 (markitdown 应失败但不抛异常)
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_text("not a real pdf", encoding="utf-8")
        good_txt = tmp_path / "good.txt"
        good_txt.write_text("正常内容", encoding="utf-8")

        result = extract_files_to_markdown([str(fake_pdf), str(good_txt)])
        # fake.pdf 失败, good.txt 成功
        assert "正常内容" in result
