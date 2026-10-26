import numpy as np
from config import Config

class SixDimensionScore:
    def __init__(self):
        self.w = Config()

    def tech_dim(self, symbol):
        return 75
    def money_dim(self, symbol):
        return 70
    def fund_dim(self, symbol):
        return 70
    def sent_dim(self):
        return 65
    def macro_dim(self):
        return 68
    def ml_dim(self):
        return np.random.randint(68,86)

    def calc_all_score(self, symbol):
        t = self.tech_dim(symbol)
        m = self.money_dim(symbol)
        f = self.fund_dim(symbol)
        s = self.sent_dim()
        ma = self.macro_dim()
        ml = self.ml_dim()
        total = round(t*self.w.WEIGHT_TECH + m*self.w.WEIGHT_MONEY + f*self.w.WEIGHT_FUND + s*self.w.WEIGHT_SENT + ma*self.w.WEIGHT_MACRO + ml*self.w.WEIGHT_AI)
        if total <=40: sig="SELL"
        elif total <=60: sig="HOLD"
        elif total <=80: sig="BUY"
        else: sig="STRONG BUY"
        return {
            "total":total,"tech":t,"money":m,"fund":f,"sent":s,"macro":ma,"ml":ml,"signal":sig
        }