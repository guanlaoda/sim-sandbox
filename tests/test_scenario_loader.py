"""测试: 场景加载器"""

import pytest
import tempfile
from pathlib import Path

import yaml

from sandbox.models.scenario import Scenario
from sandbox.scenario.loader import ScenarioLoader
from sandbox.scenario.registry import ScenarioRegistry


SAMPLE_SCENARIO_YAML = {
    "scenario_id": "test_001",
    "name": "测试场景",
    "description": "一个简单的测试场景",
    "category": "test",
    "tags": ["unit-test"],
    "difficulty": "easy",
    "user_goal": {
        "primary_intent": "查询余额",
        "slots": {"account_id": "12345"},
        "success_indicators": ["余额为"],
    },
    "environment": {
        "data": {"balance": 1000},
    },
    "constraints": {
        "max_turns": 10,
        "max_duration_seconds": 60,
    },
    "evaluation_config": {
        "accuracy_weight": 0.5,
        "safety_weight": 0.3,
        "context_weight": 0.2,
    },
}


class TestScenarioLoader:
    def test_load_file(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(
            yaml.dump(SAMPLE_SCENARIO_YAML, allow_unicode=True),
            encoding="utf-8",
        )

        loader = ScenarioLoader(scenarios_dir=tmp_path)
        scenario = loader.load_file(str(yaml_path))

        assert isinstance(scenario, Scenario)
        assert scenario.scenario_id == "test_001"
        assert scenario.name == "测试场景"
        assert scenario.user_goal.slots["account_id"] == "12345"

    def test_load_directory(self, tmp_path: Path) -> None:
        for i in range(3):
            data = dict(SAMPLE_SCENARIO_YAML)
            data["scenario_id"] = f"test_{i:03d}"
            data["name"] = f"场景_{i}"
            fpath = tmp_path / f"scenario_{i}.yaml"
            fpath.write_text(
                yaml.dump(data, allow_unicode=True), encoding="utf-8"
            )

        loader = ScenarioLoader(scenarios_dir=tmp_path)
        scenarios = loader.load_directory()
        assert len(scenarios) == 3

    def test_validate_all_passes(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "ok.yaml"
        yaml_path.write_text(
            yaml.dump(SAMPLE_SCENARIO_YAML, allow_unicode=True),
            encoding="utf-8",
        )

        loader = ScenarioLoader(scenarios_dir=tmp_path)
        scenario = loader.load_file(str(yaml_path))
        errors = loader.validate_all()
        valid_count = sum(1 for e in errors if e["valid"])
        assert valid_count > 0


class TestScenarioRegistry:
    def _make_scenario(self, sid: str, category: str = "test", difficulty: str = "easy") -> Scenario:
        data = dict(SAMPLE_SCENARIO_YAML)
        data["scenario_id"] = sid
        data["category"] = category
        data["difficulty"] = difficulty
        return Scenario.model_validate(data)

    def test_register_and_get(self) -> None:
        reg = ScenarioRegistry()
        s = self._make_scenario("s001")
        reg.register(s)
        assert reg.get("s001") is s

    def test_filter_by_category(self) -> None:
        reg = ScenarioRegistry()
        reg.register(self._make_scenario("s1", category="flight"))
        reg.register(self._make_scenario("s2", category="hotel"))
        reg.register(self._make_scenario("s3", category="flight"))

        result = reg.filter_by_category("flight")
        assert len(result) == 2

    def test_filter_by_difficulty(self) -> None:
        reg = ScenarioRegistry()
        reg.register(self._make_scenario("s1", difficulty="easy"))
        reg.register(self._make_scenario("s2", difficulty="hard"))

        result = reg.filter_by_difficulty("hard")
        assert len(result) == 1
        assert result[0].scenario_id == "s2"

    def test_search_multi_filter(self) -> None:
        reg = ScenarioRegistry()
        reg.register(self._make_scenario("s1", category="flight", difficulty="easy"))
        reg.register(self._make_scenario("s2", category="flight", difficulty="hard"))
        reg.register(self._make_scenario("s3", category="hotel", difficulty="easy"))

        result = reg.search(category="flight", difficulty="easy")
        assert len(result) == 1
        assert result[0].scenario_id == "s1"
