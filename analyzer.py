from data_fetcher import DataFetcher
from strategy import Strategy
from account import StockAccount
from configparser import ConfigParser

class Analyzer:
    def __init__(self, config=None):
        self.config = config or ConfigParser()
        self.fetcher = DataFetcher(self.config)
        self.strategy = Strategy(self.config)
        self.account = StockAccount(self.config)
        self.buy_ratio = self.config.getfloat('Buy', 'buy_ratio', fallback=0.2)
        self.min_buy_shares = self.config.getint('Buy', 'min_buy_shares', fallback=100)
        self.max_position_ratio = self.config.getfloat('ATR', 'max_position_ratio', fallback=0.2)
        self.market_index = self.config.get('Filter', 'market_index', fallback='000300.SH')
        self.market_df = None

    def analyze_stock(self, code):
        hist_df = self.fetcher.get_hist_data(code, days=100)
        if hist_df is None or hist_df.empty:
            return None, f"股票 {code} 历史数据获取失败", None

        realtime = self.fetcher.get_realtime_quote(code)
        if realtime is None:
            return None, f"股票 {code} 实时数据获取失败", None

        price = realtime['price']
        if price is None or price <= 0:
            return None, f"股票 {code} 当前价格无效", None

        if self.market_df is None:
            self.market_df = self.fetcher.get_index_hist(self.market_index, days=100)

        raw_signal, reason, atr = self.strategy.generate_signal(
            hist_df, price, realtime['volume'], self.market_df
        )

        shares = self.account.get_shares(code)
        final_signal = 'hold'
        final_reason = reason

        sell_shares, sell_reason = self.account.check_sell_rules(code, price, atr)
        if sell_shares > 0:
            success, msg = self.account.sell(code, price, sell_shares)
            if success:
                final_signal = 'sell'
                final_reason += f"；{sell_reason}，{msg}"
            else:
                final_signal = 'hold'
                final_reason += f"；{sell_reason}但卖出失败：{msg}"
        else:
            if raw_signal == 'buy':
                if shares == 0:
                    cash = self.account.get_cash(code)
                    atr_ratio = atr / price if atr and price else 0.05
                    adjusted_ratio = self.buy_ratio * max(0.5, 1 - atr_ratio * 5)
                    adjusted_ratio = max(0.1, min(self.buy_ratio, adjusted_ratio))
                    target_amount = cash * adjusted_ratio
                    target_shares = int(target_amount / price / 100) * 100
                    max_shares = int(cash / price / 100) * 100
                    buy_shares = min(target_shares, max_shares)

                    total_assets, _, _, _, _, _, _ = self.account.get_summary({})
                    if total_assets > 0:
                        max_shares_by_risk = int(total_assets * self.max_position_ratio / price / 100) * 100
                        buy_shares = min(buy_shares, max_shares_by_risk)

                    if buy_shares >= self.min_buy_shares:
                        success, msg = self.account.buy(code, buy_shares, price)
                        if success:
                            final_signal = 'buy'
                            final_reason += f"；{msg}"
                        else:
                            final_signal = 'hold'
                            final_reason += f"；买入失败：{msg}"
                    else:
                        final_signal = 'hold'
                        final_reason += f"；现金不足或价格过高，无法买入至少 {self.min_buy_shares} 股（当前现金 {cash:.2f}，价格 {price:.2f}）"
                else:
                    final_signal = 'hold'
                    final_reason += f"；当前已持仓{shares}股，继续持有（不加仓）"
            elif raw_signal == 'sell':
                if shares > 0:
                    success, msg = self.account.sell(code, price)
                    if success:
                        final_signal = 'sell'
                        final_reason += f"；{msg}"
                    else:
                        final_signal = 'hold'
                        final_reason += f"；卖出失败：{msg}"
                else:
                    final_signal = 'hold'
                    final_reason += f"；当前无持仓，无需卖出"
            else:
                if shares > 0:
                    final_reason += f"；当前持仓{shares}股，继续持有"
                else:
                    final_reason += f"；当前无持仓，继续观望"

        return final_signal, final_reason, realtime['name']