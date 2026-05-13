#!/usr/bin/env python3
"""
fedcli — 多模态 Agent 联邦 CLI 客户端
ChatGPT 对话式 + 命令模式 + 斜杠命令
"""

import click

from federation_sdk import FederationClient


def _get_client(base_url: str = "http://127.0.0.1:8000") -> FederationClient:
    return FederationClient(base_url=base_url)


# ============ 安全提醒面板 ============

def _sandbox_off_warning() -> bool:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel(
        "[bold yellow]⚠ 安全警告：关闭沙盒模式[/bold yellow]\n\n"
        "生成的代码将直接写入本地文件系统。\n"
        "风险：恶意代码访问 / 意外覆盖 / 环境影响\n\n"
        "建议仅在信任环境下关闭。",
        border_style="red",
        title="安全确认",
    ))
    return click.confirm("  确认关闭沙盒？", default=False)


def _search_warning() -> bool:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel(
        "[bold yellow]⚠ 联网搜索提醒[/bold yellow]\n\n"
        "Agent 将联网搜索参考资料，以下信息可能被发送:\n"
        "- 需求描述中的关键词\n"
        "- 设计风格和主题偏好\n"
        "- 不会发送：本地文件路径、个人信息\n\n"
        "搜索提供商: DuckDuckGo（默认，不追踪用户）",
        border_style="yellow",
        title="联网搜索",
    ))
    return click.confirm("  确认允许联网搜索？", default=False)


def _external_ref_warning(source: str) -> bool:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel(
        f"[bold yellow]⚠ 外部参考素材提醒[/bold yellow]\n\n"
        f"将处理以下外部参考:\n- {source}\n\n"
        f"以下信息可能外传:\n- URL / 网页截图和文本内容\n"
        f"- 不会发送: 你的 IP、Cookie、登录状态",
        border_style="yellow",
        title="外部参考",
    ))
    return click.confirm("  确认使用这些参考素材？", default=True)


def _file_access_warning(read_paths: list[str], write_dir: str) -> bool:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    lines = "\n".join(f"  读取: {p}" for p in read_paths)
    lines += f"\n  写入: {write_dir}/"
    console.print(Panel(
        f"[bold]📁 本地文件访问[/bold]\n\n{lines}",
        border_style="cyan",
        title="文件访问",
    ))
    return click.confirm("  是否继续？", default=True)


# ============ 命令模式 ============

@click.group()
@click.version_option(version="1.0.0", prog_name="fedcli")
def cli():
    """多模态 Agent 联邦 CLI — 像聊天一样构建应用。"""


@cli.command()
@click.argument("description")
@click.option("--style", default="modern", help="设计风格")
@click.option("--theme", default=None, help="主题色 (hex 或预设名)")
@click.option("--output", "output_format", default="both", help="输出框架")
@click.option("--sandbox/--no-sandbox", default=True, help="沙盒模式")
@click.option("--search/--no-search", default=None, help="联网搜索", is_flag=True)
@click.option("--ref", "-r", multiple=True, help="参考素材路径")
@click.option("--ref-img", multiple=True, help="图片参考")
@click.option("--ref-web", multiple=True, help="网页参考")
@click.option("--ref-project", multiple=True, help="项目参考")
def new(description, style, theme, output_format, sandbox, search, ref, ref_img, ref_web, ref_project):
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

    est = client.estimate(description, references=references,
                          style=style, output_format=output_format,
                          allow_search=search)
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
        style=style,
        theme=theme,
        output_format=output_format,
        allow_search=search,
        sandbox=sandbox,
    )
    click.echo(f"  状态: {result.status}")
    click.echo(f"  任务 ID: {result.thread_id}")


@cli.command()
@click.argument("description")
@click.option("--style", default="modern")
@click.option("--output", "output_format", default="both")
def estimate(description, style, output_format):
    """预估 Token 费用（不执行）。"""
    client = _get_client()
    est = client.estimate(description, style=style, output_format=output_format)
    click.echo()
    click.echo(f"  预估费用: {est.cost_range[0]} ~ {est.cost_range[1]}")
    click.echo(f"  预估 Token: {est.total_tokens:,}")
    click.echo(f"  置信度: {est.confidence}")
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


