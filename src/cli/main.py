"""CLI 总入口。"""

import typer

from src.cli import analyze, plan, portfolio, update
from src.cli.formatting import OutputFormat

app = typer.Typer(
    name="climbing",
    help="个人投研研究与追踪分析系统",
    no_args_is_help=True,
)

app.add_typer(update.app, name="update", help="数据更新任务")
app.add_typer(analyze.app, name="analyze", help="个股与组合分析")
app.add_typer(portfolio.app, name="portfolio", help="持仓管理")
app.add_typer(plan.app, name="plan", help="交易计划管理")


@app.callback()
def main_callback(
    ctx: typer.Context,
    format: OutputFormat = typer.Option(
        OutputFormat.TEXT,
        "--format",
        help="输出格式：text 为人类可读，json 为 agent 可解析的结构化输出。",
    ),
) -> None:
    """全局选项。"""
    ctx.ensure_object(dict)
    ctx.obj["format"] = format.value


@app.command()
def version(ctx: typer.Context) -> None:
    """显示版本号。"""
    from src.common.config import settings

    message = f"Climbing {settings.project_version}"
    if ctx.obj.get("format") == OutputFormat.JSON.value:
        import json

        typer.echo(json.dumps({"version": settings.project_version}, ensure_ascii=False))
    else:
        typer.echo(message)


if __name__ == "__main__":
    app()
