import datetime
from core.tiger_api import get_real_price, place_buy_order, place_sell_order, get_positions

class AITrader:
    def __init__(self):
        self.ai_auto_trade = False
        self.ai_log = []
        # AI股票池
        self.STOCK_POOL = ["AAPL", "MSFT", "AMZN", "TSLA", "GOOG", "META", "NVDA", "NFLX"]

    # 美股交易时间检查
    def is_market_open(self):
        now = datetime.datetime.utcnow()
        weekday = now.weekday()
        hour = now.hour
        # 美股夏令时：UTC 13:30-20:00
        if weekday >= 5:
            return False
        if hour < 13 or hour > 20:
            return False
        return True

    # AI自动选股交易
    def ai_scan_and_trade(self, score_engine):
        if not self.ai_auto_trade:
            return
        
        # 休市不交易
        if not self.is_market_open():
            self.add_ai_log("休市", "N/A", 0, "美股休市，不执行交易", "等待开盘")
            return

        best_score = 0
        best_symbol = None
        best_signal = "HOLD"
        best_reason = ""

        # 扫描股票池
        for symbol in self.STOCK_POOL:
            stock = get_real_price(symbol)
            if stock["price"] <= 0:
                continue
            score = score_engine.calc_all_score(symbol)
            reason = self.get_ai_reason(score)
            if score["total"] > best_score:
                best_score = score["total"]
                best_symbol = symbol
                best_signal = score["signal"]
                best_reason = reason

        if not best_symbol:
            return

        stock = get_real_price(best_symbol)
        price = stock["price"]
        future = self.predict_future({"total": best_score})
        amount = 10

        # 止盈止损检查现有持仓
        positions = get_positions()
        for pos in positions:
            sym = pos["symbol"]
            rate = pos["pnl_rate"]
            if rate >= 8:
                place_sell_order(sym, pos["qty"], get_real_price(sym)["price"])
                self.add_ai_log("止盈卖出", sym, pos["price"], "收益≥8%", future)
            if rate <= -3:
                place_sell_order(sym, pos["qty"], get_real_price(sym)["price"])
                self.add_ai_log("止损卖出", sym, pos["price"], "亏损≤-3%", future)

        # 买入最优股票
        if best_signal in ["STRONG BUY", "BUY"]:
            place_buy_order(best_symbol, amount, price)
            self.add_ai_log("选股买入", best_symbol, price, best_reason, future)

    def get_ai_reason(self, score):
        s = score["signal"]
        if s == "STRONG BUY":
            return f"评分{score['total']} | 全市场最高分，技术资金共振"
        elif s == "BUY":
            return f"评分{score['total']} | 趋势向好，适合买入"
        elif s == "HOLD":
            return f"评分{score['total']} | 震荡观望"
        else:
            return f"评分{score['total']} | 趋势走弱，建议卖出"

    def predict_future(self, score):
        t = score["total"]
        if t >= 80:
            return "🚀 预测：短期强势上涨"
        elif t >= 60:
            return "📈 预测：震荡偏强"
        elif t >= 40:
            return "📊 预测：区间震荡"
        else:
            return "📉 预测：大概率下跌"

    def add_ai_log(self, action, symbol, price, reason, future):
        log = {
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "symbol": symbol,
            "price": round(price, 2),
            "reason": reason,
            "future": future
        }
        self.ai_log.append(log)
        if len(self.ai_log) > 10:
            self.ai_log.pop(0)

ai_trader = AITrader()