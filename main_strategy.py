import time
import logging
from datetime import datetime, timedelta
from tigeropen.tiger_open_config import TigerOpenClientConfig 
from tigeropen.trade.trade_client import TradeClient
from tigeropen.quote.quote_client import QuoteClient
from tigeropen.common.util.signature_utils import read_private_key
from tigeropen.common.util.order_utils import limit_order 
import pandas as pd
import numpy as np

from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich import box

# ====================== 【账户与环境配置】 ======================
TIGER_ID = "20158956"                  # 你的真实 Tiger ID（保持不变）
ACCOUNT_ID = "50916350"                # 🎯 目前使用实盘账户 ID (利用实盘稳定通道拉取数据)
PRIVATE_KEY_PATH = "tiger_private_key.pem"
SANDBOX = False                        # 🎯 关闭沙盒，直连实盘稳定服务器 (配合下方安全锁使用)

# ====================== 【策略与风控配置】 ======================
# 🛑 核心护仓白名单：手动买的股票放这里，机器人绝对不会碰！
MANUAL_STOCKS = ["AAPL", "NVDA"]

# 🚀 核心股票池（20只）
STOCK_POOL = [
    "AAPL", "MSFT", "AMZN", "TSLA", "NVDA", "GOOG", "META", 
    "AMD", "INTC", "TSM", "ASML", "AVGO",
    "PLTR", "CRWD", "SNOW", 
    "SPY", "QQQ", "IWM", 
    "BABA", "PDD"
]

MAX_POSITION_PER_STOCK = 0.2    # 单只股票最大允许占用总资金的比例
MAX_TOTAL_POSITION = 0.8        # 账户最大总仓位比例
STOP_LOSS_RATE = -0.03          # 跌破 -3% 止损
TAKE_PROFIT_RATE = 0.08         # 涨过 +8% 止盈
TRADE_INTERVAL = 60             # 雷达扫描间隔（秒）

# ====================== 【系统状态】 ======================
app_state = {
    "account": {"asset": 0.0, "cash": 0.0, "market_value": 0.0},
    "positions": {},
    "scanner": [],
    "logs": []
}

def log_msg(msg, style="white"):
    """日志引擎：同时输出到终端UI和本地文件"""
    time_str = datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{time_str}] {msg}"
    app_state["logs"].append(f"[{style}]{formatted_msg}[/{style}]")
    if len(app_state["logs"]) > 12: 
        app_state["logs"].pop(0)
    with open("quant_trade.log", "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")

def init_tiger_client():
    """初始化老虎 OpenAPI 客户端"""
    try:
        client_config = TigerOpenClientConfig(sandbox_debug=SANDBOX)
        client_config.private_key = read_private_key(PRIVATE_KEY_PATH)
        client_config.tiger_id = TIGER_ID
        client_config.account = ACCOUNT_ID
        
        trade_client = TradeClient(client_config)
        quote_client = QuoteClient(client_config)
        
        trade_client.get_managed_accounts()
        mode_str = "模拟盘模式" if SANDBOX else "实盘模式 (已加物理安全锁)"
        log_msg(f"✅ 核心交易引擎连接成功 ({mode_str})", "green")
        return trade_client, quote_client
    except Exception as e:
        log_msg(f"❌ API连接失败: {str(e)}", "red")
        return None, None

