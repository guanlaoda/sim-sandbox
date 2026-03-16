"""CLI 入口 — 基于 Typer 的命令行界面"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="sandbox",
    help="对话大模型机器人仿真沙盒框架",
    add_completion=False,
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# -------------------------------------------------------------------
# run — 执行仿真
# -------------------------------------------------------------------

@app.command()
def run(
    config: str = typer.Option("config/default.yaml", "--config", "-c", help="配置文件路径"),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="场景文件或目录"),
    persona_count: int = typer.Option(3, "--personas", "-p", help="生成 persona 数量"),
    output: str = typer.Option("output", "--output", "-o", help="输出目录"),
    report_format: str = typer.Option("html", "--format", "-f", help="报告格式 (html/json/md)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
) -> None:
    """运行仿真测试"""
    _setup_logging(verbose)

    from .adapters.mock_adapter import MockBotAdapter
    from .config import SandboxConfig
    from .orchestrator.runner import SimulationRunner
    from .storage.database import Database
    from .storage.reporter import Reporter

    # 加载配置
    config_path = Path(config)
    if config_path.exists():
        cfg = SandboxConfig.load(config)
    else:
        console.print(f"[yellow]配置文件不存在: {config}, 使用默认配置[/yellow]")
        cfg = SandboxConfig()

    if persona_count:
        cfg.persona.count = persona_count

    # 创建 bot adapter
    adapter = MockBotAdapter(responses=["您好，请问有什么可以帮您？", "好的，已为您处理。"])

    runner = SimulationRunner(config=cfg, bot_adapter=adapter)

    # 覆盖场景目录
    if scenario:
        cfg.simulation.scenario_dirs = [scenario]

    # 执行
    console.print("[bold green]🚀 开始仿真运行...[/bold green]")
    batch = asyncio.run(runner.run_from_config())

    # 输出结果表格
    table = Table(title="仿真结果")
    table.add_column("场景", style="cyan")
    table.add_column("人设", style="magenta")
    table.add_column("轮次", justify="right")
    table.add_column("综合分", justify="right")
    table.add_column("结果")

    for r in batch.results:
        status = "[green]✅ PASS[/green]" if r.evaluation.overall_passed else "[red]❌ FAIL[/red]"
        table.add_row(
            r.scenario.name,
            r.persona.name,
            str(len(r.conversation.turns)),
            f"{r.evaluation.overall_score:.3f}",
            status,
        )

    console.print(table)
    console.print(
        f"\n总计: {batch.total} | 通过: {batch.passed} | 失败: {batch.failed} "
        f"| 通过率: {batch.pass_rate:.1%}"
    )

    # 生成报告
    reporter = Reporter(output_dir=f"{output}/reports")
    if report_format == "html":
        path = reporter.generate_html(batch)
    elif report_format == "json":
        path = reporter.generate_json(batch)
    else:
        path = reporter.generate_markdown(batch)

    # 持久化到数据库
    db = Database(cfg.database_path)
    db.connect()
    for r in batch.results:
        db.save_conversation(r.conversation)
        db.save_evaluation(r.evaluation)
    db.close()

    console.print(f"\n[bold]报告已保存: {path}[/bold]")


# -------------------------------------------------------------------
# validate — 校验场景/配置
# -------------------------------------------------------------------

@app.command()
def validate(
    path: str = typer.Argument(..., help="要校验的文件或目录路径"),
    type_: str = typer.Option("scenario", "--type", "-t", help="类型: scenario/config/persona"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """校验场景文件或配置"""
    _setup_logging(verbose)

    target = Path(path)
    if not target.exists():
        console.print(f"[red]路径不存在: {path}[/red]")
        raise typer.Exit(1)

    if type_ == "scenario":
        from .scenario.loader import ScenarioLoader

        if target.is_dir():
            loader = ScenarioLoader(scenarios_dir=str(target))
            results = loader.validate_all()
        else:
            loader = ScenarioLoader(scenarios_dir=str(target.parent))
            try:
                loader.load_file(str(target))
                results = [{"file": str(target), "valid": True}]
            except Exception as exc:
                results = [{"file": str(target), "valid": False, "error": str(exc)}]

        valid = [r for r in results if r["valid"]]
        invalid = [r for r in results if not r["valid"]]
        console.print(f"校验了 {len(results)} 个场景文件，通过 {len(valid)} 个")
        if invalid:
            for r in invalid:
                console.print(f"[red]  FAIL {r['file']}: {r.get('error', '未知错误')}[/red]")
            raise typer.Exit(1)
        else:
            console.print("[green]全部校验通过！[/green]")

    elif type_ == "config":
        from .config import SandboxConfig

        try:
            cfg = SandboxConfig.load(str(target))
            console.print("[green]配置文件解析成功[/green]")
        except Exception as e:
            console.print(f"[red]配置解析失败: {e}[/red]")
            raise typer.Exit(1)

    else:
        console.print(f"[red]不支持的类型: {type_}[/red]")
        raise typer.Exit(1)


# -------------------------------------------------------------------
# persona — 生成 persona
# -------------------------------------------------------------------

@app.command()
def persona(
    count: int = typer.Option(1, "--count", "-n", help="生成数量"),
    output: str = typer.Option("output/personas", "--output", "-o", help="输出目录"),
    seed: Optional[int] = typer.Option(None, "--seed", help="随机种子"),
    config: str = typer.Option("config/default.yaml", "--config", "-c", help="配置文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """生成用户画像"""
    _setup_logging(verbose)

    from .config import PersonaGenerationConfig, SandboxConfig
    from .persona.generator import PersonaGenerator

    config_path = Path(config)
    if config_path.exists():
        cfg = SandboxConfig.load(config)
        persona_cfg = cfg.persona
    else:
        persona_cfg = PersonaGenerationConfig()

    if seed is not None:
        persona_cfg.seed = seed

    gen = PersonaGenerator(config=persona_cfg, project_root=Path.cwd())
    out_path = Path(output)
    out_path.mkdir(parents=True, exist_ok=True)

    personas = gen.generate(count=count)
    for p in personas:
        fpath = out_path / f"{p.skeleton.persona_id}.json"
        fpath.write_text(p.model_dump_json(indent=2), encoding="utf-8")
        console.print(
            f"[green]生成 persona: {p.name}[/green] "
            f"({p.skeleton.communication_style.value}, "
            f"tech={p.skeleton.tech_literacy:.2f}, "
            f"patience={p.skeleton.patience_level:.2f})"
        )

    console.print(f"\n共生成 {count} 个用户画像 → {out_path}")


# -------------------------------------------------------------------
# report — 查看历史报告
# -------------------------------------------------------------------

@app.command()
def report(
    db_path: str = typer.Option("output/sandbox.db", "--db", help="数据库路径"),
    scenario_id: Optional[str] = typer.Option(None, "--scenario", "-s"),
    limit: int = typer.Option(20, "--limit", "-n"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """查看历史评测结果"""
    _setup_logging(verbose)

    from .storage.database import Database

    db = Database(db_path)
    db.connect()

    stats = db.get_summary_stats()
    console.print(f"\n[bold]数据库统计:[/bold]")
    console.print(f"  对话记录: {stats['total_conversations']}")
    console.print(f"  评测记录: {stats['total_evaluations']}")
    console.print(f"  平均分:   {stats['avg_score']:.3f}")
    console.print(f"  通过率:   {stats['pass_rate']:.1%}")

    evals = db.list_evaluations(scenario_id=scenario_id, limit=limit)
    if evals:
        table = Table(title=f"最近 {len(evals)} 条评测")
        table.add_column("Record ID")
        table.add_column("Scenario")
        table.add_column("Score", justify="right")
        table.add_column("Passed")
        table.add_column("Time")

        for e in evals:
            status = "[green]✅[/green]" if e.get("overall_passed") else "[red]❌[/red]"
            table.add_row(
                e.get("record_id", ""),
                e.get("scenario_id", ""),
                f"{e.get('overall_score', 0):.3f}",
                status,
                e.get("created_at", ""),
            )
        console.print(table)

    db.close()


# -------------------------------------------------------------------
# log — 查看对话记录详情
# -------------------------------------------------------------------

@app.command()
def log(
    record_id: Optional[str] = typer.Argument(None, help="对话记录 ID（不传则列出所有记录）"),
    db_path: str = typer.Option("output/sandbox.db", "--db", help="数据库路径"),
    scenario_id: Optional[str] = typer.Option(None, "--scenario", "-s", help="按场景筛选"),
    limit: int = typer.Option(20, "--limit", "-n", help="列表条数"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
) -> None:
    """查看对话记录和对练日志

    不传 record_id 时列出所有对话记录；传入 record_id 时显示该场对话的逐轮详情。
    """
    _setup_logging(verbose)

    from .storage.database import Database

    db = Database(db_path)
    db.connect()

    if record_id is None:
        # ---- 列表模式 ----
        convos = db.list_conversations(scenario_id=scenario_id, limit=limit)
        if not convos:
            console.print("[yellow]暂无对话记录[/yellow]")
            db.close()
            return

        table = Table(title=f"对话记录（共 {len(convos)} 条）")
        table.add_column("Record ID", style="cyan")
        table.add_column("Scenario")
        table.add_column("Persona")
        table.add_column("终止原因")
        table.add_column("延迟(ms)", justify="right")
        table.add_column("时间")

        for c in convos:
            table.add_row(
                c.get("record_id", "")[:12],
                c.get("scenario_id", ""),
                c.get("persona_id", "")[:16],
                c.get("termination_reason", "") or "",
                f"{c.get('total_bot_latency_ms', 0) or 0:.0f}",
                c.get("created_at", ""),
            )
        console.print(table)
        console.print("\n[dim]提示: sandbox log <record_id> 查看某条对话详情[/dim]")
    else:
        # ---- 详情模式 ----
        conv = db.get_conversation(record_id)
        if conv is None:
            # 支持短 ID 前缀匹配
            convos = db.list_conversations(limit=500)
            matched = [c for c in convos if c["record_id"].startswith(record_id)]
            if len(matched) == 1:
                conv = db.get_conversation(matched[0]["record_id"])
            elif len(matched) > 1:
                console.print(f"[yellow]多条记录匹配前缀 '{record_id}'，请提供更长的 ID[/yellow]")
                db.close()
                return
            else:
                console.print(f"[red]未找到记录: {record_id}[/red]")
                db.close()
                return

        console.print(f"\n[bold]对话记录 {conv['record_id']}[/bold]")
        console.print(f"  场景:     {conv.get('scenario_id', '')}")
        console.print(f"  人设:     {conv.get('persona_id', '')}")
        console.print(f"  终止原因: {conv.get('termination_reason', '')}")
        console.print(f"  总延迟:   {conv.get('total_bot_latency_ms', 0) or 0:.0f} ms")
        console.print(f"  开始:     {conv.get('started_at', '')}")
        console.print(f"  结束:     {conv.get('finished_at', '')}")
        console.print()

        turns = conv.get("turns", [])
        for t in turns:
            turn_no = t.get("turn_number", "?")
            user_msg = t.get("user_message", "")
            bot_resp = t.get("bot_response", "")
            latency = t.get("bot_latency_ms", 0)

            console.print(f"[bold cyan]═══ 第 {turn_no} 轮 ═══[/bold cyan]")
            if t.get("user_internal_thought"):
                console.print(f"  [dim]💭 内心: {t['user_internal_thought']}[/dim]")
            console.print(f"  [green]👤 用户:[/green] {user_msg}")
            console.print(f"  [blue]🤖 机器人:[/blue] {bot_resp}")
            if latency:
                console.print(f"  [dim]⏱  {latency:.0f}ms[/dim]")
            if t.get("bot_tool_calls"):
                for tc in t["bot_tool_calls"]:
                    console.print(f"  [yellow]🔧 工具调用: {tc.get('tool_name', '')}({tc.get('params', {})})[/yellow]")
            console.print()

        console.print(f"[dim]共 {len(turns)} 轮对话[/dim]")

    db.close()


# -------------------------------------------------------------------
# chat — 交互式人机对练
# -------------------------------------------------------------------

@app.command()
def chat(
    scenario_path: Optional[str] = typer.Option(None, "--scenario", "-s", help="场景文件路径"),
    config: str = typer.Option("config/default.yaml", "--config", "-c", help="配置文件路径"),
    seed: Optional[int] = typer.Option(None, "--seed", help="随机种子"),
    save: bool = typer.Option(True, "--save/--no-save", help="是否保存到数据库"),
    strategy_name: str = typer.Option("llm", "--strategy", help="对话策略: llm | rule"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
) -> None:
    """交互式对练：你扮演 Bot，与 AI 虚拟用户对话

    框架会生成一个用户画像并加载场景，由 AI 扮演用户发起对话。
    你在终端输入 Bot 的回复。输入 /quit 可提前结束。
    默认使用 LLM 驱动的角色扮演策略 (需要 DEEPSEEK_API_KEY)。
    """
    _setup_logging(verbose)

    from .adapters.human_adapter import HumanBotAdapter
    from .config import SandboxConfig
    from .evaluators.pipeline import EvaluationPipeline
    from .models.scenario import Scenario
    from .persona.generator import PersonaGenerator
    from .scenario.loader import ScenarioLoader
    from .simulator.engine import DialogSimulator
    from .simulator.strategies import LLMAssistedStrategy, RuleBasedStrategy
    from .simulator.termination import TerminationChecker
    from .storage.database import Database

    # 加载配置
    config_path = Path(config)
    cfg = SandboxConfig.load(config) if config_path.exists() else SandboxConfig()

    # 加载场景
    if scenario_path:
        loader = ScenarioLoader()
        scenario = loader.load_file(scenario_path)
    else:
        # 默认加载第一个场景
        for d in cfg.simulation.scenario_dirs:
            loader = ScenarioLoader(scenarios_dir=d)
            scenarios = loader.load_directory()
            if scenarios:
                scenario = scenarios[0]
                break
        else:
            console.print("[red]未找到场景文件，请用 --scenario 指定[/red]")
            raise typer.Exit(1)

    # 生成 persona
    if seed is not None:
        cfg.persona.seed = seed
    gen = PersonaGenerator(config=cfg.persona, project_root=Path.cwd())
    persona = gen.generate(count=1)[0]

    # 显示对练信息
    console.print()
    console.print("[bold]=" * 50)
    console.print("[bold magenta]🎮 交互式对练模式[/bold magenta]")
    console.print("[bold]=" * 50)
    console.print(f"  📝 场景: [cyan]{scenario.name}[/cyan]")
    console.print(f"  🎯 用户目标: {scenario.user_goal.primary_intent}")
    console.print(f"  👤 画像: [green]{persona.name}[/green]")
    console.print(f"     性格: {persona.skeleton.communication_style.value}")
    console.print(f"     耐心: {persona.skeleton.patience_level:.2f}")
    console.print(f"     意图清晰度: {persona.skeleton.intent_clarity:.2f}")
    if scenario.user_goal.hidden_constraints:
        console.print("  🔒 隐含约束 (你看不到的):")
        for hc in scenario.user_goal.hidden_constraints:
            console.print(f"     - [dim]{hc}[/dim]")
    console.print("[bold]=" * 50)
    console.print("[dim]提示: 你扮演 Bot，AI 扮演用户。输入 /quit 结束对话。[/dim]")
    console.print()

    # 构建模拟器组件
    adapter = _HumanBotAdapterWithQuit()
    if strategy_name == "rule":
        strategy = RuleBasedStrategy(seed=seed)
    else:
        # 默认使用 LLM 策略
        import openai
        api_key = cfg.llm.resolve_api_key()
        if not api_key:
            console.print("[red]未配置 DEEPSEEK_API_KEY 环境变量，无法使用 LLM 策略[/red]")
            console.print("[dim]提示: export DEEPSEEK_API_KEY=your_key 或者用 --strategy rule 使用规则策略[/dim]")
            raise typer.Exit(1)
        llm_client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=cfg.llm.api_base,
        )
        strategy = LLMAssistedStrategy(
            llm_client=llm_client,
            model=cfg.llm.default_model,
        )
    termination = TerminationChecker(
        max_turns=scenario.constraints.max_turns,
        timeout_seconds=scenario.constraints.max_duration_seconds,
    )
    simulator = DialogSimulator(
        bot_adapter=adapter,
        strategy=strategy,
        termination=termination,
    )

    # 运行对话
    conversation = asyncio.run(simulator.run(persona, scenario))

    # 对话结束
    console.print()
    console.print("[bold]=" * 50)
    console.print(f"[bold]对话结束！共 {len(conversation.turns)} 轮[/bold]")
    console.print(f"  终止原因: {conversation.termination_reason}")

    # 评测
    pipeline = EvaluationPipeline()
    evaluation = asyncio.run(pipeline.evaluate(conversation, scenario))

    console.print()
    console.print("[bold]📊 评测结果:[/bold]")
    table = Table()
    table.add_column("维度", style="cyan")
    table.add_column("得分", justify="right")
    table.add_column("通过")
    for r in evaluation.results:
        status = "[green]✅[/green]" if r.passed else "[red]❌[/red]"
        table.add_row(r.dimension, f"{r.score:.3f}", status)
    table.add_row("[bold]综合[/bold]", f"[bold]{evaluation.overall_score:.3f}[/bold]",
                  "[green]✅ PASS[/green]" if evaluation.overall_passed else "[red]❌ FAIL[/red]")
    console.print(table)

    # 保存
    if save:
        db = Database(cfg.database_path)
        db.connect()
        db.save_conversation(conversation)
        db.save_evaluation(evaluation)
        db.close()
        console.print(f"\n[dim]已保存到数据库，sandbox log {conversation.record_id[:8]} 查看记录[/dim]")


class _HumanBotAdapterWithQuit:
    """包装一层，支持 /quit 退出"""

    def __init__(self) -> None:
        from .adapters.human_adapter import HumanBotAdapter
        self._inner = HumanBotAdapter(show_user_message=True)
        self._quit = False

    @property
    def quit_requested(self) -> bool:
        return self._quit

    async def send_message(
        self,
        session_id: str,
        message: str,
        context: list | None = None,
    ) -> "BotResponse":
        from .adapters.base import BotResponse

        resp = await self._inner.send_message(session_id, message, context)
        if resp.text.strip().lower() in ("/quit", "/exit", "/q"):
            self._quit = True
            return BotResponse(text="", latency_ms=0, error="user_quit")
        return resp

    async def reset_session(self, session_id: str) -> None:
        await self._inner.reset_session(session_id)

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        pass


if __name__ == "__main__":
    app()
