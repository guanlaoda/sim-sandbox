"""SQLite 持久化存储"""

from __future__ import annotations

import json
import sqlite3
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.conversation import ConversationRecord
from ..models.evaluation import EvaluationReport

logger = logging.getLogger(__name__)


class Database:
    """基于 SQLite 的对话记录和评测结果存储"""

    def __init__(self, db_path: str = "output/sandbox.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                record_id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                persona_id TEXT NOT NULL,
                turns_json TEXT NOT NULL,
                termination_reason TEXT,
                total_bot_latency_ms REAL,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS evaluations (
                eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                overall_score REAL,
                overall_passed INTEGER,
                results_json TEXT NOT NULL,
                dimension_weights_json TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (record_id) REFERENCES conversations(record_id)
            );

            CREATE INDEX IF NOT EXISTS idx_conv_scenario
                ON conversations(scenario_id);
            CREATE INDEX IF NOT EXISTS idx_eval_record
                ON evaluations(record_id);
        """)
        self._conn.commit()

    def save_conversation(self, record: ConversationRecord) -> None:
        assert self._conn is not None
        turns_json = json.dumps(
            [t.model_dump(mode="json") for t in record.turns],
            ensure_ascii=False,
        )
        self._conn.execute(
            """INSERT OR REPLACE INTO conversations
               (record_id, scenario_id, persona_id, turns_json,
                termination_reason, total_bot_latency_ms,
                started_at, finished_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.record_id,
                record.scenario_id,
                record.persona_id,
                turns_json,
                record.termination_reason,
                record.total_bot_latency_ms,
                record.started_at.isoformat() if record.started_at else None,
                record.finished_at.isoformat() if record.finished_at else None,
            ),
        )
        self._conn.commit()

    def save_evaluation(self, report: EvaluationReport) -> None:
        assert self._conn is not None
        results_json = json.dumps(
            [r.model_dump(mode="json") for r in report.results],
            ensure_ascii=False,
        )
        weights_json = json.dumps(report.dimension_weights, ensure_ascii=False)
        self._conn.execute(
            """INSERT INTO evaluations
               (record_id, scenario_id, overall_score, overall_passed,
                results_json, dimension_weights_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                report.record_id,
                report.scenario_id,
                report.overall_score,
                1 if report.overall_passed else 0,
                results_json,
                weights_json,
            ),
        )
        self._conn.commit()

    def get_conversation(self, record_id: str) -> Optional[Dict[str, Any]]:
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM conversations WHERE record_id = ?", (record_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["turns"] = json.loads(d["turns_json"])
            del d["turns_json"]
            return d
        return None

    def list_evaluations(
        self,
        scenario_id: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        assert self._conn is not None
        if scenario_id:
            rows = self._conn.execute(
                "SELECT * FROM evaluations WHERE scenario_id = ? ORDER BY created_at DESC LIMIT ?",
                (scenario_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["results"] = json.loads(d["results_json"])
            del d["results_json"]
            d["dimension_weights"] = json.loads(d.get("dimension_weights_json") or "{}")
            if "dimension_weights_json" in d:
                del d["dimension_weights_json"]
            results.append(d)
        return results

    def list_conversations(
        self,
        scenario_id: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """列出对话记录摘要（不含 turns 详情）"""
        assert self._conn is not None
        if scenario_id:
            rows = self._conn.execute(
                """SELECT record_id, scenario_id, persona_id,
                          termination_reason, total_bot_latency_ms,
                          started_at, finished_at, created_at
                   FROM conversations
                   WHERE scenario_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (scenario_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT record_id, scenario_id, persona_id,
                          termination_reason, total_bot_latency_ms,
                          started_at, finished_at, created_at
                   FROM conversations
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_summary_stats(self) -> Dict[str, Any]:
        """获取汇总统计"""
        assert self._conn is not None
        total = self._conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        evals = self._conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
        avg_score = self._conn.execute(
            "SELECT AVG(overall_score) FROM evaluations"
        ).fetchone()[0]
        pass_count = self._conn.execute(
            "SELECT COUNT(*) FROM evaluations WHERE overall_passed = 1"
        ).fetchone()[0]
        return {
            "total_conversations": total,
            "total_evaluations": evals,
            "avg_score": round(avg_score, 3) if avg_score else 0.0,
            "pass_rate": round(pass_count / evals, 3) if evals else 0.0,
        }