def get_stock_data(quote_client, symbol, days=20):
    """拉取历史K线并计算量化因子"""
    try:
        bars = quote_client.get_bars(symbols=[symbol], period='day', limit=days)
        if bars is None or bars.empty: return None
        df = pd.DataFrame(bars)
        df.rename(columns={'Close':'close', 'High':'high', 'Low':'low', 'Volume':'volume'}, inplace=True)
        for col in ['close', 'high', 'low']: df[col] = df[col].astype(float)
        df['volume'] = df['volume'].astype(int)
        
        # 简单移动平均
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        # MACD
        df['ema12'] = df['close'].ewm(span=12).mean()
        df['ema26'] = df['close'].ewm(span=26).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['signal'] = df['macd'].ewm(span=9).mean()
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        rs = gain.rolling(14).mean() / loss.rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + rs))
        # 布林带
        df['bb_mid'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
        return df
    except Exception as e:
        return None

def generate_trade_signal(stock_data):
    """多因子综合打分引擎"""
    if stock_data is None or len(stock_data) < 20: return "HOLD", 0
    score = 0
    latest, prev = stock_data.iloc[-1], stock_data.iloc[-2]
    
    if latest['ma5'] > latest['ma10'] > latest['ma20']: score += 20
    elif latest['ma5'] < latest['ma10'] < latest['ma20']: score -= 20
    
    if latest['macd'] > latest['signal'] and prev['macd'] <= prev['signal']: score += 20
    elif latest['macd'] < latest['signal'] and prev['macd'] >= prev['signal']: score -= 20
    
    if latest['rsi'] < 30: score += 20
    elif latest['rsi'] > 70: score -= 20
    
    if latest['close'] < latest['bb_lower']: score += 20
    elif latest['close'] > latest['bb_upper']: score -= 20
    
    volume_ma = stock_data['volume'].rolling(5).mean().iloc[-1]
    if latest['volume'] > volume_ma * 1.2 and latest['close'] > latest['ma20']: score += 20
    elif latest['volume'] > volume_ma * 1.2 and latest['close'] < latest['ma20']: score -= 20
    
    if score >= 60: return "BUY", score
    elif score <= -60: return "SELL", score
    return "HOLD", score

def execute_trade(trade_client, symbol, action, qty, price):
    """执行交易模块 (目前带安全锁，仅记录日志，绝不花钱)"""
    try:
        # 🛑 【物理安全锁】：拦截真实的下单请求，转为纸面模拟日志
        log_msg(f"🛑 [策略触发] 意图 {action} | 标的: {symbol} | 数量: {qty:.5f} 股 | 报价: ${price:.2f}", "magenta")
        
        # ⚠️ 未来实盘跑通后，解开以下代码即可真实下单：
        # contract = trade_client.get_contracts(symbol, sec_type='STK')[0]
        # order = limit_order(account=ACCOUNT_ID, contract=contract, action=action, quantity=qty, limit_price=price)
        # trade_client.place_order(order)
        # log_msg(f"✅ 订单已发送: {action} {symbol}", "green")
        
        return True
    except Exception as e:
        log_msg(f"❌ 交易执行失败: {str(e)}", "red")
        return False

# ================= 🚀 UI 布局与渲染 =================
def generate_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=14)
    )
    layout["main"].split_row(
        Layout(name="left_panel", ratio=4),
        Layout(name="right_panel", ratio=6)
    )
    layout["left_panel"].split_column(
        Layout(name="positions", ratio=6),
        Layout(name="risk_status", ratio=4)
    )
    return layout

