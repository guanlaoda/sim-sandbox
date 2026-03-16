"""测试: 用户画像生成器"""

import pytest

from sandbox.config import PersonaGenerationConfig
from sandbox.models.persona import AgeGroup, CommunicationStyle, PersonaSkeleton, UserPersona
from sandbox.persona.generator import PersonaGenerator


class TestPersonaGenerator:
    def test_generate_returns_valid_persona(self) -> None:
        gen = PersonaGenerator(config=PersonaGenerationConfig(seed=42))
        personas = gen.generate(count=1)
        persona = personas[0]

        assert isinstance(persona, UserPersona)
        assert persona.name
        assert persona.age >= 10
        assert persona.occupation
        assert persona.personality_summary
        assert 0.0 <= persona.skeleton.tech_literacy <= 1.0
        assert 0.0 <= persona.skeleton.patience_level <= 1.0

    def test_generate_with_seed_is_deterministic(self) -> None:
        gen1 = PersonaGenerator(config=PersonaGenerationConfig(seed=123))
        gen2 = PersonaGenerator(config=PersonaGenerationConfig(seed=123))

        p1 = gen1.generate(count=1)[0]
        p2 = gen2.generate(count=1)[0]

        assert p1.skeleton.persona_id != p2.skeleton.persona_id  # uuid 不同
        assert p1.skeleton.age_group == p2.skeleton.age_group
        assert p1.skeleton.tech_literacy == p2.skeleton.tech_literacy
        assert p1.skeleton.patience_level == p2.skeleton.patience_level

    def test_generate_multiple_diverse(self) -> None:
        gen = PersonaGenerator(config=PersonaGenerationConfig(seed=0))
        personas = gen.generate(count=10)

        # 至少有 2 种不同的 communication style
        styles = {p.skeleton.communication_style for p in personas}
        assert len(styles) >= 2

    def test_persona_to_system_prompt(self) -> None:
        gen = PersonaGenerator(config=PersonaGenerationConfig(seed=42))
        persona = gen.generate(count=1)[0]
        prompt = persona.to_system_prompt()

        assert persona.name in prompt
        assert str(persona.age) in prompt
        assert persona.occupation in prompt


class TestPersonaSkeleton:
    def test_valid_skeleton(self) -> None:
        sk = PersonaSkeleton(
            persona_id="test-001",
            age_group=AgeGroup.MIDDLE,
            tech_literacy=0.7,
            patience_level=0.5,
            communication_style=CommunicationStyle.CONCISE,
            intent_clarity=0.8,
        )
        assert sk.persona_id == "test-001"
        assert sk.tech_literacy == 0.7

    def test_skeleton_domain_knowledge_default(self) -> None:
        sk = PersonaSkeleton(
            persona_id="test-002",
            age_group=AgeGroup.YOUNG,
            tech_literacy=0.9,
            patience_level=0.8,
            communication_style=CommunicationStyle.EMOTIONAL,
            intent_clarity=0.5,
        )
        assert sk.domain_knowledge == {}
