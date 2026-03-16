"""报告生成器 — 将评测结果输出为 HTML / JSON / Markdown"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from ..orchestrator.runner import BatchResult, RunResult

logger = logging.getLogger(__name__)


class Reporter:
    """生成多格式评测报告"""

    def __init__(self, output_dir: str = "output/reports") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def generate_json(self, batch: BatchResult, filename: str = "report.json") -> Path:
        """生成 JSON 格式报告"""
        data = {
            "summary": {
                "total": batch.total,
                "passed": batch.passed,
                "failed": batch.failed,
                "pass_rate": round(batch.pass_rate, 3),
            },
            "results": [self._serialize_result(r) for r in batch.results],
        }
        path = self._output_dir / filename
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("JSON report saved to %s", path)
        return path

    def generate_markdown(self, batch: BatchResult, filename: str = "report.md") -> Path:
        """生成 Markdown 格式报告"""
        lines = [
            "# 仿真测试报告",
            "",
            "## 摘要",
            "",
            f"- **总测试数**: {batch.total}",
            f"- **通过**: {batch.passed}",
            f"- **失败**: {batch.failed}",
            f"- **通过率**: {batch.pass_rate:.1%}",
            "",
            "## 详细结果",
            "",
            "| 场景 | 人设 | 轮次 | 综合分 | 通过 |",
            "|------|------|------|--------|------|",
        ]

        for r in batch.results:
            status = "✅" if r.evaluation.overall_passed else "❌"
            lines.append(
                f"| {r.scenario.name} | {r.persona.name} | "
                f"{len(r.conversation.turns)} | "
                f"{r.evaluation.overall_score:.3f} | {status} |"
            )

        lines.append("")
        lines.append("## 各维度评分")
        lines.append("")

        for r in batch.results:
            lines.append(f"### {r.scenario.name} × {r.persona.name}")
            lines.append("")
            lines.append("| 维度 | 分数 | 通过 |")
            lines.append("|------|------|------|")
            for ev in r.evaluation.results:
                status = "✅" if ev.passed else "❌"
                lines.append(f"| {ev.dimension} | {ev.score:.3f} | {status} |")
            lines.append("")

        lines.append("## 对话记录")
        lines.append("")

        for r in batch.results:
            lines.append(f"### {r.scenario.name} × {r.persona.name}")
            lines.append("")
            for t in r.conversation.turns:
                lines.append(f"**第 {t.turn_number} 轮**")
                lines.append("")
                if t.user_internal_thought:
                    lines.append(f"> 💭 *{t.user_internal_thought}*")
                    lines.append("")
                lines.append(f"🧑 **用户**: {t.user_message}")
                lines.append("")
                lines.append(f"🤖 **机器人**: {t.bot_response}")
                if t.bot_latency_ms:
                    lines.append(f"  *(延迟 {t.bot_latency_ms:.0f}ms)*")
                lines.append("")
            lines.append("---")
            lines.append("")

        path = self._output_dir / filename
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Markdown report saved to %s", path)
        return path

    def generate_html(self, batch: BatchResult, filename: str = "report.html") -> Path:
        """生成 HTML 格式报告"""
        rows = ""
        for r in batch.results:
            status = "✅" if r.evaluation.overall_passed else "❌"
            dim_cells = ""
            for ev in r.evaluation.results:
                color = "#4caf50" if ev.passed else "#f44336"
                dim_cells += f'<td style="color:{color}">{ev.score:.3f}</td>'
            rows += (
                f"<tr>"
                f"<td>{r.scenario.name}</td>"
                f"<td>{r.persona.name}</td>"
                f"<td>{len(r.conversation.turns)}</td>"
                f"<td><b>{r.evaluation.overall_score:.3f}</b></td>"
                f"{dim_cells}"
                f"<td>{status}</td>"
                f"</tr>\n"
            )

        # 获取维度名
        dim_headers = ""
        if batch.results:
            for ev in batch.results[0].evaluation.results:
                dim_headers += f"<th>{ev.dimension}</th>"

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>仿真测试报告</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2em; }}
h1 {{ color: #333; }}
h2 {{ color: #555; margin-top: 2em; }}
.summary {{ background: #f5f5f5; padding: 1em; border-radius: 8px; margin-bottom: 1.5em; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
th {{ background: #4a90d9; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.chat-section {{ margin-top: 2em; }}
.chat-block {{ background: #fafafa; border: 1px solid #e0e0e0; border-radius: 8px; padding: 1em; margin-bottom: 1.5em; }}
.chat-block h3 {{ margin-top: 0; color: #4a90d9; }}
.turn {{ margin-bottom: 1em; padding-bottom: 0.8em; border-bottom: 1px dashed #eee; }}
.turn:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
.turn-label {{ font-size: 0.85em; color: #999; margin-bottom: 0.3em; }}
.thought {{ color: #888; font-style: italic; font-size: 0.9em; margin-bottom: 0.3em; }}
.user-msg {{ background: #e3f2fd; padding: 0.5em 0.8em; border-radius: 12px; display: inline-block; max-width: 85%; margin-bottom: 0.3em; }}
.bot-msg {{ background: #f1f8e9; padding: 0.5em 0.8em; border-radius: 12px; display: inline-block; max-width: 85%; }}
.latency {{ color: #aaa; font-size: 0.8em; margin-left: 0.5em; }}
details {{ margin-top: 1em; }}
details summary {{ cursor: pointer; color: #4a90d9; font-weight: bold; }}
</style>
</head>
<body>
<h1>仿真测试报告</h1>
<div class="summary">
<p>总测试数: <b>{batch.total}</b> | 通过: <b>{batch.passed}</b> | 失败: <b>{batch.failed}</b> | 通过率: <b>{batch.pass_rate:.1%}</b></p>
</div>
<h2>评测结果</h2>
<table>
<tr>
<th>场景</th><th>人设</th><th>轮次</th><th>综合分</th>{dim_headers}<th>结果</th>
</tr>
{rows}
</table>

<h2>对话记录</h2>
{self._render_conversations_html(batch)}

</body>
</html>"""

        path = self._output_dir / filename
        path.write_text(html, encoding="utf-8")
        logger.info("HTML report saved to %s", path)
        return path

    @staticmethod
    def _render_conversations_html(batch: BatchResult) -> str:
        """渲染对话记录 HTML 片段"""
        import html as _html

        sections = []
        for i, r in enumerate(batch.results, 1):
            turns_html = ""
            for t in r.conversation.turns:
                thought = ""
                if t.user_internal_thought:
                    thought = f'<div class="thought">💭 {_html.escape(t.user_internal_thought)}</div>'
                latency = ""
                if t.bot_latency_ms:
                    latency = f'<span class="latency">({t.bot_latency_ms:.0f}ms)</span>'
                turns_html += (
                    f'<div class="turn">'
                    f'<div class="turn-label">第 {t.turn_number} 轮</div>'
                    f'{thought}'
                    f'<div>🧑 <span class="user-msg">{_html.escape(t.user_message)}</span></div>'
                    f'<div>🤖 <span class="bot-msg">{_html.escape(t.bot_response)}</span>{latency}</div>'
                    f'</div>'
                )
            sections.append(
                f'<details{"  open" if i <= 3 else ""}>'
                f'<summary>{_html.escape(r.scenario.name)} × {_html.escape(r.persona.name)}'
                f' ({len(r.conversation.turns)} 轮)</summary>'
                f'<div class="chat-block">{turns_html}</div>'
                f'</details>'
            )
        return "\n".join(sections)

    @staticmethod
    def _serialize_result(r: RunResult) -> dict:
        return {
            "scenario_id": r.scenario.scenario_id,
            "scenario_name": r.scenario.name,
            "persona_id": r.persona.skeleton.persona_id,
            "persona_name": r.persona.name,
            "turns": len(r.conversation.turns),
            "termination_reason": r.conversation.termination_reason,
            "overall_score": r.evaluation.overall_score,
            "overall_passed": r.evaluation.overall_passed,
            "dimensions": {
                ev.dimension: {"score": ev.score, "passed": ev.passed}
                for ev in r.evaluation.results
            },
            "conversation": [
                {
                    "turn": t.turn_number,
                    "user": t.user_message,
                    "bot": t.bot_response,
                    "thought": t.user_internal_thought,
                    "latency_ms": t.bot_latency_ms,
                }
                for t in r.conversation.turns
            ],
        }