def update_ui(layout):
    # 1. 顶部栏 (资金信息)
    account_text = f"[bold cyan]📊 总资产 (Total Assets):[/] [bold white]${app_state['account']['asset']:,.2f}[/]   |   " \
                   f"[bold green]💵 可用资金 (Cash):[/] [bold white]${app_state['account']['cash']:,.2f}[/]   |   " \
                   f"[bold yellow]📈 持仓市值 (Market Value):[/] [bold white]${app_state['account']['market_value']:,.2f}[/]"
    layout["header"].update(Panel(account_text, title="[bold]账户核心概况 (Account)[/bold]", border_style="cyan", box=box.HEAVY))

    # 2. 左上角：持仓监控
    pos_table = Table(expand=True, border_style="blue", box=box.SIMPLE_HEAD)
    pos_table.add_column("股票", style="cyan", justify="left")
    pos_table.add_column("持仓", justify="right")
    pos_table.add_column("现价", justify="right")
    pos_table.add_column("盈亏", justify="right")
    
    for sym, p in app_state["positions"].items():
        pnl_val = p['pnl_rate']
        pnl_str = f"[green]+{pnl_val:.2f}%[/]" if pnl_val > 0 else f"[red]{pnl_val:.2f}%[/]"
        # 🛡️ 碎股显示修复：保留 5 位小数，去掉千位分隔符
        pos_table.add_row(sym, f"{p['qty']:.5f}", f"{p['latest_price']:.2f}", pnl_str)
    layout["positions"].update(Panel(pos_table, title="[bold]实时持仓库 (Portfolio)[/bold]", border_style="blue"))

    # 3. 左下角：风控与系统引擎参数
    risk_table = Table(expand=True, border_style="yellow", box=box.MINIMAL)
    risk_table.add_column("引擎参数", style="white")
    risk_table.add_column("当前设定", justify="right")
    risk_table.add_row("护仓白名单", f"[cyan]{', '.join(MANUAL_STOCKS)}[/cyan]")
    risk_table.add_row("交易池容量", f"{len(STOCK_POOL)} 标的")
    risk_table.add_row("单股最大仓位", f"{MAX_POSITION_PER_STOCK*100}%")
    risk_table.add_row("止盈 / 止损线", f"[green]+{TAKE_PROFIT_RATE*100}%[/] / [red]{STOP_LOSS_RATE*100}%[/]")
    risk_table.add_row("执行模式", "[bold blink red]实盘接管中 (本地无损模拟)[/]" if not SANDBOX else "[bold yellow]纸面模拟 (Sandbox)[/]")
    layout["risk_status"].update(Panel(risk_table, title="[bold]风控引擎 (Risk Engine)[/bold]", border_style="yellow"))

    # 4. 右侧：策略扫描雷达
    scan_table = Table(expand=True, border_style="magenta", box=box.SIMPLE_HEAD)
    scan_table.add_column("标的", style="cyan", justify="center")
    scan_table.add_column("量化信号", justify="center")
    scan_table.add_column("多因子综合评分", justify="right")
    scan_table.add_column("最新报价", justify="right")
    
    for item in app_state["scanner"]:
        sig = item['signal']
        sig_str = f"[bold red on white] BUY [/]" if sig == "BUY" else (f"[bold green on white] SELL [/]" if sig == "SELL" else f"[dim white]HOLD[/]")
        score_val = item['score']
        score_str = f"[red]{score_val}[/]" if score_val >= 60 else (f"[green]{score_val}[/]" if score_val <= -60 else f"{score_val}")
        scan_table.add_row(item['symbol'], sig_str, score_str, f"${item['price']:.2f}")
    layout["right_panel"].update(Panel(scan_table, title="[bold]量化扫描雷达 (Alpha Scanner)[/bold]", border_style="magenta"))

    # 5. 底部：系统日志
    log_text = "\n".join(app_state["logs"])
    layout["footer"].update(Panel(log_text, title="[bold]系统底层日志 (Core Logs)[/bold]", border_style="white", box=box.HEAVY))