# ============ 对话模式引擎 ============

STYLES: dict[str, str] = {
    "modern": "现代 — 圆角卡片、渐变、微阴影",
    "minimal": "极简 — 大量留白、细线条",
    "glassmorphism": "毛玻璃 — 半透明面板、层次感",
    "dark": "暗夜 — 深色背景、荧光色",
    "brutalist": "粗野主义 — 粗边框、撞色",
    "cyberpunk": "赛博朋克 — 霓虹灯效",
    "neumorphism": "新拟态 — 柔和浮雕、内阴影",
    "classic": "经典 — 衬线字体、传统布局",
    "retro": "复古 — 像素字体、高饱和",
    "organic": "自然 — 圆润形状、大地色系",
    "luxury": "奢华 — 金色点缀、暗色质感",
    "playful": "活泼 — 鲜艳色彩、弹跳动画",
}

THEMES: dict[str, str] = {
    "ocean": "海洋蓝 #2563EB",
    "forest": "森林绿 #16A34A",
    "sunset": "日落橙 #EA580C",
    "rose": "玫瑰红 #E11D48",
    "lavender": "薰衣草紫 #7C3AED",
    "midnight": "午夜蓝黑 #1E293B",
    "teal": "青碧 #0D9488",
    "amber": "琥珀金 #D97706",
    "slate": "石板灰 #64748B",
}

OUTPUT_FORMATS: dict[str, str] = {
    "html": "HTML+CSS 纯静态",
    "react": "React 组件化",
    "vue": "Vue 渐进式",
    "flutter": "Flutter 跨平台",
    "both": "全都要",
}

SLASH_COMMANDS: dict[str, str] = {
    "/new": "开始一个新需求",
    "/status": "查看任务状态",
    "/approve": "批准等待中的任务",
    "/reject": "拒绝任务",
    "/list": "列出所有任务",
    "/preview": "打印 preview 文件内容",
    "/estimate": "只预估不执行",
    "/system": "系统健康信息",
    "/style": "重新选择设计风格",
    "/theme": "重新选择主题色",
    "/sandbox": "切换沙盒模式 on/off",
    "/search": "切换联网搜索 on/off",
    "/help": "显示帮助",
    "/exit": "退出",
}


class ConversationState:
    """对话状态：记住用户的选择。"""

    def __init__(self):
        self.style: str = "modern"
        self.theme: str | None = None
        self.output_format: str = "both"
        self.allow_search: bool | None = None
        self.sandbox: bool = True
        self.description: str = ""
        self.references: list = []


def _print_banner():
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel.fit(
        "[bold]欢迎使用 Agent 联邦平台[/bold]\n"
        "直接告诉我你想做什么，我会一步步引导你。\n"
        "输入 [bold]/help[/bold] 查看可用命令  |  输入 [bold]/exit[/bold] 退出",
        border_style="cyan",
    ))


def _ask_style(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]1) 设计风格选哪种？[/bold]\n")
    for key, desc in STYLES.items():
        marker = " [cyan](当前)[/cyan]" if key == state.style else ""
        console.print(f"  {key:<18} {desc}{marker}")
    console.print(f"\n  [dim]直接输入风格名，回车使用当前: [{state.style}][/dim]")


def _ask_theme(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]2) 主题色选哪种？[/bold]\n")
    for key, desc in THEMES.items():
        console.print(f"  {key:<12} {desc}")
    console.print("  custom       任意 hex 色值")
    console.print("\n  [dim]回车跳过[/dim]")


def _ask_output_format(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]3) 输出什么框架？[/bold]\n")
    for key, desc in OUTPUT_FORMATS.items():
        marker = " [cyan](当前)[/cyan]" if key == state.output_format else ""
        console.print(f"  {key:<12} {desc}{marker}")
    console.print(f"\n  [dim]回车使用当前: [{state.output_format}][/dim]")


