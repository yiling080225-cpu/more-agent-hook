"""安全审计 Agent: 渗透测试、OWASP 扫描、合规检查、漏洞评估、代码加固"""

import json
import re
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

SECURITY_AGENT_CARD = AgentCard(
    name="security_audit_agent",
    description="安全审计专家，渗透测试、OWASP 扫描、合规检查、漏洞评估、代码加固",
    version="1.0.0",
    capabilities={
        "input": ["text", "code", "config", "url"],
        "output": ["vulnerability_report", "json"],
        "skills": [
            "penetration_testing",
            "owasp_scanning",
            "compliance_checking",
            "vulnerability_assessment",
            "code_hardening",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.security_agent_port}/a2a",
    model=settings.model_for("security"),
    max_context_tokens=200000,
)

SECURITY_SYSTEM_PROMPT = """你是一个世界级安全审计专家和渗透测试工程师。你拥有 15 年以上信息安全经验，持有 OSCP/CISSP/CSSLP 等认证。你的任务是以攻击者视角深度审查系统安全。

核心能力:
1. **渗透测试**: 模拟真实攻击链——侦察→扫描→利用→提权→持久化→横向移动
2. **OWASP 扫描**: 基于 OWASP Top 10 (2021) 和 OWASP ASVS 进行系统性安全评估
3. **合规检查**: SOC2/ISO 27001/GDPR/HIPAA/PCI-DSS 合规性对照检查
4. **漏洞评估**: CVSS v3.1 评分，PoC 可行性分析，攻击面分析
5. **代码加固**: 给出可落地的修复代码和安全加固方案

审计方法论:
- **攻击者视角**: 不只找"已知漏洞"，而是思考"如果是黑产会如何攻击"
- **纵深防御**: 检查每层防护——网络层/应用层/数据层/身份认证层
- **实际危害**: 每个漏洞都评估真实业务影响（数据泄露/资金损失/服务中断）
- **误报控制**: 排除已正确处理的场景，只报告真实风险
- **可操作修复**: 每条发现都附带具体的修复代码或配置变更

输出格式 (严格 JSON):
{
    "audit_summary": {
        "scope": "审计范围",
        "methodology": "审计方法论",
        "total_findings": N,
        "risk_distribution": {"critical": N, "high": N, "medium": N, "low": N, "info": N},
        "overall_risk_level": "critical / high / medium / low"
    },
    "findings": [
        {
            "id": "SEC-001",
            "title": "漏洞标题",
            "category": "OWASP 分类 (如 A01:2021-Broken Access Control)",
            "cwe_id": "CWE-xxx",
            "cvss_score": 0.0-10.0,
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "severity": "critical / high / medium / low / info",
            "description": "漏洞详细描述",
            "attack_scenario": "攻击者如何利用此漏洞的完整步骤",
            "affected_component": "受影响的组件/文件/行号",
            "prerequisites": "利用前提条件",
            "impact": {"confidentiality": "影响", "integrity": "影响", "availability": "影响"},
            "remediation": {
                "immediate": "紧急缓解措施",
                "permanent": "永久修复方案",
                "code_fix": "修复代码 (如果是代码问题)",
                "config_fix": "配置变更 (如果是配置问题)"
            },
            "references": ["CVE-xxxx-xxxx", "OWASP 链接"]
        }
    ],
    "compliance": {
        "frameworks": {"soc2": "status", "gdpr": "status", "iso27001": "status"},
        "gaps": ["不合规项1"],
        "recommendations": ["合规建议1"]
    },
    "security_hardening": {
        "server": ["加固项1"],
        "application": ["加固项2"],
        "network": ["加固项3"],
        "authentication": ["加固项4"]
    },
    "executive_summary": "面向管理层的一句话总结"
}

审计优先级: critical > high > medium > low > info
- critical: 无需认证即可远程代码执行/数据泄露，立即修复
- high: 需认证但易利用，或信息泄露严重，24h 内修复
- medium: 利用条件较苛刻，1 周内修复
- low: 最佳实践偏离，下个迭代修复
- info: 仅供参考的信息"""


class SecurityAgent(BaseAgent):
    """安全审计 Agent — 基于 Claude API (Opus)，深度安全分析"""

    def __init__(self):
        super().__init__(card=SECURITY_AGENT_CARD)
        from anthropic import AsyncAnthropic
        cfg = settings.client_for("security")
        self.client = AsyncAnthropic(**cfg)
        self.model = settings.model_for("security")

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("task_type", "security_audit")
        target = task.get("code") or task.get("text", "")

        dispatch = {
            "security_audit": self._security_audit,
            "vulnerability_scan": self._vulnerability_scan,
            "owasp_check": self._owasp_check,
            "compliance_review": self._compliance_review,
            "penetration_test": self._penetration_test,
        }
        handler = dispatch.get(task_type, self._security_audit)
        return await handler(target, task)

    async def _call(self, user_msg: str, max_tokens: int = 8192) -> tuple:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=SECURITY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _security_audit(self, target: str, task: Dict) -> Dict[str, Any]:
        """全面安全审计: 从代码到架构的完整安全评估。"""
        scope = task.get("scope", "full")
        tech_stack = task.get("tech_stack", "")
        stack_hint = f"\n\n技术栈: {tech_stack}" if tech_stack else ""
        target_block = self._format_code_block(target, task)
        user_msg = (
            f"对以下系统进行全面安全审计 (范围: {scope}):\n\n{target_block}{stack_hint}\n\n"
            f"请从攻击者视角审查，覆盖 OWASP Top 10，给出 CVSS 3.1 评分。"
            f"{self._format_files_hint(task)}"
        )
        try:
            content, tokens = await self._call(user_msg, max_tokens=8192)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("security_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _vulnerability_scan(self, target: str, task: Dict) -> Dict[str, Any]:
        """漏洞扫描: 针对特定组件或代码块做漏洞评估。"""
        scan_type = task.get("scan_type", "code")
        target_block = self._format_code_block(target, task)
        user_msg = (
            f"对以下{scan_type}进行漏洞扫描和评估:\n\n{target_block}\n\n"
            f"请识别所有安全漏洞，给出 CVSS 评分和修复建议。{self._format_files_hint(task)}"
        )
        try:
            content, tokens = await self._call(user_msg, max_tokens=8192)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("security_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _owasp_check(self, target: str, task: Dict) -> Dict[str, Any]:
        """OWASP Top 10 专项检查。"""
        target_block = self._format_code_block(target, task)
        user_msg = (
            f"根据 OWASP Top 10 (2021) 检查以下代码/系统:\n\n{target_block}\n\n"
            f"请逐项对照 OWASP Top 10 检查，每个类别标注通过/风险/不适用。{self._format_files_hint(task)}"
        )
        try:
            content, tokens = await self._call(user_msg, max_tokens=8192)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("security_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _compliance_review(self, target: str, task: Dict) -> Dict[str, Any]:
        """合规审查: 对照特定框架检查合规性。"""
        frameworks = task.get("frameworks", ["soc2", "gdpr", "iso27001"])
        fw_str = ", ".join(frameworks)
        target_desc = task.get("system_description", target)
        user_msg = (
            f"对以下系统进行合规审查 (框架: {fw_str}):\n\n{target_desc}\n\n"
            f"请逐框架评估合规状态，列出不合规项和改进建议。{self._format_files_hint(task)}"
        )
        try:
            content, tokens = await self._call(user_msg, max_tokens=4096)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("security_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _penetration_test(self, target: str, task: Dict) -> Dict[str, Any]:
        """渗透测试: 模拟攻击链。"""
        target_url = task.get("target_url", "")
        target_desc = target_url or task.get("system_description", target)
        user_msg = (
            f"对以下目标进行渗透测试规划和分析:\n\n目标: {target_desc}\n\n"
            f"请模拟完整攻击链 (侦察→扫描→利用→提权→持久化)，分析潜在攻击面。{self._format_files_hint(task)}"
        )
        try:
            content, tokens = await self._call(user_msg, max_tokens=8192)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("security_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    @staticmethod
    def _format_code_block(target: str, task: Dict) -> str:
        """格式化代码/目标为可审查的文本块。"""
        if isinstance(target, dict):
            return json.dumps(target, ensure_ascii=False, indent=2)
        if isinstance(target, list):
            parts = []
            for f in target:
                if isinstance(f, dict) and "path" in f:
                    parts.append(f"// {f['path']}\n{f.get('content', '')}")
                else:
                    parts.append(str(f))
            return "\n\n".join(parts)
        return str(target)[:50000]

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    pass
            return {
                "audit_summary": {
                    "overall_risk_level": "unknown",
                    "total_findings": 0,
                },
                "findings": [],
                "raw_output": text,
            }
