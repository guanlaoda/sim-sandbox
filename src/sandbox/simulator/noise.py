"""文本风格化噪声注入引擎

根据 NoiseProfile 对用户消息施加各类真实感失真：
ASR 噪声、打字错误、方言特征、表情符号、语气词、自我纠正等。
"""

from __future__ import annotations

import random
import re
from typing import List

from ..models.persona import Dialect, NoiseProfile

# ================================================================
# ASR 同音字 / 近音字替换表  (原字 → 可能的 ASR 错误)
# ================================================================

_HOMOPHONE_MAP: dict[str, list[str]] = {
    # 声母混淆 (zh/z, ch/c, sh/s, n/l, f/h, r/l)
    "北京": ["背景", "备经"],
    "上海": ["商海", "伤害"],
    "南京": ["难经", "南金"],
    "广州": ["光州", "光周"],
    "深圳": ["申圳", "深镇"],
    "成都": ["程度", "承都"],
    "杭州": ["航州", "杭洲"],
    "西安": ["希安", "西按"],
    "机票": ["鸡票", "基票"],
    "航班": ["行班", "杭班"],
    "预订": ["预定", "鱼定"],
    "经济舱": ["精计仓", "经计舱"],
    "商务舱": ["商务仓", "尚务舱"],
    "头等舱": ["头等仓", "投等舱"],
    "出发": ["初发", "出法"],
    "到达": ["道达", "到大"],
    "乘客": ["成客", "称客"],
    "时间": ["实间", "世间"],
    "日期": ["日其", "日齐"],
    "帮我": ["办我", "帮窝"],
    "查一下": ["茶一下", "差一下"],
    "谢谢": ["些些", "泻泻"],
    "可以": ["科以", "克以"],
    "没有": ["没游", "美有"],
    "知道": ["之到", "只到"],
    "怎么": ["咋么", "真么"],
    "需要": ["须要", "虚要"],
    "确认": ["确人", "去认"],
    "取消": ["曲消", "去消"],
}

# 单字级 ASR 替换 (常见混淆)
_CHAR_HOMOPHONE: dict[str, list[str]] = {
    "是": ["式", "事", "市"],
    "的": ["地", "得"],
    "了": ["乐", "勒"],
    "不": ["步", "部"],
    "我": ["窝", "沃"],
    "你": ["泥", "拟"],
    "要": ["耀", "药"],
    "有": ["又", "游"],
    "就": ["旧", "九"],
    "这": ["着", "哲"],
    "那": ["拿", "纳"],
    "把": ["吧", "巴"],
    "从": ["丛", "葱"],
    "去": ["曲", "趣"],
    "到": ["道", "倒"],
    "飞": ["非", "肥"],
    "十": ["四", "石"],
    "四": ["十", "似"],
}

# ================================================================
# 打字 / 拼音选词错误表
# ================================================================

_PINYIN_TYPO_MAP: dict[str, list[str]] = {
    "北京": ["背景", "北晶"],
    "上海": ["商海", "桑海"],
    "航班": ["杭班", "行班"],
    "机票": ["积票", "鸡票"],
    "预订": ["预定", "鱼鼎"],
    "经济舱": ["精济仓", "惊记舱"],
    "出发": ["初发", "粗发"],
    "日期": ["日其", "日骑"],
    "乘客": ["成客", "程客"],
    "帮忙": ["帮芒", "棒忙"],
    "查询": ["差询", "茶询"],
}

# ================================================================
# 方言特征词库
# ================================================================

_DIALECT_WORDS: dict[Dialect, dict[str, list[str]]] = {
    Dialect.NORTHERN: {
        "好的": ["中", "得嘞", "行嘞"],
        "怎么": ["咋", "咋整"],
        "不行": ["不中", "整不了"],
        "知道": ["知道了呗", "知道啦"],
        "可以": ["中", "能成"],
        "在哪里": ["搁哪儿", "在哪儿"],
        "东西": ["东西儿", "玩意儿"],
        "一点": ["一点儿", "一丢丢儿"],
    },
    Dialect.SOUTHERN: {
        "好的": ["好的嘞", "要得"],
        "很好": ["蛮好的", "好得很"],
        "知道": ["晓得", "晓得了"],
        "什么": ["么子", "啥子"],
        "可以": ["可以的嘞", "行的"],
        "厉害": ["好厉害的", "蛮厉害"],
    },
    Dialect.CANTONESE: {
        "谢谢": ["唔该", "多谢"],
        "有没有": ["有冇", "有没"],
        "好的": ["好嘅", "得"],
        "漂亮": ["靓", "好靓"],
        "不好意思": ["唔好意思", "不好意思嘅"],
        "什么": ["乜嘢", "咩"],
    },
    Dialect.SICHUAN: {
        "好的": ["要得", "巴适"],
        "什么": ["啥子", "爪子"],
        "没有": ["莫得", "没得"],
        "知道": ["晓得", "晓不晓得"],
        "厉害": ["巴适得板", "牛皮"],
        "可以": ["要得", "可以嘛"],
        "怎么": ["啷个", "咋个"],
    },
    Dialect.SHANGHAI: {
        "我": ["阿拉"],
        "你": ["侬"],
        "很好": ["老好的", "交关好"],
        "知道": ["晓得", "阿晓得"],
        "谢谢": ["谢谢侬"],
        "什么": ["啥个"],
    },
}