def _ask_search(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]4) 需要联网搜索吗？[/bold]")
    console.print("  [yellow]开启后需求关键词会发送到搜索引擎。[/yellow]")
    default = "否" if state.allow_search is None else ("是" if state.allow_search else "否")
    console.print(f"\n  [dim][{default}] [/dim]")


def _ask_sandbox(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]5) 沙盒模式？[/bold]")
    console.print("  开启 = 隔离环境运行，安全。关闭 = 直接写文件。")
    default = "开启" if state.sandbox else "关闭"
    console.print(f"\n  [dim][{default}] [/dim]")


def _show_summary(state: ConversationState, client: FederationClient) -> None:
    from rich.console import Console
    from rich.table import Table
    console = Console()

    est = client.estimate(state.description, references=state.references,
                          style=state.style, output_format=state.output_format,
                          allow_search=state.allow_search)

    table = Table(title="确认汇总", border_style="cyan")
    table.add_column("项目", style="dim")
    table.add_column("选择")
    table.add_row("需求", state.description[:40])
    table.add_row("风格", f"{state.style} + {state.theme or '默认'}")
    table.add_row("输出", state.output_format)
    table.add_row("搜索", "开" if state.allow_search else "关")
    table.add_row("沙盒", "开" if state.sandbox else "关")
    table.add_row("预估费用", f"{est.cost_range[0]} ~ {est.cost_range[1]}")
    table.add_row("预估 Token", f"{est.total_tokens:,}")
    console.print(table)


def _handle_slash_command(cmd: str, state: ConversationState, client: FederationClient) -> bool:
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

    if op == "/style":
        _ask_style(state)
        return True

    if op == "/theme":
        _ask_theme(state)
        return True

    if op == "/sandbox":
        val = parts[1] if len(parts) > 1 else ""
        if val.lower() in ("on", "true", "1"):
            state.sandbox = True
            click.echo("  沙盒模式: 开启")
        elif val.lower() in ("off", "false", "0"):
            if _sandbox_off_warning():
                state.sandbox = False
                click.echo("  沙盒模式: 关闭")
        else:
            click.echo(f"  沙盒模式: {'开' if state.sandbox else '关'}")
        return True

    if op == "/search":
        val = parts[1] if len(parts) > 1 else ""
        if val.lower() in ("on", "true", "1"):
            if _search_warning():
                state.allow_search = True
                click.echo("  联网搜索: 开启")
        elif val.lower() in ("off", "false", "0"):
            state.allow_search = False
            click.echo("  联网搜索: 关闭")
        else:
            click.echo(f"  联网搜索: {'开' if state.allow_search else '关'}")
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
        desc = " ".join(parts[1:]) if len(parts) > 1 else state.description
        est = client.estimate(desc, style=state.style, output_format=state.output_format)
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

    click.echo(f"  未知命令: {op}，输入 /help 查看可用命令")
    return True


def _execute_workflow(state: ConversationState, client: FederationClient) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]开始处理...[/bold]\n")

    result = client.execute(
        state.description,
        references=state.references,
        style=state.style,
        theme=state.theme,
        output_format=state.output_format,
        allow_search=state.allow_search,
        sandbox=state.sandbox,
    )

    if result.status == "completed":
        console.print("[green]方案已生成！[/green]")
        if result.preview_path:
            console.print(f"  预览路径: {result.preview_path}")
    elif result.status == "waiting_human":
        console.print("[yellow]任务需要人工审批。[/yellow]")
        console.print(f"  任务 ID: {result.thread_id}")
    else:
        console.print(f"[red]任务失败: {result.error or result.status}[/red]")


