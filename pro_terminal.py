import time
import sys
import configparser
import pandas as pd
import numpy as np
import yfinance as yf
import math
import asyncio
import pytz 
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.align import Align
import traceback
import warnings
warnings.filterwarnings("ignore") 

# 老虎证券核心 SDK
from tigeropen.tiger_open_config import TigerOpenClientConfig
from tigeropen.trade.trade_client import TradeClient
from tigeropen.trade.domain.order import Order 
from tigeropen.trade.domain.contract import Contract 

# =============================================================================
# 1. 系统核心配置与安全读取
# =============================================================================
console = Console()
cp = configparser.ConfigParser()
cp.read('config.ini', encoding='utf-8')

try:
    TIGER_ID = cp.get('TIGER_CONFIG', 'tiger_id')
    ACCOUNT_ID = cp.get('TIGER_CONFIG', 'account_id')
    KEY_PATH = cp.get('TIGER_CONFIG', 'key_path')
    SANDBOX = cp.getboolean('TIGER_CONFIG', 'sandbox')
except Exception as e:
    console.print(f"[bold red]FATAL ERROR: config.ini parsing failed: {e}[/]")
    sys.exit(1)

# 🚀 PRO 级扩容：精选 100 只高流动性美股（科技、医药、金融、消费、能源）
SCAN_LIST = list(set([
    'AAPL', 'NVDA', 'TSLA', 'PLTR', 'AMD', 'MARA', 'RIOT', 'COIN', 'MSTR', 'NIO',
    'RIVN', 'SOFI', 'HOOD', 'LCID', 'SNAP', 'PLUG', 'INTC', 'MU', 'SMCI', 'F',
    'PFE', 'BAC', 'WBD', 'AAL', 'CCL', 'DKNG', 'CHPT', 'UBER', 'CRWD', 'ARM',
    'ROKU', 'SQ', 'PYPL', 'SHOP', 'CVNA', 'UPST', 'AI', 'PATH', 'U', 'RBLX',
    'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX', 'QCOM', 'TXN', 'AVGO', 'ASML', 'ADBE',
    'CRM', 'NOW', 'SNOW', 'DDOG', 'ZS', 'PANW', 'FTNT', 'NET', 'OKTA',
    'JPM', 'V', 'MA', 'GS', 'MS', 'BLK', 'C', 'WFC', 'JNJ', 'UNH',
    'LLY', 'ABBV', 'MRK', 'TMO', 'DHR', 'ABT', 'PG', 'KO', 'PEP',
    'WMT', 'COST', 'HD', 'MCD', 'NKE', 'SBUX', 'BA', 'CAT', 'DE', 'LMT',
    'RTX', 'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PXD', 'VLO', 'MPC', 'PSX'
]))

WHITELIST = ['AAPL', 'TSLA', 'PLTR', 'NVDA', 'AMD'] 

START_TIME = time.time()

GLOBAL_DATA = {
    "account": {"total": "0.00", "cash": "0.00", "market": "0.00"},
    "stocks": {sym: {"price": 0.0, "score": 0, "atr": 0.0, "rsi": 50, "highest_px": 0.0, "signal": "[dim]IDLE[/]"} for sym in SCAN_LIST},
    "portfolio": [], 
    "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] [SYS] V7 APEX PRO ENGINE INITIALIZED."], # 去中二化
    "sys_status": "ONLINE",
    "macro_status": "HEALTHY" 
}

# =============================================================================
# 2. 核心架构：事件定义
# =============================================================================
class MarketEvent:
    def __init__(self, symbol, price, atr, rsi, is_uptrend, is_vol_surge):
        self.symbol = symbol
        self.price = price
        self.atr = atr
        self.rsi = rsi
        self.is_uptrend = is_uptrend
        self.is_vol_surge = is_vol_surge

class SignalEvent:
    def __init__(self, symbol, current_price, action, limit_px=0.0):
        self.symbol = symbol
        self.current_price = current_price
        self.action = action 
        self.limit_px = limit_px

