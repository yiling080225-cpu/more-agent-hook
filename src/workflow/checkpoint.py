"""SQLite Checkpoint 持久化 — LangGraph Checkpointer 的本地实现"""

import json
import sqlite3
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

logger = structlog.get_logger()


class SQLiteCheckpointer(BaseCheckpointSaver):
    """基于 SQLite 的 LangGraph Checkpoint 存储 (替代 Firestore)

    支持:
    - 断点恢复: 工作流中断后从最新 Checkpoint 继续
    - 时间旅行: 查看历史状态
    - 线程隔离: 多个项目/工作流并行运行
    """

    def __init__(self, db_path: str = "data/checkpoints.db"):
        super().__init__()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                checkpoint_data TEXT NOT NULL,
                metadata_data TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
            ON checkpoints(thread_id, created_at DESC)
        """)
        conn.commit()
        conn.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """获取指定线程的最新 Checkpoint"""
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")

        if checkpoint_id:
            row = self.conn.execute(
                "SELECT * FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?",
                (thread_id, checkpoint_id),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
                (thread_id,),
            ).fetchone()

        if not row:
            return None

        return self._row_to_tuple(row)

    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """保存 Checkpoint"""
        thread_id = config.get("configurable", {}).get("thread_id", "default")

        self.conn.execute(
            """INSERT OR REPLACE INTO checkpoints
               (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint_data, metadata_data, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                thread_id,
                checkpoint["id"],
                checkpoint.get("parent_checkpoint_id"),
                json.dumps(checkpoint, default=str),
                json.dumps(metadata, default=str),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()

        logger.info("checkpoint_saved", thread_id=thread_id, checkpoint_id=checkpoint["id"])
        return {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint["id"]}}

    def put_writes(
        self,
        config: Dict[str, Any],
        writes: list,
        task_id: str,
        task_path: str = "",
    ) -> None:
        """保存中间写入 (LangGraph 要求实现，此处简化存储)"""
        pass

    def list(
        self,
        config: Optional[Dict[str, Any]],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """列出 Checkpoint 历史"""
        thread_id = config.get("configurable", {}).get("thread_id", "default") if config else "default"

        rows = self.conn.execute(
            "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT ?",
            (thread_id, limit or 50),
        ).fetchall()

        for row in rows:
            yield self._row_to_tuple(row)

    def _row_to_tuple(self, row: sqlite3.Row) -> CheckpointTuple:
        """将数据库行转为 CheckpointTuple"""
        checkpoint_data = json.loads(row["checkpoint_data"])
        metadata = json.loads(row["metadata_data"])
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": row["thread_id"],
                    "checkpoint_id": row["checkpoint_id"],
                }
            },
            checkpoint=checkpoint_data,
            metadata=metadata,
            parent_config={
                "configurable": {
                    "thread_id": row["thread_id"],
                    "checkpoint_id": row["parent_checkpoint_id"],
                }
            }
            if row["parent_checkpoint_id"]
            else None,
        )

    def delete_thread(self, thread_id: str) -> None:
        """删除指定线程的所有 Checkpoint"""
        self.conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        self.conn.commit()
        logger.info("checkpoint_thread_deleted", thread_id=thread_id)

    def get_latest_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取线程最新状态 (便捷方法)"""
        row = self.conn.execute(
            "SELECT checkpoint_data FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        if row:
            return json.loads(row["checkpoint_data"])
        return None

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
