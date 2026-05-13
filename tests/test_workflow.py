"""测试: LangGraph 工作流 + Checkpoint"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSQLiteCheckpointer:
    """SQLite Checkpoint 测试"""

    def test_init_creates_db(self):
        from src.workflow.checkpoint import SQLiteCheckpointer
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            cp = SQLiteCheckpointer(db_path=db_path)
            assert os.path.exists(db_path)
            cp.close()

    def test_put_and_get(self):
        from src.workflow.checkpoint import SQLiteCheckpointer
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            cp = SQLiteCheckpointer(db_path=db_path)

            config = {"configurable": {"thread_id": "test-thread-1"}}
            checkpoint = {
                "id": "ckpt-001",
                "parent_checkpoint_id": None,
                "channel_values": {"status": "running", "data": "test"},
            }
            metadata = {"source": "test", "step": 1}

            cp.put(config, checkpoint, metadata, {})

            result = cp.get_tuple(config)
            assert result is not None
            assert result.checkpoint["id"] == "ckpt-001"
            assert result.checkpoint["channel_values"]["status"] == "running"

            cp.close()

    def test_get_latest_state(self):
        from src.workflow.checkpoint import SQLiteCheckpointer
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            cp = SQLiteCheckpointer(db_path=db_path)

            config = {"configurable": {"thread_id": "test-thread-2"}}
            cp.put(config, {"id": "ckpt-1", "channel_values": {"v": 1}}, {}, {})
            cp.put(config, {"id": "ckpt-2", "channel_values": {"v": 2}}, {}, {})

            state = cp.get_latest_state("test-thread-2")
            assert state is not None
            assert state["channel_values"]["v"] == 2  # 最新

            cp.close()

    def test_delete_thread(self):
        from src.workflow.checkpoint import SQLiteCheckpointer
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            cp = SQLiteCheckpointer(db_path=db_path)

            config = {"configurable": {"thread_id": "to-delete"}}
            cp.put(config, {"id": "ckpt-1", "channel_values": {}}, {}, {})
            cp.delete_thread("to-delete")
            assert cp.get_latest_state("to-delete") is None

            cp.close()

    def test_list_checkpoints(self):
        from src.workflow.checkpoint import SQLiteCheckpointer
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            cp = SQLiteCheckpointer(db_path=db_path)

            config = {"configurable": {"thread_id": "list-test"}}
            for i in range(3):
                cp.put(config, {"id": f"ckpt-{i}", "channel_values": {"i": i}}, {}, {})

            checkpoints = list(cp.list(config, limit=10))
            assert len(checkpoints) == 3

            cp.close()


class TestWorkflowBuilder:
    """工作流图构建测试"""

    def test_build_workflow(self):
        from src.workflow.ecommerce_workflow import build_workflow
        graph = build_workflow()
        assert graph is not None
        # 验证节点存在
        nodes = graph.get_graph().nodes
        node_names = {n for n in nodes}
        assert "parse_requirements" in node_names
        assert "multimodal_analysis" in node_names
        assert "human_review_ui" in node_names
        assert "generate_frontend" in node_names
        assert "generate_backend" in node_names
        assert "code_review" in node_names
        assert "deploy" in node_names

    def test_build_with_checkpointer(self):
        from src.workflow.ecommerce_workflow import build_workflow
        from src.workflow.checkpoint import SQLiteCheckpointer
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            cp = SQLiteCheckpointer(db_path=db_path)
            graph = build_workflow(checkpointer=cp)
            assert graph is not None
            cp.close()


class TestFeatureExtraction:
    """功能提取测试"""

    def test_extract_features_ecommerce(self):
        from src.workflow.ecommerce_workflow import _extract_features
        features = _extract_features("做一个电商网站，需要商品展示、购物车、支付功能")
        assert "product" in features
        assert "cart" in features
        assert "payment" in features

    def test_extract_features_empty(self):
        from src.workflow.ecommerce_workflow import _extract_features
        features = _extract_features("一个简单的网站")
        assert "web_app" in features


class TestLocalCodeReview:
    """本地代码审查测试"""

    def test_local_review_detects_eval(self):
        from src.workflow.ecommerce_workflow import _local_code_review
        result = _local_code_review({"main.py": "eval(user_input)"})
        issues = result.get("issues", [])
        assert any(i["severity"] == "critical" for i in issues)

    def test_local_review_clean_code(self):
        from src.workflow.ecommerce_workflow import _local_code_review
        result = _local_code_review({"main.py": "print('hello world')"})
        assert result["verdict"] == "approved"