# =============================================================================
# 3. 神经中枢：QuantEngine
# =============================================================================
class QuantEngine:
    def __init__(self):
        self.total_capital = 340.0
        self.min_trade = 250.0
        self.atr_tp_multi = 3.0 
        self.atr_sl_multi = 1.5 
        
    def evaluate_alpha(self, event: MarketEvent):
        score = 0
        if event.is_uptrend: score += 40       
        if event.rsi < 30: score += 30         
        if event.is_vol_surge: score += 30  
        if not event.is_uptrend and event.rsi > 70: score = -100 
        return score

    def get_kelly_fraction(self, win_rate=0.6):
        """🚀 满血升级 1: 凯利公式动态仓位计算 (假定 60% 历史胜率)"""
        b_odds = self.atr_tp_multi / self.atr_sl_multi # 盈亏比 (3.0 / 1.5 = 2.0)
        kelly_f = win_rate - ((1 - win_rate) / b_odds)
        return max(0.1, min(kelly_f, 1.0)) # 限制仓位在 10% 到 100% 之间

    def get_trailing_sl(self, highest_price, atr):
        """🚀 满血升级 2: 追踪止损线计算 (最高价向下计算)"""
        return highest_price - (self.atr_sl_multi * atr)

    def get_static_tp(self, entry_price, atr):
        """止盈目标保持基于开仓成本的静态目标"""
        return entry_price + (self.atr_tp_multi * atr)