# 方言后缀/语气词
_DIALECT_SUFFIXES: dict[Dialect, list[str]] = {
    Dialect.NORTHERN: ["呗", "嘛", "呢吧", "不是", "哇"],
    Dialect.SOUTHERN: ["嘞", "喏", "啵", "咯", "哈"],
    Dialect.CANTONESE: ["嘅", "喇", "咩", "啦", "咧"],
    Dialect.SICHUAN: ["嘛", "撒", "噻", "哦", "嘞"],
    Dialect.SHANGHAI: ["伐", "嘛", "哦", "呀", "嗯哪"],
}

# ================================================================
# 表情符号库
# ================================================================

_EMOJI_POSITIVE: list[str] = ["😄", "👌", "🙏", "✅", "👍", "😊", "🎉", "💪"]
_EMOJI_NEGATIVE: list[str] = ["😭", "😡", "💢", "😤", "😞", "😢", "🤦"]
_EMOJI_NEUTRAL: list[str] = ["🤔", "😅", "😏", "🙃", "😐", "👀"]
_EMOJI_URGENT: list[str] = ["🔥", "⚡", "‼️", "🆘", "❗"]

# ================================================================
# 语气词 / 犹豫词
# ================================================================

_FILLER_WORDS: list[str] = [
    "嗯", "那个", "就是说", "额", "这个", "反正", "对了",
    "嗯...那个", "怎么说呢", "就是", "然后", "所以说",
]

# ================================================================
# 网络用语
# ================================================================

_INTERNET_SLANG: dict[str, list[str]] = {
    "很好": ["yyds", "绝绝子", "太顶了"],
    "厉害": ["6", "666", "牛"],
    "好的": ["OK的", "收到", "rr", "好嘞"],
    "没办法": ["蚌埠住了", "绷不住了", "无语"],
    "着急": ["急死了", "DNA动了", "等不及了"],
    "谢谢": ["感谢老铁", "谢谢大佬", "蟹蟹"],
    "不好": ["寄了", "芭比Q了", "完蛋"],
    "生气": ["真的会谢", "无语死了", "麻了"],
}

# ================================================================
# 缩写映射
# ================================================================

_ABBREVIATION_MAP: dict[str, str] = {
    "北京": "bj",
    "上海": "sh",
    "广州": "gz",
    "深圳": "sz",
    "成都": "cd",
    "杭州": "hz",
    "南京": "nj",
    "西安": "xa",
    "经济舱": "jjc",
    "商务舱": "swc",
    "头等舱": "tdc",
}


# ================================================================
# 噪声注入引擎
# ================================================================

