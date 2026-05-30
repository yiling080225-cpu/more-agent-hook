"""知识/RAG Agent: 文档解析、上下文注入、RAG 问答、知识检索"""

import json
import re
import structlog
from typing import Any, Dict

from ..config import settings
from ..api.schemas import AgentCard
from .base import BaseAgent
from ..utils._content import extract_text

logger = structlog.get_logger()

KNOWLEDGE_AGENT_CARD = AgentCard(
    name="knowledge_rag_agent",
    description="知识检索专家，文档解析、上下文注入、RAG 问答、知识检索",
    version="1.0.0",
    capabilities={
        "input": ["text", "document", "query"],
        "output": ["text", "json", "context_chunks"],
        "skills": [
            "document_parsing",
            "context_retrieval",
            "rag_qa",
            "knowledge_query",
        ],
    },
    endpoint=f"http://{settings.host}:{settings.knowledge_agent_port}/a2a",
    model=settings.model_for("knowledge"),
    max_context_tokens=128000,
)

KNOWLEDGE_SYSTEM_PROMPT = """你是一个资深知识检索和 RAG 系统专家。你的任务是从文档和知识库中提取、组织和回答信息。

核心能力:
1. **文档解析**: 从上传的文档（Markdown/文本）中提取结构化信息和关键实体
2. **上下文检索**: 根据查询从文档中定位最相关的上下文片段
3. **RAG 问答**: 基于检索到的上下文，准确回答问题并标注引用来源
4. **知识查询**: 对知识库做探索性查询，发现关联、总结主题

工作原则:
- 精确引用: 每个回答都标注信息来源（文档名/章节/段落）
- 不编造: 如果文档中没有相关信息，明确说明"未找到"
- 结构化: 复杂信息用表格/列表整理，便于下游 Agent 使用
- 上下文完整性: 提供足够的上文保证语义完整

输出格式 (严格 JSON):
{
    "query": "原始查询",
    "answer": "基于文档的回答",
    "confidence": 0.0-1.0,
    "source_chunks": [
        {"document": "文档名", "section": "章节", "content": "相关原文片段", "relevance": 0.0-1.0}
    ],
    "entities": [{"name": "实体名", "type": "类型", "mentions": ["提及1"]}],
    "related_topics": ["相关主题1", "相关主题2"],
    "follow_up_questions": ["可追问的问题1"]
}"""


class KnowledgeAgent(BaseAgent):
    """知识/RAG Agent — 基于 Claude API，支持文档解析和上下文注入"""

    def __init__(self):
        super().__init__(card=KNOWLEDGE_AGENT_CARD)
        from anthropic import AsyncAnthropic
        cfg = settings.client_for("knowledge")
        self.client = AsyncAnthropic(**cfg)
        self.model = settings.model_for("knowledge")

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("task_type", "rag_qa")
        query = task.get("query") or task.get("text", "")

        dispatch = {
            "document_parse": self._document_parse,
            "context_retrieval": self._context_retrieval,
            "rag_qa": self._rag_qa,
            "knowledge_query": self._knowledge_query,
        }
        handler = dispatch.get(task_type, self._rag_qa)
        return await handler(query, task)

    async def _call(self, user_msg: str, max_tokens: int = 4096) -> tuple:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=KNOWLEDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        content = extract_text(resp.content)
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        return content, tokens

    async def _document_parse(self, query: str, task: Dict) -> Dict[str, Any]:
        """解析文档，提取结构化信息。优先使用 task 中已通过 markitdown 转换的 files_markdown。"""
        files_md = task.get("files_markdown", "")
        doc_text = task.get("document_text", query)
        if files_md:
            doc_text = f"{doc_text}\n\n## 附件内容 (Markdown)\n{files_md[:50000]}"
        user_msg = (
            f"解析以下文档内容，提取关键实体、主题和结构:\n\n"
            f"--- 文档开始 ---\n{doc_text[:30000]}\n--- 文档结束 ---\n\n"
            f"请提取: 1)标题 2)主要章节 3)关键实体(人名/地名/术语/数字) 4)核心观点 5)文档类型{self._format_files_hint(task)}"
        )
        try:
            content, tokens = await self._call(user_msg, max_tokens=4096)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("knowledge_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _context_retrieval(self, query: str, task: Dict) -> Dict[str, Any]:
        """从文档中检索与查询最相关的上下文片段。"""
        files_md = task.get("files_markdown", "")
        corpus = task.get("corpus", task.get("document_text", query))
        if files_md:
            corpus = f"{corpus}\n\n{files_md[:50000]}"
        user_msg = (
            f"从以下文档语料中检索与查询最相关的上下文片段:\n\n"
            f"查询: {query}\n\n"
            f"--- 语料开始 ---\n{corpus[:30000]}\n--- 语料结束 ---\n\n"
            f"请返回相关片段，每个片段标注相关性评分 (0-1)。{self._format_files_hint(task)}"
        )
        try:
            content, tokens = await self._call(user_msg, max_tokens=4096)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("knowledge_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _rag_qa(self, query: str, task: Dict) -> Dict[str, Any]:
        """RAG 问答: 基于提供的文档上下文回答问题。"""
        files_md = task.get("files_markdown", "")
        context_text = task.get("context_text", task.get("document_text", ""))
        if files_md:
            context_text = f"{context_text}\n\n{files_md[:50000]}"
        context_block = f"\n\n参考文档:\n---\n{context_text[:30000]}\n---" if context_text else ""
        user_msg = f"基于以下上下文回答问题:\n\n问题: {query}{context_block}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg, max_tokens=4096)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("knowledge_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

    async def _knowledge_query(self, query: str, task: Dict) -> Dict[str, Any]:
        """探索性知识查询: 对知识库做宽泛的主题探索。"""
        domain = task.get("domain", "")
        domain_hint = f"\n领域: {domain}" if domain else ""
        user_msg = f"对以下主题做知识探索性查询:\n\n{query}{domain_hint}{self._format_files_hint(task)}"
        try:
            content, tokens = await self._call(user_msg, max_tokens=4096)
            result = self._parse_json(content)
            result.update(model_used=self.model, tokens_used=tokens)
            return {"success": True, **result}
        except Exception as e:
            logger.error("knowledge_agent_error", error=str(e))
            return {"success": False, "error": str(e)}

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
            return {"raw_output": text, "answer": text, "confidence": 0.5, "source_chunks": []}
