from tigeropen.tiger_open_config import TigerOpenClientConfig
from tigeropen.trade.trade_client import TradeClient
from tigeropen.common.util.signature_utils import read_private_key

# ====================== 【务必填写真实的ID】 ======================
TIGER_ID = "20158956"     # 这里填你真实的 TIGER_ID
ACCOUNT_ID = "21946767516413829"   # 这里填你真实的 ACCOUNT_ID
PRIVATE_KEY_PATH = "tiger_private_key.pem"
SANDBOX = True
# ======================================================================

try:
    client_config = TigerOpenClientConfig(sandbox_debug=SANDBOX)
    client_config.private_key = read_private_key(PRIVATE_KEY_PATH)
    client_config.tiger_id = TIGER_ID
    client_config.account = ACCOUNT_ID
    
    client = TradeClient(client_config)

    accounts = client.get_managed_accounts()
    print("✅ 连接成功！！！老虎服务器鉴权通过。")
    print(f"你名下的账户有：{[a.account for a in accounts]}")
    
    positions = client.get_positions()
    print(f"当前持仓：{len(positions)}只")
    for pos in positions:
        # 🚨 修复：官方结构必须通过 pos.contract 才能获取到 symbol
        print(f"  - {pos.contract.symbol}: {pos.quantity}股 | 最新价: {pos.market_price} | 盈亏: {pos.unrealized_pnl}")
        
except Exception as e:
    print(f"❌ 连接失败，错误原因：{str(e)}")