#!/usr/bin/env python3
"""
fedcli — 多模态 Agent 联邦 CLI 客户端
命令模式 + 对话模式 + 斜杠命令
"""

import click

from federation_sdk import FederationClient


def _get_client(base_url: str = "http://127.0.0.1:8000") -> FederationClient:
    return FederationClient(base_url=base_url)


# ============ 命令模式 ============

@click.group()
@click.version_option(version="1.0.0", prog_name="fedcli")
def cli():
    """多模态 Agent 联邦 CLI — 像聊天一样构建应用。"""


@cli.command()
@click.argument("description")
@click.option("--style", default=None, help="设计风格 (自由描述，如: 极简、赛博朋克、苹果官网风格)")
@click.option("--theme", default=None, help="主题色 (hex 或描述，如: #2563EB、深海蓝)")
@click.option("--output", "output_format", default=None, help="输出格式 (如: html、react、vue)")
@click.option("--ref", "-r", multiple=True, help="参考素材路径")
@click.option("--ref-img", multiple=True, help="图片参考")
@click.option("--ref-web", multiple=True, help="网页参考")
@click.option("--ref-project", multiple=True, help="项目参考")
def new(description, style, theme, output_format, ref, ref_img, ref_web, ref_project):
    """提交新需求。"""
    client = _get_client()
    references = []
    from federation_sdk.references import resolve_reference
    for r in ref:
        references.append(resolve_reference(r))
    for r in ref_img:
        from federation_sdk.models import ImageRef
        references.append(ImageRef(source=r))
    for r in ref_web:
        from federation_sdk.models import WebPageRef
        references.append(WebPageRef(source=r))
    for r in ref_project:
        from federation_sdk.models import ProjectRef
        references.append(ProjectRef(source=r))

    est = client.estimate(description, references=references)
    click.echo()
    click.echo(f"  预估费用: {est.cost_range[0]} ~ {est.cost_range[1]}")
    click.echo(f"  预估 Token: {est.total_tokens:,}")
    click.echo()

    if not click.confirm("确认执行?"):
        click.echo("已取消。")
        return

    result = client.execute(
        description,
        references=references,
        style=style or "",
        theme=theme or "",
        output_format=output_format or "",
    )
    click.echo(f"  状态: {result.status}")
    click.echo(f"  任务 ID: {result.thread_id}")


@cli.command()
@click.argument("description")
def estimate(description):
    """预估 Token 费用（不执行）。"""
    client = _get_client()
    est = client.estimate(description)
    click.echo()
    click.echo(f"  预估费用: {est.cost_range[0]} ~ {est.cost_range[1]}")
    click.echo(f"  预估 Token: {est.total_tokens:,}")
    click.echo(f"  使用 fedcli new ... 提交执行")


@cli.command()
@click.argument("thread_id", required=False)
def status(thread_id):
    """查看任务状态。"""
    client = _get_client()
    if thread_id:
        s = client.status(thread_id)
        click.echo(f"  任务: {s.thread_id}")
        click.echo(f"  状态: {s.status}")
        if s.step:
            click.echo(f"  步骤: {s.step}")
    else:
        workflows = client.workflow.list()
        click.echo(f"  活跃工作流: {workflows.get('workflows', [])}")


@cli.command()
@click.argument("thread_id")
def approve(thread_id):
    """批准等待中的任务。"""
    client = _get_client()
    result = client.approve(thread_id)
    click.echo(f"  已批准: {result.status}")


@cli.command()
@click.argument("thread_id")
@click.option("--reason", default="", help="拒绝原因")
def reject(thread_id, reason):
    """拒绝等待中的任务。"""
    client = _get_client()
    result = client.reject(thread_id, reason=reason)
    click.echo(f"  已拒绝: {result.status}")


@cli.command("list")
def list_cmd():
    """列出所有工作流。"""
    client = _get_client()
    data = client.workflow.list()
    workflows = data.get("workflows", [])
    if not workflows:
        click.echo("  没有活跃的工作流。")
    for w in workflows:
        click.echo(f"  {w.get('thread_id', 'unknown')} — {w.get('status', 'unknown')}")


@cli.command()
def system():
    """系统健康检查。"""
    client = _get_client()
    info = client.health()
    click.echo(f"  版本: {info.version}")
    click.echo(f"  状态: {info.status}")
    click.echo(f"  Agent 数: {info.agents_count}")


# ============ 对话模式 ============

SLASH_COMMANDS: dict[str, str] = {
    "/new": "开始一个新需求",
    "/status": "查看任务状态",
    "/approve": "批准等待中的任务",
    "/reject": "拒绝任务",
    "/list": "列出所有任务",
    "/preview": "打印 preview 文件内容",
    "/estimate": "只预估不执行",
    "/system": "系统健康信息",
    "/help": "显示帮助",
    "/exit": "退出",
}


def _print_banner():
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel.fit(
        "[bold]欢迎使用 Agent 联邦平台[/bold]\n"
        "直接告诉我你想做什么，我会立即执行。\n"
        "输入 [bold]/help[/bold] 查看可用命令  |  输入 [bold]/exit[/bold] 退出",
        border_style="cyan",
    ))


