"""YAML 场景加载器"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import yaml

from ..models.scenario import Scenario

logger = logging.getLogger(__name__)


class ScenarioLoader:
    """从 YAML 文件加载场景定义"""

    def __init__(self, scenarios_dir: str | Path = "scenarios") -> None:
        self._dir = Path(scenarios_dir)

    def load_file(self, path: str | Path) -> Scenario:
        """加载单个场景文件"""
        p = Path(path)
        if not p.is_absolute():
            p = self._dir / p
        if not p.exists():
            raise FileNotFoundError(f"Scenario file not found: {p}")

        with open(p, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        return Scenario.model_validate(raw)

    def load_directory(self, sub_path: str = "") -> List[Scenario]:
        """从目录递归加载所有 .yaml/.yml 场景"""
        target = self._dir / sub_path if sub_path else self._dir
        if not target.exists():
            logger.warning("Scenarios directory not found: %s", target)
            return []

        scenarios: List[Scenario] = []
        for f in sorted(target.rglob("*.yaml")):
            try:
                scenarios.append(self.load_file(f.resolve()))
                logger.info("Loaded scenario: %s", f.name)
            except Exception as exc:
                logger.error("Failed to load %s: %s", f, exc)

        for f in sorted(target.rglob("*.yml")):
            try:
                scenarios.append(self.load_file(f.resolve()))
            except Exception as exc:
                logger.error("Failed to load %s: %s", f, exc)

        return scenarios

    def load_by_patterns(
        self,
        include: List[str],
        exclude: List[str] | None = None,
    ) -> List[Scenario]:
        """按 glob 模式加载场景"""
        import fnmatch

        all_files = sorted(self._dir.rglob("*.yaml")) + sorted(self._dir.rglob("*.yml"))
        exclude = exclude or []

        matched: List[Path] = []
        for f in all_files:
            rel = str(f.relative_to(self._dir))
            if any(fnmatch.fnmatch(rel, pat) for pat in include):
                if not any(fnmatch.fnmatch(rel, ex) for ex in exclude):
                    matched.append(f)

        scenarios: List[Scenario] = []
        for f in matched:
            try:
                scenarios.append(self.load_file(f))
            except Exception as exc:
                logger.error("Failed to load %s: %s", f, exc)
        return scenarios

    def validate_all(self) -> List[dict]:
        """验证目录下所有场景的格式正确性"""
        results = []
        for f in sorted(self._dir.resolve().rglob("*.yaml")):
            try:
                self.load_file(f)
                results.append({"file": str(f), "valid": True})
            except Exception as exc:
                results.append({"file": str(f), "valid": False, "error": str(exc)})
        return results