# ================= 主循环 =================
def main():
    console = Console()
    console.clear()
    
    trade_client, quote_client = init_tiger_client()
    if not trade_client:
        return
        
    layout = generate_layout()
    update_ui(layout)
    
    last_scan_time = 0
    
    # 🎯 修复关键点：去掉了 screen=True 参数，防止全屏接管导致界面卡死或黑屏
    with Live(layout, refresh_per_second=4) as live:
        while True:
            try:
                current_time = time.time()
                
                if current_time - last_scan_time > TRADE_INTERVAL:
                    log_msg("📡 建立安全通道，拉取云端账户数据...", "cyan")
                    update_ui(layout)
                    
                    # 1. 资产解析器
                    assets = trade_client.get_prime_assets()
                    try:
                        total_asset, cash, market_val = 0.0, 0.0, 0.0
                        if hasattr(assets, 'segments') and 'S' in assets.segments:
                            seg = assets.segments['S']
                            total_asset = getattr(seg, 'net_liquidation', 0)
                            cash = getattr(seg, 'cash_available_for_trade', 0)
                            market_val = getattr(seg, 'gross_position_value', 0)
                        elif hasattr(assets, 'summary'):
                            total_asset = getattr(assets.summary, 'net_liquidation', 0)
                            cash = getattr(assets.summary, 'cash', 0)
                            market_val = getattr(assets.summary, 'gross_position_value', 0)
                            
                        app_state["account"]["asset"] = float(total_asset)
                        app_state["account"]["cash"] = float(cash)
                        app_state["account"]["market_value"] = float(market_val)
                    except Exception as e:
                        log_msg(f"⚠️ 资产节点解析警告: {str(e)}", "yellow")

                    # 2. 刷新持仓
                    positions = trade_client.get_positions()
                    app_state["positions"].clear()
                    if positions:
                        for pos in positions:
                            latest_price = float(pos.market_price)
                            market_value = float(getattr(pos, 'market_value', 0))
                            
                            # 🛡️ 终极碎股修复：用 真实市值 / 现价 反推真实持股数
                            if latest_price > 0 and market_value > 0:
                                true_qty = round(market_value / latest_price, 5)
                            else:
                                true_qty = float(pos.quantity)

                            app_state["positions"][pos.contract.symbol] = {
                                "qty": true_qty,
                                "latest_price": latest_price,
                                "pnl_rate": float(pos.unrealized_pnl_percent) * 100
                            }
                    
                    # ==========================================
                    # 🛑 3. 止盈止损检查 (加入白名单拦截)
                    # ==========================================
                    for symbol, pos in app_state["positions"].items():
                        if symbol in MANUAL_STOCKS:  # 白名单拦截！
                            continue
                            
                        pnl_rate = pos['pnl_rate'] / 100
                        qty, price = pos['qty'], pos['latest_price']
                        
                        if pnl_rate <= STOP_LOSS_RATE or pnl_rate >= TAKE_PROFIT_RATE:
                            execute_trade(trade_client, symbol, "SELL", qty, price)

                    # ==========================================
                    # ⚡ 4. 启动多因子引擎扫盘
                    # ==========================================
                    log_msg(f"⚡ 启动多因子引擎，正在测算 {len(STOCK_POOL)} 只核心标的...", "yellow")
                    update_ui(layout) 
                    
                    app_state["scanner"].clear()
                    for symbol in STOCK_POOL:
                        stock_data = get_stock_data(quote_client, symbol)
                        signal, score = generate_trade_signal(stock_data)
                        price = float(stock_data.iloc[-1]['close']) if stock_data is not None else 0
                        
                        app_state["scanner"].append({
                            "symbol": symbol, "signal": signal, "score": score, "price": price
                        })
                        
                        # 如果信号是 BUY，准备模拟下单
                        if signal == "BUY":
                            if symbol in MANUAL_STOCKS:
                                log_msg(f"🛡️ 白名单保护：跳过自动加仓 {symbol}", "blue")
                                continue
                                
                            max_pos_value = total_asset * MAX_POSITION_PER_STOCK
                            current_pos_value = app_state["positions"].get(symbol, {}).get('qty', 0) * price
                            available_value = max_pos_value - current_pos_value
                            if available_value <= 0: continue
                            
                            qty = available_value / price # 支持买入碎股
                            if qty <= 0: continue
                            
                            execute_trade(trade_client, symbol, "BUY", qty, price)

                    last_scan_time = time.time()
                    log_msg(f"✅ 扫描完成，防拥堵熔断 {TRADE_INTERVAL} 秒", "green")

                else:
                    countdown = int(TRADE_INTERVAL - (current_time - last_scan_time))
                    layout["right_panel"].update(Panel(layout["right_panel"].renderable, title=f"[bold]量化扫描雷达 (下一次重载: {countdown}s)[/bold]", border_style="magenta"))
                
                update_ui(layout)
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                break 
            except Exception as e:
                log_msg(f"❌ 引擎核心异常: {str(e)}", "red")
                update_ui(layout) 
                time.sleep(5)

if __name__ == "__main__":
    main()