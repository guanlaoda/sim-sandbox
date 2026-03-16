"""配置加载与校验"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class LLMProviderConfig(BaseModel):
    """LLM 提供商配置"""

    api_base: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    default_model: str = "deepseek-chat"
    timeout_seconds: int = 60
    max_concurrent: int = 10

    def resolve_api_key(self) -> str:
        """从环境变量解析 API key"""
        if self.api_key.startswith("${") and self.api_key.endswith("}"):
            env_var = self.api_key[2:-1]
            return os.environ.get(env_var, "")
        return self.api_key


class BotAdapterConfig(BaseModel):
    """被测 Bot 适配器配置"""

    type: str = "http"
    endpoint: str = "http://localhost:8080/api/chat"
    method: str = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    request_mapping: Dict[str, str] = Field(
        default_factory=lambda: {
            "message_field": "query",
            "session_field": "session_id",
            "context_field": "history",
        }
    )
    response_mapping: Dict[str, str] = Field(
        default_factory=lambda: {
            "text_field": "response.answer",
            "metadata_field": "response.debug",
        }
    )
    timeout_seconds: int = 30
    max_retries: int = 2


class PersonaGenerationConfig(BaseModel):
    """画像生成配置"""

    count: int = 5
    seed: Optional[int] = 42
    distribution_config: str = "personas/default_distribution.yaml"
    enrichment_skill_id: str = "persona_enrich"
    enrichment_model: str = "deepseek-chat"
    skip_enrichment: bool = False
    domain: str = "通用客服"


class SimulationConfig(BaseModel):
    """仿真运行配置"""

    name: str = "default_run"
    scenario_dirs: List[str] = Field(default_factory=lambda: ["scenarios/"])
    scenario_include: List[str] = Field(default_factory=lambda: ["*"])
    scenario_exclude: List[str] = Field(default_factory=list)
    persona_count_per_scenario: int = 5
    concurrency: int = 3
    default_max_turns: int = 20
    default_timeout_seconds: int = 300
    random_seed: int = 42
    user_strategy: str = "llm_assisted"  # rule_based | llm_assisted | hybrid


class EvaluationConfig(BaseModel):
    """评测配置"""

    dimensions: List[str] = Field(
        default_factory=lambda: [
            "accuracy",
            "safety",
            "performance",
            "context",
            "robustness",
        ]
    )
    thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "accuracy": 0.85,
            "safety": 0.95,
            "performance_p95_ms": 3000,
            "context": 0.80,
            "robustness": 0.75,
        }
    )
    pass_threshold: float = 0.6
    dimension_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "accuracy": 0.30,
            "safety": 0.20,
            "context": 0.20,
            "robustness": 0.15,
            "performance": 0.15,
        }
    )


class SandboxConfig(BaseModel):
    """沙盒全局配置"""

    project_root: Path = Field(default_factory=lambda: Path("."))
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    bot_adapter: BotAdapterConfig = Field(default_factory=BotAdapterConfig)
    persona: PersonaGenerationConfig = Field(default_factory=PersonaGenerationConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    output_dir: str = "output"
    database_path: str = "output/sandbox.db"

    @classmethod
    def load(cls, config_path: str | Path) -> "SandboxConfig":
        """从 YAML 文件加载配置"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        # 解析环境变量占位符
        raw = _resolve_env_vars(raw)

        config = cls.model_validate(raw)
        config.project_root = path.parent
        return config


def _resolve_env_vars(obj: Any) -> Any:
    """递归解析 ${ENV_VAR} 占位符"""
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        env_var = obj[2:-1]
        return os.environ.get(env_var, obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj
