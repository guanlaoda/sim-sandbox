"""用户画像生成器"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
import yaml

from ..config import PersonaGenerationConfig
from ..models.persona import (
    AgeGroup,
    CommunicationStyle,
    Dialect,
    NoiseProfile,
    PersonaSkeleton,
    UserPersona,
)

logger = logging.getLogger(__name__)


class DistributionSampler:
    """基于配置分布的参数采样器"""

    def __init__(self, config_path: str | Path, seed: Optional[int] = None) -> None:
        self._config_path = Path(config_path)
        self._rng = np.random.default_rng(seed)
        self._distributions: Dict[str, Any] = {}
        self._correlations: List[Dict[str, Any]] = []
        self._load_config()

    def _load_config(self) -> None:
        if not self._config_path.exists():
            logger.warning("Distribution config not found: %s, using defaults", self._config_path)
            self._distributions = self._default_distributions()
            return

        with open(self._config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        sampler_cfg = raw.get("persona_generation", raw).get("sampler", raw)
        self._distributions = sampler_cfg.get("distributions", self._default_distributions())
        self._correlations = sampler_cfg.get("correlations", [])

    @staticmethod
    def _default_distributions() -> Dict[str, Any]:
        return {
            "age_group": {"young": 0.4, "middle": 0.4, "senior": 0.2},
            "tech_literacy": {"type": "normal", "mean": 0.6, "std": 0.2},
            "patience_level": {"type": "uniform", "min": 0.2, "max": 0.9},
            "communication_style": {
                "concise": 0.3,
                "verbose": 0.3,
                "emotional": 0.2,
                "formal": 0.2,
            },
            "intent_clarity": {"type": "uniform", "min": 0.3, "max": 1.0},
        }

    def _weighted_choice(self, dist: Dict[str, float]) -> str:
        keys = list(dist.keys())
        weights = np.array([dist[k] for k in keys], dtype=float)
        # 过滤掉非权重键 (如 type)
        valid = [(k, w) for k, w in zip(keys, weights) if isinstance(w, (int, float))]
        if not valid:
            return keys[0]
        vkeys, vweights = zip(*valid)
        vweights_arr = np.array(vweights, dtype=float)
        vweights_arr /= vweights_arr.sum()
        return str(self._rng.choice(list(vkeys), p=vweights_arr))

    def _sample_float(self, dist: Dict[str, Any]) -> float:
        dist_type = dist.get("type", "uniform")
        if dist_type == "normal":
            val = self._rng.normal(dist.get("mean", 0.5), dist.get("std", 0.2))
        elif dist_type == "uniform":
            val = self._rng.uniform(dist.get("min", 0.0), dist.get("max", 1.0))
        else:
            val = self._rng.uniform(0.0, 1.0)
        return float(np.clip(val, 0.0, 1.0))

    def _matches_condition(self, condition: Dict[str, Any], state: Dict[str, Any]) -> bool:
        for key, expected in condition.items():
            if state.get(key) != expected:
                return False
        return True

    def sample(self, domain: str) -> PersonaSkeleton:
        """采样一个画像骨架"""
        d = self._distributions

        age_group = self._weighted_choice(d.get("age_group", {"middle": 1.0}))
        tech_literacy = self._sample_float(
            d.get("tech_literacy", {"type": "normal", "mean": 0.6, "std": 0.2})
        )

        # 应用相关性
        state = {"age_group": age_group}
        for corr in self._correlations:
            if self._matches_condition(corr.get("if", {}), state):
                then = corr.get("then", {})
                if "tech_literacy" in then:
                    tech_literacy = self._sample_float(then["tech_literacy"])

        patience_level = self._sample_float(
            d.get("patience_level", {"type": "uniform", "min": 0.2, "max": 0.9})
        )
        comm_style = self._weighted_choice(
            d.get(
                "communication_style",
                {"concise": 0.3, "verbose": 0.3, "emotional": 0.2, "formal": 0.2},
            )
        )
        intent_clarity = self._sample_float(
            d.get("intent_clarity", {"type": "uniform", "min": 0.3, "max": 1.0})
        )

        return PersonaSkeleton(
            persona_id=f"persona_{uuid4().hex[:8]}",
            age_group=AgeGroup(age_group),
            tech_literacy=round(tech_literacy, 2),
            patience_level=round(patience_level, 2),
            communication_style=CommunicationStyle(comm_style),
            intent_clarity=round(intent_clarity, 2),
            domain_knowledge={domain: round(float(self._rng.uniform(0, 1)), 2)},
            noise_profile=self._sample_noise_profile(
                d, age_group, comm_style, tech_literacy
            ),
        )

    def _sample_noise_profile(
        self,
        distributions: Dict[str, Any],
        age_group: str,
        comm_style: str,
        tech_literacy: float,
    ) -> NoiseProfile:
        """根据分布配置和已有属性采样噪声配置"""
        nd = distributions.get("noise_profile", {})

        # ASR 错误率
        asr_error_rate = self._sample_float(
            nd.get("asr_error_rate", {"type": "uniform", "min": 0.0, "max": 0.15})
        )
        # 老年人口音更重
        if age_group == "senior":
            asr_error_rate = min(1.0, asr_error_rate + 0.1)

        # 打字错误率
        typo_rate = self._sample_float(
            nd.get("typo_rate", {"type": "uniform", "min": 0.0, "max": 0.1})
        )
        # 技术素养低 → 打字错误更多
        if tech_literacy < 0.3:
            typo_rate = min(1.0, typo_rate + 0.08)

        # 方言
        dialect_dist = nd.get("dialect", {
            "none": 0.5, "northern": 0.15, "southern": 0.1,
            "cantonese": 0.1, "sichuan": 0.1, "shanghai": 0.05,
        })
        dialect = self._weighted_choice(dialect_dist)

        # 表情频率
        emoji_frequency = self._sample_float(
            nd.get("emoji_frequency", {"type": "uniform", "min": 0.0, "max": 0.3})
        )
        if age_group == "young":
            emoji_frequency = min(1.0, emoji_frequency + 0.15)
        elif age_group == "senior":
            emoji_frequency = max(0.0, emoji_frequency - 0.1)

        # 语气词
        filler_word_rate = self._sample_float(
            nd.get("filler_word_rate", {"type": "uniform", "min": 0.0, "max": 0.3})
        )
        if comm_style == "verbose":
            filler_word_rate = min(1.0, filler_word_rate + 0.15)

        # 缩写
        abbreviation_rate = self._sample_float(
            nd.get("abbreviation_rate", {"type": "uniform", "min": 0.0, "max": 0.15})
        )
        if age_group == "young" and tech_literacy > 0.6:
            abbreviation_rate = min(1.0, abbreviation_rate + 0.1)

        # 网络用语
        internet_slang = (
            age_group == "young"
            and tech_literacy > 0.5
            and self._rng.random() < nd.get("internet_slang_probability", 0.4)
        )

        # 自我纠正
        self_correction_rate = self._sample_float(
            nd.get("self_correction_rate", {"type": "uniform", "min": 0.0, "max": 0.1})
        )

        # 标点混乱
        punctuation_chaos = self._sample_float(
            nd.get("punctuation_chaos", {"type": "uniform", "min": 0.0, "max": 0.15})
        )
        if comm_style == "emotional":
            punctuation_chaos = min(1.0, punctuation_chaos + 0.1)

        # 应用 noise_profile 相关性重写
        state = {"age_group": age_group, "communication_style": comm_style}
        for corr in self._correlations:
            if self._matches_condition(corr.get("if", {}), state):
                then = corr.get("then", {})
                np_overrides = then.get("noise_profile", {})
                if "asr_error_rate" in np_overrides:
                    asr_error_rate = self._sample_float(np_overrides["asr_error_rate"])
                if "typo_rate" in np_overrides:
                    typo_rate = self._sample_float(np_overrides["typo_rate"])
                if "emoji_frequency" in np_overrides:
                    emoji_frequency = self._sample_float(np_overrides["emoji_frequency"])

        return NoiseProfile(
            asr_error_rate=round(asr_error_rate, 2),
            typo_rate=round(typo_rate, 2),
            dialect=Dialect(dialect),
            emoji_frequency=round(emoji_frequency, 2),
            filler_word_rate=round(filler_word_rate, 2),
            abbreviation_rate=round(abbreviation_rate, 2),
            internet_slang=internet_slang,
            self_correction_rate=round(self_correction_rate, 2),
            punctuation_chaos=round(punctuation_chaos, 2),
        )


class PersonaGenerator:
    """用户画像生成器 — 两阶段生成 (采样 + LLM 丰化)"""

    def __init__(self, config: PersonaGenerationConfig | None = None, project_root: Path | None = None) -> None:
        self.config = config or PersonaGenerationConfig()
        project_root = project_root or Path.cwd()
        dist_path = project_root / self.config.distribution_config
        self._sampler = DistributionSampler(dist_path, seed=config.seed)

    def generate_skeleton(self) -> PersonaSkeleton:
        """生成画像骨架"""
        return self._sampler.sample(self.config.domain)

    def generate_skeletons(self, count: int) -> List[PersonaSkeleton]:
        """批量生成画像骨架"""
        return [self._sampler.sample(self.config.domain) for _ in range(count)]

    def enrich_skeleton(self, skeleton: PersonaSkeleton) -> UserPersona:
        """将骨架丰化为完整画像 (规则版, 不调用 LLM)"""
        age_ranges = {
            AgeGroup.YOUNG: (18, 35),
            AgeGroup.MIDDLE: (36, 55),
            AgeGroup.SENIOR: (56, 75),
        }
        age_min, age_max = age_ranges[skeleton.age_group]
        rng = np.random.default_rng(hash(skeleton.persona_id) % (2**32))
        age = int(rng.integers(age_min, age_max + 1))

        # 根据年龄和特征生成合理的职业
        occupation = self._pick_occupation(skeleton, rng)
        habits = self._pick_language_habits(skeleton, rng)
        triggers = self._pick_emotional_triggers(skeleton, rng)

        return UserPersona(
            skeleton=skeleton,
            name=self._generate_name(rng),
            age=age,
            occupation=occupation,
            personality_summary=self._generate_personality(skeleton),
            background_story=f"{occupation}，{age}岁，{skeleton.communication_style.value}型沟通风格。",
            language_habits=habits,
            emotional_triggers=triggers,
            typical_expressions=self._generate_expressions(skeleton),
        )

    def generate(self, count: int = 1) -> List[UserPersona]:
        """生成完整画像 (骨架 + 基础丰化)"""
        skeletons = self.generate_skeletons(count)
        return [self.enrich_skeleton(s) for s in skeletons]

    # ---- 辅助方法 ----

    @staticmethod
    def _generate_name(rng: np.random.Generator) -> str:
        surnames = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
        given_names = ["伟", "芳", "敏", "强", "丽", "军", "洋", "勇", "艳", "杰",
                       "明", "霞", "秀英", "建国", "小红", "志远", "雪梅", "浩然"]
        return str(rng.choice(surnames)) + str(rng.choice(given_names))

    @staticmethod
    def _pick_occupation(skeleton: PersonaSkeleton, rng: np.random.Generator) -> str:
        if skeleton.age_group == AgeGroup.SENIOR:
            options = ["退休教师", "退休公务员", "个体商户", "退休工人", "家庭主妇/夫"]
        elif skeleton.tech_literacy > 0.7:
            options = ["软件工程师", "产品经理", "大学生", "设计师", "数据分析师"]
        elif skeleton.age_group == AgeGroup.YOUNG:
            options = ["销售员", "服务员", "快递员", "大学生", "自由职业者"]
        else:
            options = ["公司职员", "小生意人", "教师", "医生", "公务员"]
        return str(rng.choice(options))

    @staticmethod
    def _pick_language_habits(skeleton: PersonaSkeleton, rng: np.random.Generator) -> List[str]:
        habits: List[str] = []
        if skeleton.communication_style == CommunicationStyle.VERBOSE:
            habits += ["就是说", "然后呢", "嗯那个", "你知道吧"]
        elif skeleton.communication_style == CommunicationStyle.EMOTIONAL:
            habits += ["哎呀", "天哪", "太...了吧", "！！"]
        elif skeleton.communication_style == CommunicationStyle.FORMAL:
            habits += ["请问", "麻烦您", "感谢", "贵公司"]
        else:
            habits += ["嗯", "好", "行", "OK"]

        if skeleton.tech_literacy < 0.3:
            habits.append("那个啥...")
        if skeleton.patience_level < 0.3:
            habits.append("快点")
        return habits[:5]

    @staticmethod
    def _pick_emotional_triggers(
        skeleton: PersonaSkeleton, rng: np.random.Generator
    ) -> List[str]:
        triggers: List[str] = []
        if skeleton.patience_level < 0.4:
            triggers += ["等待时间过长", "重复提问"]
        if skeleton.communication_style == CommunicationStyle.EMOTIONAL:
            triggers += ["被忽视", "态度冷漠"]
        triggers += ["被误解", "得不到帮助"]
        return triggers[:4]

    @staticmethod
    def _generate_personality(skeleton: PersonaSkeleton) -> str:
        style_desc = {
            CommunicationStyle.CONCISE: "言简意赅",
            CommunicationStyle.VERBOSE: "表达详细",
            CommunicationStyle.EMOTIONAL: "情绪丰富",
            CommunicationStyle.FORMAL: "谈吐正式",
        }
        patience_desc = "有耐心" if skeleton.patience_level > 0.6 else "容易急躁"
        tech_desc = (
            "熟悉技术" if skeleton.tech_literacy > 0.6 else "不太懂技术"
        )
        return f"{style_desc.get(skeleton.communication_style, '普通')}的用户，{patience_desc}，{tech_desc}。"

    @staticmethod
    def _generate_expressions(skeleton: PersonaSkeleton) -> Dict[str, str]:
        base = {}
        if skeleton.intent_clarity > 0.7:
            base["开场"] = "你好，我想..."
            base["不满"] = "这不是我要的"
        else:
            base["开场"] = "嗯...那个...我有个事想问问"
            base["不满"] = "嗯...这个好像不太对吧..."
        return base