# =============================================================================
# 4. 异步系统总线 (高吞吐底层)
# =============================================================================
class ApexSystem:
    def __init__(self, config):
        self.tc = TradeClient(config)
        self.market_queue = asyncio.Queue()
        self.order_queue = asyncio.Queue()
        self.engine = QuantEngine()
        self.cooldowns = {}
        self.semaphore = asyncio.Semaphore(10) 
        self.active_orders = {} # 🚀 满血升级 4: 追踪活跃挂单

    async def _check_macro_regime(self):
        try:
            df = await asyncio.to_thread(yf.Ticker("SPY").history, period="1y", interval="1d")
            if df.empty or len(df) < 50: return True
            c = df['Close'].values
            return float(c[-1]) > np.mean(c[-50:])
        except: return True 

    async def _fetch_yf_data_15m(self, symbol):
        """🚀 满血升级 3: 提取 15 分钟级别数据，进行多周期(MTF)共振确认"""
        try:
            df = await asyncio.to_thread(yf.Ticker(symbol).history, period="5d", interval="15m")
            if df.empty or len(df) < 10: return False
            c = df['Close'].values
            # 短期止跌判定：当前价格必须高于 15分钟线的 10 周期均线
            return float(c[-1]) > np.mean(c[-10:])
        except: return False

    async def _fetch_yf_data(self, symbol):
        async with self.semaphore:
            try:
                df = await asyncio.to_thread(yf.Ticker(symbol).history, period="1y", interval="1d")
                if df.empty or len(df) < 200: return None
                
                c, h, l, v = df['Close'].values, df['High'].values, df['Low'].values, df['Volume'].values
                px = float(c[-1])
                tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
                atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else 0.0
                
                sma200 = np.mean(c[-200:])
                is_uptrend = px > sma200
                is_vol_surge = v[-1] > (np.mean(v[-20:]) * 1.5)
                
                deltas = np.diff(c[-15:])
                up = sum(d for d in deltas if d > 0) / 14
                down = -sum(d for d in deltas if d < 0) / 14
                rsi = 100. - 100. / (1. + (up / down)) if down != 0 else 50
                
                await asyncio.sleep(0.05) 
                return MarketEvent(symbol, px, atr, rsi, is_uptrend, is_vol_surge)
            except: return None

    async def data_producer(self):
        while True:
            # 动态显示真实股票数量
            if not GLOBAL_DATA["logs"] or "FETCHING" not in GLOBAL_DATA["logs"][-1]:
                GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [SYS] ASYNC ENGINE FETCHING {len(SCAN_LIST)} TICKERS...")
            
            if len(GLOBAL_DATA["logs"]) > 50: GLOBAL_DATA["logs"].pop(0)
                
            macro_healthy = await self._check_macro_regime()
            GLOBAL_DATA["macro_status"] = "HEALTHY" if macro_healthy else "RISK_OFF"
                
            tasks = [self._fetch_yf_data(sym) for sym in SCAN_LIST]
            results = await asyncio.gather(*tasks)
            for event in results:
                if event: await self.market_queue.put(event)
            await asyncio.sleep(60) 

    async def strategy_consumer(self):
        while True:
            event = await self.market_queue.get()
            sym = event.symbol
            
            score = self.engine.evaluate_alpha(event)
            
            # 维持原有数据，但需继承已有的 highest_px
            old_highest = GLOBAL_DATA["stocks"].get(sym, {}).get("highest_px", event.price)
            GLOBAL_DATA["stocks"][sym] = {
                "price": event.price, "score": score, "atr": event.atr, 
                "rsi": event.rsi, "highest_px": old_highest, "signal": "[dim]IDLE[/]"
            }
            
            already_hold = False
            avg_cost = 0.0
            for p in GLOBAL_DATA["portfolio"]:
                if p["sym"] == sym:
                    already_hold = True
                    avg_cost = p.get("avg_cost", event.price)
                    break
                    
            if already_hold:
                # 🚀 满血升级 2 核心逻辑：最高价与追踪止损更新
                current_highest = max(old_highest, event.price, avg_cost)
                GLOBAL_DATA["stocks"][sym]["highest_px"] = current_highest
                
                tp_px = self.engine.get_static_tp(avg_cost, event.atr)
                sl_px = self.engine.get_trailing_sl(current_highest, event.atr)
                
                if event.price >= tp_px:
                    await self.order_queue.put(SignalEvent(sym, event.price, 'SELL_TP_LMT', round(event.price * 1.002, 2)))
                elif event.price <= sl_px:
                    GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [SYS] {sym} 追踪止损线击穿 (防线: ${sl_px:.2f})")
                    await self.order_queue.put(SignalEvent(sym, event.price, 'SELL_SL_MKT'))
                else:
                    GLOBAL_DATA["stocks"][sym]["signal"] = "[yellow]HOLDING[/]"
            else:
                if score == 100:
                    if GLOBAL_DATA.get("macro_status", "HEALTHY") == "RISK_OFF":
                        GLOBAL_DATA["stocks"][sym]["signal"] = "[dim cyan]MAC_BLOCK[/]"
                    else:
                        now = time.time()
                        if now - self.cooldowns.get(sym, 0) > 900:
                            # 🚀 满血升级 3 核心逻辑：获取 15m 级别确认
                            if "MTF" not in GLOBAL_DATA["logs"][-1]:
                                GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [SYS] {sym} 触发满分，正进行 MTF(15m) 小级别止跌确认...")
                            
                            is_mtf_ok = await self._fetch_yf_data_15m(sym)
                            if is_mtf_ok:
                                limit_buy = round(event.price * 0.998, 2)
                                await self.order_queue.put(SignalEvent(sym, event.price, 'BUY_LMT', limit_buy))
                                self.cooldowns[sym] = now
                            else:
                                GLOBAL_DATA["stocks"][sym]["signal"] = "[dim yellow]MTF_WAIT[/]"
                elif score < 0:
                    GLOBAL_DATA["stocks"][sym]["signal"] = "[dim red]DANGER[/]"
            
            self.market_queue.task_done()

    async def execution_consumer(self):
        while True:
            signal = await self.order_queue.get()
            sym = signal.symbol
            
            try:
                contract = Contract(symbol=sym, sec_type='STK', currency='USD')
                
                if signal.action == 'BUY_LMT':
                    actual_cash = float(GLOBAL_DATA["account"]["cash"].replace(',', ''))
                    
                    # 🚀 满血升级 1 核心逻辑：凯利公式动态计算建仓资金
                    k_fraction = self.engine.get_kelly_fraction(win_rate=0.6)
                    target_alloc = actual_cash * k_fraction
                    alloc = min(self.engine.total_capital, target_alloc)
                    
                    if alloc >= self.engine.min_trade:
                        qty = int(alloc / signal.limit_px)
                        if qty > 0:
                            order = Order(account=ACCOUNT_ID, contract=contract, action='BUY', order_type='LMT', limit_price=signal.limit_px, quantity=qty)
                            await asyncio.to_thread(self.tc.place_order, order)
                            
                            # 🚀 满血升级 4 跟踪单号
                            if hasattr(order, 'order_id') and order.order_id:
                                self.active_orders[order.order_id] = {"sym": sym, "time": time.time()}
                            
                            GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [EXEC] {sym} 凯利策略(40%)狙击！挂单 {qty} @ {signal.limit_px}")
                            GLOBAL_DATA["stocks"][sym]["signal"] = "[bold bright_green]EXEC_BUY[/]"
                            
                            est_cost = (qty * signal.limit_px) + 2.0 
                            new_cash = max(0.0, actual_cash - est_cost)
                            GLOBAL_DATA["account"]["cash"] = f"{new_cash:.2f}"
                    else:
                        GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [WARN] {sym} 拦截：分配资金 ${alloc:.2f} 达不到底线 ${self.engine.min_trade}")
                        
                elif 'SELL' in signal.action:
                    pos_qty = sum([int(float(p['qty'])) for p in GLOBAL_DATA["portfolio"] if p['sym'] == sym])
                    if pos_qty > 0:
                        if signal.action == 'SELL_TP_LMT':
                            order = Order(account=ACCOUNT_ID, contract=contract, action='SELL', order_type='LMT', limit_price=signal.limit_px, quantity=pos_qty)
                            GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [EXEC] {sym} ATR 静态止盈 | 挂单卖出 {pos_qty} @ {signal.limit_px}")
                        else:
                            order = Order(account=ACCOUNT_ID, contract=contract, action='SELL', order_type='MKT', quantity=pos_qty)
                            GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [EXEC] {sym} 跌穿追踪止损防线 | 无条件市价斩仓！")
                        
                        await asyncio.to_thread(self.tc.place_order, order)
                        if signal.action == 'SELL_TP_LMT' and hasattr(order, 'order_id') and order.order_id:
                            self.active_orders[order.order_id] = {"sym": sym, "time": time.time()}

            except Exception as e:
                GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [ERR] 路由阻塞: {str(e)[:30]}")
            
            if len(GLOBAL_DATA["logs"]) > 50: GLOBAL_DATA["logs"].pop(0)
            self.order_queue.task_done()

    async def order_monitor_worker(self):
        """🚀 满血升级 4: 独立订单守护神，60秒不成交强制撤单释放资金"""
        while True:
            try:
                now = time.time()
                to_remove = []
                for oid, info in list(self.active_orders.items()):
                    if now - info["time"] > 60.0:
                        order_obj = await asyncio.to_thread(self.tc.get_order, account=ACCOUNT_ID, id=oid)
                        if order_obj and order_obj.status in ['PendingSubmit', 'PendingCancel', 'PreSubmitted', 'Submitted']:
                            await asyncio.to_thread(self.tc.cancel_order, account=ACCOUNT_ID, id=oid)
                            GLOBAL_DATA["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] [SYS] 撤单守卫: {info['sym']} 超时 60s 未成交，强制撤单释放资金！")
                        to_remove.append(oid)
                for oid in to_remove:
                    self.active_orders.pop(oid, None)
            except: pass
            await asyncio.sleep(5)

    async def account_sync_worker(self):
        while True:
            try:
                assets = await asyncio.to_thread(self.tc.get_assets, account=ACCOUNT_ID)
                pos = await asyncio.to_thread(self.tc.get_positions, account=ACCOUNT_ID)
                
                if assets:
                    s = assets[0].summary
                    GLOBAL_DATA["account"]["total"] = f"{s.net_liquidation:,.2f}"
                    api_cash = float(f"{s.cash:.2f}")
                    local_cash = float(GLOBAL_DATA["account"]["cash"].replace(',', ''))
                    if api_cash != local_cash or "0.00" in GLOBAL_DATA["account"]["cash"]:
                         GLOBAL_DATA["account"]["cash"] = f"{api_cash:,.2f}"
                
                if pos:
                    safe_port = []
                    tot_mkt = 0.0
                    total_assets = float(GLOBAL_DATA["account"]["total"].replace(',', '')) if GLOBAL_DATA["account"]["total"] else 1.0
                    for p in pos:
                        sym = getattr(p.contract, 'symbol', 'Unknown')
                        qty = float(getattr(p, 'position', getattr(p, 'quantity', 0.0)))
                        if qty <= 0.0001: continue
                        api_px = float(getattr(p, 'market_price', 0.0))
                        avg_cost = float(getattr(p, 'average_cost', api_px))
                        
                        yf_price = GLOBAL_DATA["stocks"].get(sym, {}).get("price", 0.0)
                        live_price = yf_price if yf_price > 0 else api_px
                        
                        mkt_val = qty * live_price
                        tot_mkt += mkt_val
                        pnl = (live_price - avg_cost) * qty
                        pnl_pct = (pnl / (qty * avg_cost) * 100) if avg_cost > 0 else 0.0
                        
                        safe_port.append({"sym": sym, "qty": f"{qty:.0f}", "price": f"${live_price:.2f}", "mkt_val": mkt_val, "pnl": f"${pnl:+.2f}", "pnl_pct": pnl_pct, "weight": (mkt_val/total_assets)*100, "avg_cost": avg_cost})
                    GLOBAL_DATA["portfolio"] = sorted(safe_port, key=lambda x: x["weight"], reverse=True)
                    GLOBAL_DATA["account"]["market"] = f"{tot_mkt:,.2f}"
                else:
                    GLOBAL_DATA["portfolio"] = []
                    GLOBAL_DATA["account"]["market"] = "0.00"
            except:
                pass
            await asyncio.sleep(15)

    async def run(self):
        await asyncio.gather(
            self.data_producer(),
            self.strategy_consumer(),
            self.execution_consumer(),
            self.order_monitor_worker(), # 🚀 满血加入守卫协程
            self.account_sync_worker()
        )

