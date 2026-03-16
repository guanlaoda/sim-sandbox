"""SimulationRunner — 端到端仿真运行器

协调 Persona 生成 → 场景加载 → 对话模拟 → 评测 的完整流程。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..adapters.base import BaseBotAdapter
from ..config import SandboxConfig
from ..evaluators.pipeline import EvaluationPipeline
from ..models.conversation import ConversationRecord
from ..models.evaluation import EvaluationReport
from ..models.persona import UserPersona
from ..models.scenario import Scenario
from ..persona.generator import PersonaGenerator
from ..scenario.loader import ScenarioLoader
from ..scenario.registry import ScenarioRegistry
from ..simulator.engine import DialogSimulator
from ..simulator.strategies import BaseStrategy, RuleBasedStrategy
from ..simulator.termination import TerminationChecker

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """单次仿真运行结果"""

    persona: UserPersona
    scenario: Scenario
    conversation: ConversationRecord
    evaluation: EvaluationReport


@dataclass
class BatchResult:
    """批量仿真结果"""

    results: List[RunResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


class SimulationRunner:
    """端到端仿真运行器"""

    def __init__(
        self,
        config: SandboxConfig,
        bot_adapter: BaseBotAdapter,
        strategy: BaseStrategy | None = None,
    ) -> None:
        self._config = config
        self._bot = bot_adapter
        self._strategy = strategy or RuleBasedStrategy()
        self._persona_gen = PersonaGenerator(config=config.persona, project_root=Path.cwd())
        self._scenario_loader = ScenarioLoader()
        self._registry = ScenarioRegistry()
        self._pipeline = EvaluationPipeline()

    async def run_single(
        self,
        persona: UserPersona,
        scenario: Scenario,
        session_id: str | None = None,
    ) -> RunResult:
        """执行一次 persona + scenario 的仿真"""
        # 构建 simulator
        termination = TerminationChecker(
            max_turns=scenario.constraints.max_turns,
            timeout_seconds=scenario.constraints.max_duration_seconds,
        )
        simulator = DialogSimulator(
            bot_adapter=self._bot,
            strategy=self._strategy,
            termination=termination,
        )

        # 执行对话
        conversation = await simulator.run(persona, scenario, session_id)

        # 评测
        evaluation = await self._pipeline.evaluate(conversation, scenario)

        logger.info(
            "Run completed: scenario=%s persona=%s turns=%d score=%.3f",
            scenario.scenario_id,
            persona.skeleton.persona_id,
            len(conversation.turns),
            evaluation.overall_score,
        )

        return RunResult(
            persona=persona,
            scenario=scenario,
            conversation=conversation,
            evaluation=evaluation,
        )

    async def run_batch(
        self,
        scenarios: List[Scenario],
        personas: List[UserPersona],
        concurrency: int = 5,
    ) -> BatchResult:
        """批量运行: 每个 scenario × persona 组合执行一次"""
        batch = BatchResult()
        semaphore = asyncio.Semaphore(concurrency)

        async def _run_one(persona: UserPersona, scenario: Scenario) -> RunResult:
            async with semaphore:
                return await self.run_single(persona, scenario)

        tasks = [
            _run_one(persona, scenario)
            for scenario in scenarios
            for persona in personas
        ]
        batch.total = len(tasks)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, RunResult):
                batch.results.append(r)
                if r.evaluation.overall_passed:
                    batch.passed += 1
                else:
                    batch.failed += 1
            else:
                batch.failed += 1
                logger.error("Run failed with exception: %s", r)

        logger.info(
            "Batch completed: total=%d passed=%d failed=%d rate=%.1f%%",
            batch.total,
            batch.passed,
            batch.failed,
            batch.pass_rate * 100,
        )
        return batch

    async def run_from_config(self) -> BatchResult:
        """根据配置文件自动运行"""
        # 加载场景
        scenario_dirs = self._config.simulation.scenario_dirs
        scenarios: list[Scenario] = []
        for d in scenario_dirs:
            loader = ScenarioLoader(scenarios_dir=d)
            loaded = loader.load_directory()
            scenarios.extend(loaded)

        if not scenarios:
            logger.warning("No scenarios found, nothing to run")
            return BatchResult()

        # 生成 persona
        count = self._config.persona.count
        personas = self._persona_gen.generate(count=count)

        return await self.run_batch(
            scenarios, personas, concurrency=self._config.simulation.concurrency
        )