def _show_summary(description: str, client: FederationClient) -> None:
    from rich.console import Console
    from rich.table import Table
    console = Console()

    est = client.estimate(description)

    table = Table(title="确认汇总", border_style="cyan")
    table.add_column("项目", style="dim")
    table.add_column("内容")
    table.add_row("需求", description[:60])
    table.add_row("预估费用", f"{est.cost_range[0]} ~ {est.cost_range[1]}")
    table.add_row("预估 Token", f"{est.total_tokens:,}")
    console.print(table)


def _handle_slash_command(cmd: str, client: FederationClient) -> bool:
    """处理斜杠命令。返回 True 继续对话，False 退出。"""
    parts = cmd.strip().split()
    op = parts[0].lower()

    if op == "/exit":
        from rich.console import Console
        Console().print("[dim]再见！[/dim]")
        return False

    if op == "/help":
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="可用命令")
        table.add_column("命令", style="cyan")
        table.add_column("说明")
        for k, v in SLASH_COMMANDS.items():
            table.add_row(k, v)
        console.print(table)
        return True

    if op == "/system":
        info = client.health()
        click.echo(f"  版本: {info.version}  状态: {info.status}  Agent 数: {info.agents_count}")
        return True

    if op == "/status":
        tid = parts[1] if len(parts) > 1 else None
        if tid:
            s = client.status(tid)
            click.echo(f"  任务: {s.thread_id}  状态: {s.status}")
        else:
            data = client.workflow.list()
            click.echo(f"  工作流: {data.get('workflows', [])}")
        return True

    if op == "/list":
        data = client.workflow.list()
        for w in data.get("workflows", []):
            click.echo(f"  {w.get('thread_id', 'unknown')} — {w.get('status', 'unknown')}")
        return True

    if op == "/estimate":
        desc = " ".join(parts[1:]) if len(parts) > 1 else ""
        if desc:
            est = client.estimate(desc)
            click.echo(f"  预估费用: {est.cost_range[0]} ~ {est.cost_range[1]}  Token: {est.total_tokens:,}")
        return True

    if op == "/preview":
        file = parts[1] if len(parts) > 1 else None
        from pathlib import Path
        preview_dir = Path("preview")
        if file:
            fpath = preview_dir / file
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8")[:1000]
                click.echo(content)
            else:
                click.echo(f"  文件不存在: {fpath}")
        else:
            if preview_dir.exists():
                for f in sorted(preview_dir.iterdir()):
                    click.echo(f"  {f.name}")
            else:
                click.echo("  preview/ 为空")
        return True

    if op == "/approve":
        tid = parts[1] if len(parts) > 1 else ""
        if tid:
            client.approve(tid)
            click.echo(f"  已批准: {tid}")
        return True

    if op == "/reject":
        tid = parts[1] if len(parts) > 1 else ""
        if tid:
            client.reject(tid)
            click.echo(f"  已拒绝: {tid}")
        return True

    if op == "/new":
        # 清空当前状态，开始新需求
        click.echo("  开始新需求，请直接输入描述。")
        return True

    click.echo(f"  未知命令: {op}，输入 /help 查看可用命令")
    return True


def _execute_workflow(description: str, client: FederationClient) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]开始处理...[/bold]\n")

    result = client.execute(description)

    if result.status == "completed":
        console.print("[green]方案已生成！[/green]")
        if result.output and isinstance(result.output, dict) and result.output.get("preview_path"):
            console.print(f"  预览路径: {result.output['preview_path']}")
    elif result.status == "waiting_human":
        console.print("[yellow]任务需要人工审批。[/yellow]")
        console.print(f"  任务 ID: {result.thread_id}")
    else:
        console.print(f"[red]任务失败: {result.error or result.status}[/red]")


@cli.command(name="chat")
@click.option("--base-url", default="http://127.0.0.1:8000", help="Gateway 地址")
def chat_cmd(base_url):
    """启动对话模式。"""
    client = FederationClient(base_url=base_url)
    _print_banner()

    while True:
        try:
            user_input = click.prompt("\nYou", prompt_suffix=": ", default="").strip()
        except (KeyboardInterrupt, EOFError):
            click.echo("\n[dim]再见！[/dim]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            if not _handle_slash_command(user_input, client):
                break
            continue

        # 直接执行: 展示预估 → 确认 → 执行
        _show_summary(user_input, client)

        if click.confirm("\n确认执行?"):
            _execute_workflow(user_input, client)
        else:
            click.echo("  已取消。")


@cli.command()
def interactive():
    """启动对话模式（默认）。"""
    chat_cmd.callback()


def main():
    """入口：无参数 = 对话模式，有参数 = 命令模式。"""
    import sys
    if len(sys.argv) == 1:
        chat_cmd.callback(base_url="http://127.0.0.1:8000")
    else:
        cli()


if __name__ == "__main__":
    main()