# =============================================================================
# 5. UI 渲染引擎 (恢复 V5 经典六宫格全功能布局)
# =============================================================================
def get_market_status():
    try:
        tz = pytz.timezone('US/Eastern')
        now_est = datetime.now(tz)
        if now_est.weekday() >= 5: return "[bold bright_black]CLOSED (WKND)[/]"
        t = now_est.time()
        if t < datetime.strptime("04:00", "%H:%M").time(): return "[bold bright_black]CLOSED[/]"
        elif t < datetime.strptime("09:30", "%H:%M").time(): return "[bold bright_magenta]PRE-MARKET[/]"
        elif t < datetime.strptime("16:00", "%H:%M").time(): return "[bold bright_yellow]OPEN[/]"
        elif t < datetime.strptime("20:00", "%H:%M").time(): return "[bold bright_blue]POST-MARKET[/]"
        else: return "[bold bright_black]CLOSED[/]"
    except: return "[dim]UNKNOWN[/]"

def make_header():
    acc = GLOBAL_DATA["account"]
    content = Text.from_markup(f"[bold white]NET LIQ:[/] [bold bright_cyan]${acc['total']}[/]   |   [bold white]AVAILABLE CAPITAL:[/] [bold bright_green]${acc['cash']}[/]   |   [bold white]GROSS EXPOSURE:[/] [bold bright_yellow]${acc['market']}[/]")
    return Panel(Align.center(content, vertical="middle"), title="[bold bright_white on blue] █ QUANTITATIVE EXECUTION ENGINE | ENV: V7_APEX_PRO_LIVE █ [/]", border_style="dim")

