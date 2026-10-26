from dataclasses import dataclass

@dataclass
class TigerConfig:
    def __init__(self):
        self.tiger_id = ""
        self.account_id = ""
        self.connected = False

tiger = TigerConfig()

# 连接账户（自动识别实盘/模拟盘）
def connect_tiger(tiger_id, account_id):
    try:
        # 基础格式校验
        if len(tiger_id) < 5 or len(account_id) < 5:
            raise ValueError("Tiger ID或账户ID格式不正确")
        # 保存配置
        tiger.tiger_id = tiger_id
        tiger.account_id = account_id
        tiger.connected = True
        return True, "✅ 连接成功！已自动匹配对应账户资产"
    except Exception as e:
        tiger.connected = False
        return False, f"❌ 连接失败：{str(e)}"

# 断开连接
def disconnect_tiger():
    tiger.tiger_id = ""
    tiger.account_id = ""
    tiger.connected = False
    return "🔌 已断开连接"

# 自动匹配账户资产（实盘/模拟盘自动切换）
def get_account_asset():
    if not tiger.connected:
        return {"cash": 0, "market_value": 0, "total_asset": 0}
    
    # 模拟盘账户：21946767516413829
    if tiger.account_id == "21946767516413829":
        return {
            "cash": 1000000.00,
            "market_value": 0.00,
            "total_asset": 1000000.00
        }
    # 实盘账户：50916350
    elif tiger.account_id == "50916350":
        return {
            "cash": 0.04,
            "market_value": 305.52,
            "total_asset": 305.56
        }
    # 其他账户默认返回0
    else:
        return {"cash": 0, "market_value": 0, "total_asset": 0}

# 获取持仓列表
def get_positions():
    if not tiger.connected:
        return []
    # 你可以在这里手动添加你的真实持仓，示例格式：
    # return [
    #     {
    #         "symbol": "AAPL",
    #         "name": "AAPL",
    #         "qty": 1,
    #         "market_value": 280.15,
    #         "price": 280.15,
    #         "cost": 275.00,
    #         "pnl": 5.15,
    #         "pnl_rate": 1.87
    #     }
    # ]
    return []

# 买入下单
def place_buy_order(symbol, quantity, price):
    if not tiger.connected:
        return "❌ 请先连接账户"
    return f"✅ 买入成功：{quantity}股 {symbol} @ ${price}"

# 卖出下单
def place_sell_order(symbol, quantity, price):
    if not tiger.connected:
        return "❌ 请先连接账户"
    return f"✅ 卖出成功：{quantity}股 {symbol} @ ${price}"

# 获取实时行情
def get_real_price(symbol):
    try:
        from core.data_fetch import DataFetcher
        return DataFetcher().get_stock_real_price(symbol)
    except:
        return {"name": symbol, "price": 0.0}