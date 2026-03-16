"""评测结果数据模型"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvalDetail(BaseModel):
    """评测明细"""

    check_name: str
    score: float = Field(ge=0, le=1)
    passed: bool = True
    evidence: str = ""
    suggestion: str = ""


class EvaluationResult(BaseModel):
    """单维度评测结果"""

    dimension: str
    score: float = Field(ge=0, le=1)
    details: List[EvalDetail] = Field(default_factory=list)
    passed: bool = True
    threshold: float = 0.0
    weight: float = 1.0


class EvaluationReport(BaseModel):
    """完整评测报告"""

    record_id: str
    scenario_id: str = ""
    results: List[EvaluationResult] = Field(default_factory=list)
    dimension_weights: Dict[str, float] = Field(default_factory=dict)
    overall_score: float = 0.0
    overall_passed: bool = True

    def compute_overall(self) -> None:
        """计算加权总分"""
        if not self.results:
            return
        total_weight = 0.0
        weighted_sum = 0.0
        for r in self.results:
            w = self.dimension_weights.get(r.dimension, 1.0)
            weighted_sum += r.score * w
            total_weight += w
        self.overall_score = round(weighted_sum / total_weight, 3) if total_weight else 0.0
        self.overall_passed = all(r.passed for r in self.results)