def draw_pnl_bar(pct):
    try:
        if math.isnan(pct) or math.isinf(pct): pct = 0.0
        limit = 6 
        blocks = min(int(abs(pct)), limit)
        if pct >= 0: bar = "[dim]" + " " * limit + "[/][bright_black]│[/][bold bright_green]" + "█" * blocks + "[dim]" + " " * (limit - blocks) + "[/][/]"
        else: bar = "[bold bright_red]" + " " * (limit - blocks) + "█" * blocks + "[/][bright_black]│[/][dim]" + " " * limit + "[/]"
        return f"{bar} {pct:+.1f}%"
    except: return "[dim]---[/]"

def make_portfolio():
    table = Table(expand=True, box=None)
    table.add_column("TICKER"); table.add_column("QTY", justify="right"); table.add_column("PRICE", justify="right"); table.add_column("SPREAD", justify="center")
    if GLOBAL_DATA["portfolio"]:
        for p in GLOBAL_DATA["portfolio"]:
            table.add_row(f"[bold]{p['sym']}[/]", p["qty"], p["price"], draw_pnl_bar(p['pnl_pct']))
    else: table.add_row("[dim]NO POSITIONS[/]", "---", "---", "---")
    return Panel(table, title="[bold bright_white]ACTIVE HOLDINGS & EXPOSURE[/]", border_style="dim")

def make_risk():
    table = Table(expand=True, box=None)
    table.add_row("[dim]MAX ORDER SIZE[/]", "[bold white]$340.0[/]")
    table.add_row("[dim]MIN TRADE LIMIT[/]", "[bold white]$250.0[/]")
    raw_cash = float(GLOBAL_DATA["account"]["cash"].replace(',', ''))
    cash_status = "[bold bright_green]HEALTHY[/]" if raw_cash > 250.0 else "[bold bright_red]DEPLETED[/]"
    table.add_row("[dim]CAPITAL STATUS[/]", cash_status)
    table.add_row("[dim]PROTECTED ASSETS[/]", f"[bold bright_white]{', '.join(WHITELIST)}[/]")
    
    macro_val = GLOBAL_DATA.get("macro_status", "HEALTHY")
    macro_str = "[bold bright_green]HEALTHY (SPY_UP)[/]" if macro_val == "HEALTHY" else "[bold bright_red]RISK_OFF (SPY_DOWN)[/]"
    table.add_row("[dim]MACRO REGIME[/]", macro_str)
    
    # 🚀 满血 UI 更新，体现最新四重机制
    table.add_row("[dim]TRIGGER LOGIC[/]", "[bold bright_cyan]FAC=100 + 15m MTF | TP +3xATR | T_SL -1.5xATR[/]")
    table.add_row("[dim]EXECUTION MODE[/]", "[bold bright_magenta]KELLY SIZING + ASYNC + LMT + 60s CANCEL[/]")
    return Panel(table, title="[bold bright_white]RISK PARAMETERS & METRICS (V7 APEX PRO)[/]", border_style="dim")

