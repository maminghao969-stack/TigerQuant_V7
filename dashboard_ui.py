import time
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text

console = Console()

# ================= 1. 生成各个区块的内容 =================

def make_header():
    """顶部：账户概况"""
    header_text = Text()
    header_text.append(" 💼 总资产: ", style="bold white")
    header_text.append("$305.56", style="bold cyan")
    header_text.append("   |   💵 可用资金: ", style="bold white")
    header_text.append("$0.04", style="bold green")
    header_text.append("   |   📊 持仓市值: ", style="bold white")
    header_text.append("$305.52", style="bold yellow")
    return Panel(header_text, title="模拟盘账户概况 (Paper Trading)", title_align="center", border_style="cyan")

def make_portfolio():
    """左上：实时持仓"""
    table = Table(expand=True, box=None)
    table.add_column("股票", style="bold blue")
    table.add_column("持仓", justify="right")
    table.add_column("现价", justify="right")
    table.add_column("盈亏", justify="right")

    # 模拟数据
    table.add_row("AAPL", "0.17703", "280.07", "[green]+8.93%[/green]")
    table.add_row("NVDA", "0.46686", "198.12", "[green]+9.59%[/green]")
    table.add_row("PLTR", "0.14886", "144.41", "[red]-8.49%[/red]")
    table.add_row("TSLA", "0.36272", "391.34", "[red]-12.49%[/red]")
    
    return Panel(table, title="实时持仓库 (Portfolio)", border_style="blue")

def make_risk_engine():
    """左下：风控引擎"""
    table = Table(expand=True, box=None, show_header=True)
    table.add_column("引擎参数", style="white")
    table.add_column("当前设定", justify="right", style="cyan")

    table.add_row("护仓白名单", "AAPL, NVDA, TSLA, PLTR")
    table.add_row("交易池容量", "20 标的")
    table.add_row("单股最大仓位", "20.0%")
    table.add_row("止盈 / 止损线", "[green]+8.0%[/green] / [red]-3.0%[/red]")
    table.add_row("执行模式", "[yellow]官方模拟盘 (真实下单中 🚀)[/yellow]")

    return Panel(table, title="风控引擎 (Risk Engine)", border_style="yellow")

def make_scanner():
    """右侧：量化雷达"""
    table = Table(expand=True, header_style="bold magenta")
    table.add_column("标的", style="bold blue")
    table.add_column("量化信号", justify="center")
    table.add_column("多因子综合评分", justify="right")
    table.add_column("最新报价", justify="right")

    # 模拟数据
    stocks = [
        ("AAPL", "HOLD", "20", "$280.14"), ("MSFT", "HOLD", "0", "$414.44"),
        ("AMZN", "HOLD", "0", "$268.26"), ("TSLA", "HOLD", "0", "$390.82"),
        ("NVDA", "HOLD", "0", "$198.45"), ("GOOG", "HOLD", "-20", "$383.22"),
        ("META", "HOLD", "0", "$608.75"), ("AMD", "HOLD", "0", "$360.54"),
        ("INTC", "HOLD", "-20", "$99.62"), ("TSM", "HOLD", "20", "$397.67"),
    ]
    for sym, sig, score, price in stocks:
        table.add_row(sym, sig, score, price)

    return Panel(table, title="量化扫描雷达 (Alpha Scanner)", border_style="magenta")

def make_logs():
    """底部：系统日志"""
    now = datetime.now().strftime("%H:%M:%S")
    log_text = (
        f"[[cyan]{now}[/cyan]] ✅ [bold green]核心交易引擎连接成功 (实盘模式)[/bold green]\n"
        f"[[cyan]{now}[/cyan]] 📡 建立安全通道，拉取云端账户数据...\n"
        f"[[cyan]{now}[/cyan]] ⚡ 启动多因子引擎，正在测算 20 只核心标的...\n"
        f"[[cyan]{now}[/cyan]] ⏳ 扫描完成，防拥堵熔断 60 秒"
    )
    return Panel(log_text, title="系统底层日志 (Core Logs)", border_style="white")

# ================= 2. 构建整体布局 (Layout) =================
def generate_layout():
    layout = Layout()

    # 1. 切分上中下三块
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=8)
    )

    # 2. 把中间部分切分成左右两块
    layout["main"].split_row(
        Layout(name="left", ratio=4),  # 左侧占4份
        Layout(name="right", ratio=6)  # 右侧占6份，雷达表更宽一点
    )

    # 3. 把左侧再切分成上下两块 (持仓和风控)
    layout["left"].split_column(
        Layout(name="portfolio", ratio=3),
        Layout(name="risk", ratio=2)
    )

    # 4. 将生成的面板填入对应的区块
    layout["header"].update(make_header())
    layout["portfolio"].update(make_portfolio())
    layout["risk"].update(make_risk_engine())
    layout["right"].update(make_scanner())
    layout["footer"].update(make_logs())

    return layout

# ================= 3. 运行引擎 =================
def main():
    # 模拟刷新动画
    with Live(generate_layout(), refresh_per_second=1, screen=True) as live:
        try:
            while True:
                # 在真实代码中，这里会去调用老虎 API 更新数据
                # live.update(generate_layout())
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[bold red]终端已关闭。[/bold red]")

if __name__ == "__main__":
    main()