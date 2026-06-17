"""CLI 总入口。"""

import typer

from src.cli import analyze, plan, portfolio, update

app = typer.Typer(
    name="climbing",
    help="个人投研研究与追踪分析系统",
    no_args_is_help=True,
)

app.add_typer(update.app, name="update", help="数据更新任务")
app.add_typer(analyze.app, name="analyze", help="个股与组合分析")
app.add_typer(portfolio.app, name="portfolio", help="持仓管理")
app.add_typer(plan.app, name="plan", help="交易计划管理")


@app.command()
def version() -> None:
    """显示版本号。"""
    from src.common.config import settings
    typer.echo(f"Climbing {settings.project_version}")


if __name__ == "__main__":
    app()
