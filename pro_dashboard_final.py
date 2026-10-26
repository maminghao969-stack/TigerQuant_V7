import time
import configparser
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text

# 老虎证券 SDK 导入
from tigeropen.tiger_open_config import TigerOpenClientConfig
from tigeropen.quote.quote_client import QuoteClient
from config import Config  # 导入你的 6 大因子权重

# ================= 1. 初始化配置 =================
cp = configparser.ConfigParser()
cp.read('config.ini', encoding='utf-8')

TIGER_ID = cp.get('TIGER_CONFIG', 'tiger_id')
ACCOUNT_ID = cp.get('TIGER_CONFIG', 'account_id')
KEY_PATH = cp.get('TIGER_CONFIG', 'key_path')
SANDBOX = cp.getboolean('TIGER_CONFIG', 'sandbox')

# 你想监控的 20 只股票 (现在可以填满 20 个了)
WATCH_LIST = ['AAPL', 'NVDA', 'TSLA', 'PLTR', 'AMD', 'MSFT', 'AMZN', 'GOOG', 'META', 'NFLX']
GLOBAL_DATA = {} # 用于存放实时的行情数据

# ================= 2. 逻辑引擎 =================

def get_real_data(quote_client):
    """从老虎 API 获取真实数据"""
    try:
        # 批量获取快照
        quotes = quote_client.get_stock_briefs(WATCH_LIST)
        for _, row in quotes.iterrows():
            symbol = row['symbol']
            price = row['latest_price']
            # 这里调用你之前的加权算法
            # 为了演示，暂用 71.0 分，你可以接入真正的 main_strategy.py
            score = 71.0 
            GLOBAL_DATA[symbol] = {
                'price': price,
                'score': score,
                'signal': "BUY" if score > 75 else "HOLD"
            }
        return True
    except Exception as e:
        return str(e)

# ================= 3. 动态 UI 组件 =================

def make_header():
    return Panel(
        Text.from_markup(f" 💼 总资产: [bold cyan]$305.56[/] | 💵 可用: [bold green]$0.04[/] | 🛰️ 模式: {'[yellow]模拟[/]' if SANDBOX else '[red]实盘[/]'}"),
        title="账户概况", border_style="cyan"
    )

def make_scanner():
    table = Table(expand=True, border_style="magenta")
    table.add_column("标的", style="bold blue")
    table.add_column("量化信号", justify="center")
    table.add_column("综合评分", justify="right")
    table.add_column("最新报价", justify="right")

    for sym in WATCH_LIST:
        data = GLOBAL_DATA.get(sym, {'price': 0, 'score': 0, 'signal': 'WAIT'})
        color = "green" if data['score'] > 70 else "white"
        table.add_row(sym, data['signal'], f"[{color}]{data['score']}[/]", f"${data['price']}")
    
    return Panel(table, title=f"量化扫描雷达 (已连接 {len(WATCH_LIST)} 标的)", border_style="magenta")

def make_logs(msg="系统运行中..."):
    now = datetime.now().strftime("%H:%M:%S")
    return Panel(f"[{now}] {msg}", title="系统底层日志", border_style="white")

# ================= 4. 布局与运行 =================

def generate_layout(log_msg="数据更新成功"):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=5)
    )
    layout["main"].split_row(
        Layout(Panel("持仓数据计算中...", title="实时持库"), ratio=4),
        Layout(name="right", ratio=6)
    )
    layout["header"].update(make_header())
    layout["right"].update(make_scanner())
    layout["footer"].update(make_logs(log_msg))
    return layout

def main():
    # 初始化 API
    conf = TigerOpenClientConfig(sandbox_debug=SANDBOX)
    conf.tiger_id = TIGER_ID
    conf.private_key = open(KEY_PATH).read()
    qc = QuoteClient(conf)

    with Live(generate_layout("正在建立连接..."), refresh_per_second=1, screen=True) as live:
        while True:
            status = get_real_data(qc)
            msg = "✅ 扫描完成" if status is True else f"❌ 错误: {status}"
            live.update(generate_layout(msg))
            time.sleep(10) # 10秒刷新一次，防止被限流

if __name__ == "__main__":
    main()