@cli.command(name="chat")
@click.option("--base-url", default="http://127.0.0.1:8000", help="Gateway 地址")
def chat_cmd(base_url):
    """启动 ChatGPT 式对话模式。"""
    client = FederationClient(base_url=base_url)
    state = ConversationState()
    _print_banner()

    phase = "describe"

    while True:
        try:
            user_input = click.prompt("\nYou", prompt_suffix=": ", default="").strip()
        except (KeyboardInterrupt, EOFError):
            click.echo("\n[dim]再见！[/dim]")
            break

        if not user_input:
            if phase == "style":
                _ask_style(state)
            elif phase == "theme":
                _ask_theme(state)
            elif phase == "output":
                _ask_output_format(state)
            elif phase == "search":
                _ask_search(state)
            elif phase == "sandbox":
                _ask_sandbox(state)
            elif phase == "confirm":
                _show_summary(state, client)
            continue

        if user_input.startswith("/"):
            if not _handle_slash_command(user_input, state, client):
                break
            continue

        text_lower = user_input.lower()

        if phase == "describe":
            state.description = user_input
            click.echo("\n  好的！我来理解一下你的需求。")
            _ask_style(state)
            phase = "style"

        elif phase == "style":
            matched_style = None
            for key in STYLES:
                if key in text_lower:
                    matched_style = key
                    break
            if matched_style:
                state.style = matched_style
                click.echo(f"  [green]✓ 风格: {STYLES[matched_style]}[/green]")

            matched_theme = None
            for key in THEMES:
                if key in text_lower:
                    matched_theme = key
                    break
            if matched_theme:
                state.theme = matched_theme
                click.echo(f"  [green]✓ 主题: {THEMES[matched_theme]}[/green]")
            elif user_input.startswith("#"):
                state.theme = user_input.strip()
                click.echo(f"  [green]✓ 自定义主题: {state.theme}[/green]")

            if not matched_style and not matched_theme:
                state.style = user_input.strip()
                click.echo(f"  [green]✓ 风格: {state.style}[/green]")

            _ask_output_format(state)
            phase = "output"

        elif phase == "output":
            matched = None
            for key in OUTPUT_FORMATS:
                if key in text_lower:
                    matched = key
                    break
            if matched:
                state.output_format = matched
            elif "html" in text_lower:
                state.output_format = "html"
            elif "react" in text_lower:
                state.output_format = "react"
            elif "vue" in text_lower:
                state.output_format = "vue"
            elif "flutter" in text_lower:
                state.output_format = "flutter"
            elif "全要" in user_input or "both" in text_lower:
                state.output_format = "both"
            else:
                state.output_format = user_input.strip()
            click.echo(f"  [green]✓ 输出框架: {state.output_format}[/green]")
            _ask_search(state)
            phase = "search"

        elif phase == "search":
            if any(w in text_lower for w in ("是", "开", "yes", "y", "要", "可以")):
                if _search_warning():
                    state.allow_search = True
            elif any(w in text_lower for w in ("否", "关", "no", "n", "不要", "不用")):
                state.allow_search = False
            click.echo(f"  [green]✓ 联网搜索: {'开' if state.allow_search else '关'}[/green]")
            _ask_sandbox(state)
            phase = "sandbox"

        elif phase == "sandbox":
            if any(w in text_lower for w in ("开", "是", "yes", "y", "安全")):
                state.sandbox = True
            elif any(w in text_lower for w in ("关", "否", "no", "n", "快")):
                if _sandbox_off_warning():
                    state.sandbox = False
            click.echo(f"  [green]✓ 沙盒模式: {'开' if state.sandbox else '关'}[/green]")
            _show_summary(state, client)
            phase = "confirm"

        elif phase == "confirm":
            if text_lower in ("y", "yes", "是", "确认", "开始", "ok", "好"):
                _execute_workflow(state, client)
                state = ConversationState()
                phase = "describe"
            elif text_lower in ("n", "no", "否", "取消", "不"):
                click.echo("  已取消。输入新需求开始。")
                state = ConversationState()
                phase = "describe"
            else:
                click.echo("  请输入 Y/N，或 /help 查看命令")


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