class NoiseInjector:
    """根据 NoiseProfile 对消息文本施加风格化噪声"""

    def __init__(self, profile: NoiseProfile, seed: int | None = None) -> None:
        self._profile = profile
        self._rng = random.Random(seed)

    @property
    def is_active(self) -> bool:
        """是否有任何噪声被启用"""
        p = self._profile
        return (
            p.asr_error_rate > 0
            or p.typo_rate > 0
            or p.dialect != Dialect.NONE
            or p.emoji_frequency > 0
            or p.filler_word_rate > 0
            or p.abbreviation_rate > 0
            or p.internet_slang
            or p.self_correction_rate > 0
            or p.punctuation_chaos > 0
        )

    def apply(self, text: str, mood: float = 0.5) -> str:
        """对文本施加所有已启用的噪声，返回处理后的文本"""
        if not self.is_active or not text:
            return text

        p = self._profile

        # 1. 缩写替换 (在其他错误之前，因为替换的是完整词)
        if p.abbreviation_rate > 0:
            text = self._apply_abbreviations(text, p.abbreviation_rate)

        # 2. ASR 同音字错误
        if p.asr_error_rate > 0:
            text = self._apply_asr_errors(text, p.asr_error_rate)

        # 3. 打字错误
        if p.typo_rate > 0:
            text = self._apply_typo_errors(text, p.typo_rate)

        # 4. 方言特征词替换
        if p.dialect != Dialect.NONE:
            text = self._apply_dialect(text, p.dialect)

        # 5. 网络用语替换
        if p.internet_slang:
            text = self._apply_internet_slang(text)

        # 6. 语气词插入
        if p.filler_word_rate > 0:
            text = self._apply_filler_words(text, p.filler_word_rate)

        # 7. 自我纠正
        if p.self_correction_rate > 0:
            text = self._apply_self_correction(text, p.self_correction_rate)

        # 8. 表情符号
        if p.emoji_frequency > 0:
            text = self._apply_emoji(text, p.emoji_frequency, mood)

        # 9. 标点混乱
        if p.punctuation_chaos > 0:
            text = self._apply_punctuation_chaos(text, p.punctuation_chaos)

        return text

    # ---- 各噪声实现 ----

    def _apply_asr_errors(self, text: str, rate: float) -> str:
        """ASR 同音字/近音字替换"""
        # 先尝试词级别替换
        for word, replacements in _HOMOPHONE_MAP.items():
            if word in text and self._rng.random() < rate:
                text = text.replace(word, self._rng.choice(replacements), 1)

        # 再尝试单字替换 (较低概率)
        char_rate = rate * 0.3
        result = list(text)
        for i, ch in enumerate(result):
            if ch in _CHAR_HOMOPHONE and self._rng.random() < char_rate:
                result[i] = self._rng.choice(_CHAR_HOMOPHONE[ch])
        return "".join(result)

    def _apply_typo_errors(self, text: str, rate: float) -> str:
        """打字/拼音选词错误"""
        for word, replacements in _PINYIN_TYPO_MAP.items():
            if word in text and self._rng.random() < rate:
                text = text.replace(word, self._rng.choice(replacements), 1)
        return text

    def _apply_abbreviations(self, text: str, rate: float) -> str:
        """地名/术语缩写"""
        for word, abbr in _ABBREVIATION_MAP.items():
            if word in text and self._rng.random() < rate:
                text = text.replace(word, abbr, 1)
        return text

    def _apply_dialect(self, text: str, dialect: Dialect) -> str:
        """方言特征词替换和后缀添加"""
        word_map = _DIALECT_WORDS.get(dialect, {})
        for standard, variants in word_map.items():
            if standard in text and self._rng.random() < 0.5:
                text = text.replace(standard, self._rng.choice(variants), 1)

        # 添加方言语气后缀 (约 30% 概率)
        suffixes = _DIALECT_SUFFIXES.get(dialect, [])
        if suffixes and self._rng.random() < 0.3:
            # 去掉句末标点再加后缀
            text = text.rstrip("。，！？.!?,")
            text += self._rng.choice(suffixes)

        return text

    def _apply_internet_slang(self, text: str) -> str:
        """网络用语替换 (约 30% 概率命中)"""
        for keyword, slangs in _INTERNET_SLANG.items():
            if keyword in text and self._rng.random() < 0.3:
                text = text.replace(keyword, self._rng.choice(slangs), 1)
        return text

    def _apply_filler_words(self, text: str, rate: float) -> str:
        """在句首或逗号处插入语气词"""
        if self._rng.random() > rate:
            return text

        filler = self._rng.choice(_FILLER_WORDS)

        # 句首插入
        if self._rng.random() < 0.6:
            # 去掉句首已有的语气词避免重复
            for existing in _FILLER_WORDS:
                if text.startswith(existing):
                    return text
            sep = "，" if not text.startswith("，") else ""
            return f"{filler}{sep}{text}"

        # 逗号处插入
        parts = text.split("，", 1)
        if len(parts) == 2:
            return f"{parts[0]}，{filler}，{parts[1]}"
        return text

    def _apply_self_correction(self, text: str, rate: float) -> str:
        """自我纠正：先说错再改正"""
        if self._rng.random() > rate:
            return text

        # 寻找可以"说错"的城市名
        cities = ["北京", "上海", "广州", "深圳", "成都", "杭州", "南京", "西安"]
        corrections = {
            "北京": "南京", "上海": "杭州", "广州": "深圳",
            "深圳": "广州", "成都": "重庆", "杭州": "上海",
            "南京": "北京", "西安": "西宁",
        }
        for city in cities:
            if city in text and city in corrections:
                wrong = corrections[city]
                correction_phrases = [
                    f"{wrong}，不对，{city}",
                    f"{wrong}，哦不，是{city}",
                    f"{wrong}...等等，{city}才对",
                ]
                text = text.replace(city, self._rng.choice(correction_phrases), 1)
                break

        return text

    def _apply_emoji(self, text: str, frequency: float, mood: float) -> str:
        """添加表情符号"""
        if self._rng.random() > frequency:
            return text

        if mood > 0.6:
            emoji = self._rng.choice(_EMOJI_POSITIVE)
        elif mood < 0.3:
            emoji = self._rng.choice(_EMOJI_NEGATIVE)
        else:
            emoji = self._rng.choice(_EMOJI_NEUTRAL)

        # 30% 概率额外加急迫表情
        if mood < 0.4 and self._rng.random() < 0.3:
            emoji += self._rng.choice(_EMOJI_URGENT)

        return text.rstrip("。.") + emoji

    def _apply_punctuation_chaos(self, text: str, rate: float) -> str:
        """标点遗漏或滥用"""
        if self._rng.random() > rate:
            return text

        if self._rng.random() < 0.5:
            # 删除标点
            text = re.sub(r"[，。！？,\.!?]", "", text)
        else:
            # 叠加感叹号
            text = text.rstrip("。.") + "！！！"

        return text