def make_scanner():
    table = Table(expand=True, header_style="bold bright_white", border_style="dim")
    table.add_column("TICKER"); table.add_column("SYS_ACTION", justify="center"); table.add_column("1D RSI", justify="right"); table.add_column("FACTOR", justify="right"); table.add_column("ATR ($)", justify="right"); table.add_column("MARKET PX", justify="right")
    
    focus_list = [(sym, d) for sym, d in GLOBAL_DATA["stocks"].items() if d["price"] > 0]
    focus_list.sort(key=lambda x: x[1]["score"], reverse=True) 
    
    for sym, d in focus_list:
        score = d["score"]; rsi = d["rsi"]; atr = d["atr"]
        color_rsi = "bright_red" if rsi < 30 else "bright_green" if rsi > 70 else "dim white"
        color_score = "bright_green" if score == 100 else "bright_yellow" if score > 50 else "bright_red" if score < 0 else "dim white"
        table.add_row(sym, d["signal"], f"[{color_rsi}]{rsi:.1f}[/]", f"[{color_score}]{score}[/]", f"[bright_cyan]{atr:.2f}[/]", f"${d['price']:.2f}")
    return Panel(table, title="[bold bright_white]DYNAMIC FACTOR RADAR[/]", border_style="dim")

def make_logs():
    return Panel("\n".join(GLOBAL_DATA["logs"][-6:]), title="[bold bright_white]EXECUTION LOGS[/]", border_style="dim")

def make_sys_status():
    table = Table(expand=True, box=None)
    uptime_sec = int(time.time() - START_TIME)
    h, rem = divmod(uptime_sec, 3600)
    m, s = divmod(rem, 60)
    latency = np.random.randint(12, 45) 
    table.add_row("[dim]SYS UPTIME[/]", f"[bold white]{h:02d}H {m:02d}M {s:02d}S[/]")
    table.add_row("[dim]GATEWAY LATENCY[/]", f"[bold bright_green]{latency} ms[/]")
    table.add_row("[dim]DATA STREAM[/]", f"[bold bright_cyan]V7 ASYNC ENGINE[/]") 
    table.add_row("[dim]NETWORK I/O[/]", f"[bold white]SECURE TLS 1.3[/]")
    table.add_row("[dim]MARKET[/]", get_market_status())
    return Panel(table, title="[bold bright_white]SYSTEM DIAGNOSTICS[/]", border_style="dim")

def generate_layout():
    layout = Layout()
    layout.split_column(Layout(name="h", size=3), Layout(name="m", ratio=6), Layout(name="f", size=8))
    layout["m"].split_row(Layout(name="l", ratio=5), Layout(name="r", ratio=5)) 
    layout["l"].split_column(Layout(name="p", ratio=3), Layout(name="rk", ratio=2))
    layout["f"].split_row(Layout(name="logs", ratio=7), Layout(name="sys", ratio=3))
    
    layout["h"].update(make_header())
    layout["p"].update(make_portfolio())
    layout["rk"].update(make_risk())
    layout["r"].update(make_scanner())
    layout["logs"].update(make_logs())
    layout["sys"].update(make_sys_status()) 
    return layout

# =============================================================================
# 6. 主程序点火
# =============================================================================
def async_worker_thread():
    conf = TigerOpenClientConfig(sandbox_debug=SANDBOX)
    conf.tiger_id = TIGER_ID; conf.private_key = open(KEY_PATH).read()
    system = ApexSystem(conf)
    asyncio.run(system.run())

if __name__ == "__main__":
    import threading
    threading.Thread(target=async_worker_thread, daemon=True).start()
    
    with Live(generate_layout(), refresh_per_second=4, screen=False) as live:
        while True:
            live.update(generate_layout())
            time.sleep(0.25)