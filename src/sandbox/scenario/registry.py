"""场景注册与检索"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..models.scenario import Difficulty, Scenario


class ScenarioRegistry:
    """场景注册表 — 集中管理所有已加载的场景"""

    def __init__(self) -> None:
        self._scenarios: Dict[str, Scenario] = {}

    def register(self, scenario: Scenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario

    def register_many(self, scenarios: List[Scenario]) -> None:
        for s in scenarios:
            self.register(s)

    def get(self, scenario_id: str) -> Optional[Scenario]:
        return self._scenarios.get(scenario_id)

    def list_all(self) -> List[Scenario]:
        return list(self._scenarios.values())

    def filter_by_category(self, category: str) -> List[Scenario]:
        return [s for s in self._scenarios.values() if s.category == category]

    def filter_by_difficulty(self, difficulty: Difficulty) -> List[Scenario]:
        return [s for s in self._scenarios.values() if s.difficulty == difficulty]

    def filter_by_tags(self, tags: List[str]) -> List[Scenario]:
        tag_set = set(tags)
        return [s for s in self._scenarios.values() if tag_set & set(s.tags)]

    def search(
        self,
        category: Optional[str] = None,
        difficulty: Optional[Difficulty] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Scenario]:
        results = self.list_all()
        if category:
            results = [s for s in results if s.category == category]
        if difficulty:
            results = [s for s in results if s.difficulty == difficulty]
        if tags:
            tag_set = set(tags)
            results = [s for s in results if tag_set & set(s.tags)]
        return results

    @property
    def count(self) -> int:
        return len(self._scenarios)
