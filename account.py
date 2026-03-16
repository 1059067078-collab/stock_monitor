import json
import os
from config import load_stocks
from trade_logger import TradeLogger

ACCOUNT_FILE = "account.json"
INITIAL_CASH_PER_STOCK = 20000

class StockAccount:
    def __init__(self, config=None):
        self.config = config
        self.accounts = {}
        self.logger = TradeLogger()
        self.load()

    def load(self):
        if os.path.exists(ACCOUNT_FILE):
            with open(ACCOUNT_FILE, 'r') as f:
                data = json.load(f)
                self.accounts = data.get('accounts', {})
                stocks = load_stocks()
                for code in stocks:
                    if code not in self.accounts:
                        self.accounts[code] = {'cash': INITIAL_CASH_PER_STOCK, 'shares': 0, 'cost': 0.0}
                to_delete = [code for code in self.accounts if code not in stocks]
                for code in to_delete:
                    del self.accounts[code]
        else:
            stocks = load_stocks()
            self.accounts = {}
            for code in stocks:
                self.accounts[code] = {'cash': INITIAL_CASH_PER_STOCK, 'shares': 0, 'cost': 0.0}
        self.save()

    def save(self):
        with open(ACCOUNT_FILE, 'w') as f:
            json.dump({'accounts': self.accounts}, f, indent=2)

    def get_cash(self, code):
        if code not in self.accounts:
            self.accounts[code] = {'cash': INITIAL_CASH_PER_STOCK, 'shares': 0, 'cost': 0.0}
            self.save()
        return self.accounts[code]['cash']

    def get_shares(self, code):
        return self.accounts.get(code, {}).get('shares', 0)

    def get_cost(self, code):
        return self.accounts.get(code, {}).get('cost', 0.0)

    def get_entry_price(self, code):
        cost = self.get_cost(code)
        shares = self.get_shares(code)
        return cost / shares if shares > 0 else None

    def buy(self, code, shares, price):
        cash = self.get_cash(code)
        cost = shares * price
        if cash < cost:
            return False, f"股票 {code} 现金不足，需 {cost:.2f} 元，当前现金 {cash:.2f} 元"
        self.accounts[code]['cash'] -= cost
        self.accounts[code]['shares'] += shares
        old_cost = self.accounts[code].get('cost', 0.0)
        self.accounts[code]['cost'] = old_cost + cost
        self.save()
        self.logger.log(code, 'buy', price, shares, old_cost)
        return True, f"股票 {code} 买入 {shares} 股，花费 {cost:.2f} 元，剩余现金 {self.accounts[code]['cash']:.2f} 元"

    def sell(self, code, price, shares=None):
        current_shares = self.get_shares(code)
        if current_shares == 0:
            return False, f"股票 {code} 持仓为0，无法卖出"
        if shares is None or shares >= current_shares:
            sell_shares = current_shares
            new_shares = 0
        else:
            sell_shares = shares
            new_shares = current_shares - sell_shares

        current_cost = self.accounts[code].get('cost', 0.0)
        if current_shares > 0:
            cost_per_share = current_cost / current_shares
            sell_cost = cost_per_share * sell_shares
        else:
            sell_cost = 0.0

        income = sell_shares * price
        self.accounts[code]['cash'] += income
        self.accounts[code]['shares'] = new_shares
        self.accounts[code]['cost'] = current_cost - sell_cost
        self.save()

        profit = income - sell_cost
        profit_pct = (profit / sell_cost * 100) if sell_cost > 0 else 0
        self.logger.log(code, 'sell', price, sell_shares, current_cost, profit, profit_pct)

        return True, f"股票 {code} 卖出 {sell_shares} 股，收入 {income:.2f} 元，实现盈亏 {profit:+.2f} ({profit_pct:+.1f}%)，当前现金 {self.accounts[code]['cash']:.2f} 元"

    def add_cash(self, code, amount):
        if code not in self.accounts:
            self.accounts[code] = {'cash': INITIAL_CASH_PER_STOCK, 'shares': 0, 'cost': 0.0}
        self.accounts[code]['cash'] += amount
        self.save()
        return f"股票 {code} 追加资金 {amount:.2f} 元，当前现金 {self.accounts[code]['cash']:.2f} 元"

    def add_stock_account(self, code):
        if code not in self.accounts:
            self.accounts[code] = {'cash': INITIAL_CASH_PER_STOCK, 'shares': 0, 'cost': 0.0}
            self.save()

    def remove_stock_account(self, code):
        if code in self.accounts:
            if self.accounts[code]['shares'] > 0:
                return False, f"股票 {code} 仍有持仓 {self.accounts[code]['shares']} 股，请先卖出"
            del self.accounts[code]
            self.save()
            return True, f"股票 {code} 账户已移除"
        return False, f"股票 {code} 账户不存在"

    def get_summary(self, prices):
        total_cash = 0
        total_stock_value = 0
        total_cost = 0
        details = {}
        for code, acc in self.accounts.items():
            cash = acc['cash']
            shares = acc['shares']
            cost = acc.get('cost', 0.0)
            price = prices.get(code)
            stock_value = shares * price if price else 0
            total_cash += cash
            total_stock_value += stock_value
            total_cost += cost
            profit = stock_value - cost if shares > 0 else 0.0
            profit_pct = (profit / cost * 100) if cost > 0 and shares > 0 else 0.0
            details[code] = {
                'cash': cash,
                'shares': shares,
                'price': price,
                'stock_value': stock_value,
                'cost': cost,
                'profit': profit,
                'profit_pct': profit_pct,
                'total': cash + stock_value
            }
        total_assets = total_cash + total_stock_value
        total_profit = total_stock_value - total_cost
        total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0.0
        return total_assets, total_cash, total_stock_value, total_cost, total_profit, total_profit_pct, details

    def check_sell_rules(self, code, price, atr=None):
        shares = self.get_shares(code)
        if shares == 0:
            return 0, None

        entry_price = self.get_entry_price(code)
        if entry_price is None:
            return 0, None

        profit_pct = (price - entry_price) / entry_price

        if self.config:
            take_profit_enabled = self.config.getboolean('Sell', 'enable_take_profit', fallback=False)
            stop_loss_enabled = self.config.getboolean('Sell', 'enable_stop_loss', fallback=False)
            stop_loss_atr = self.config.getfloat('ATR', 'stop_loss_atr', fallback=2.0)
            take_profit_atr = self.config.getfloat('ATR', 'take_profit_atr', fallback=3.0)
        else:
            take_profit_enabled = False
            stop_loss_enabled = False
            stop_loss_atr = 2.0
            take_profit_atr = 3.0

        # ATR止损
        if stop_loss_enabled and atr is not None and atr > 0:
            stop_price = entry_price - stop_loss_atr * atr
            if price <= stop_price:
                return shares, f"ATR止损触发 (价格 {price:.2f} <= {stop_price:.2f})"

        # ATR止盈（分批止盈50%）
        if take_profit_enabled and atr is not None and atr > 0:
            take_profit_price = entry_price + take_profit_atr * atr
            if price >= take_profit_price:
                sell_shares = int(shares * 0.5 / 100) * 100
                if sell_shares >= 100:
                    return sell_shares, f"ATR止盈触发 (价格 {price:.2f} >= {take_profit_price:.2f})，卖出50%"
                else:
                    return shares, f"ATR止盈触发，但剩余股数不足100，全部卖出"

        # 固定比例止盈止损
        if stop_loss_enabled and profit_pct < 0:
            levels_str = self.config.get('Sell', 'stop_loss_levels', fallback='')
            for level in levels_str.split(','):
                if ':' not in level:
                    continue
                loss_pct_str, sell_ratio_str = level.split(':')
                loss_pct = float(loss_pct_str)
                sell_ratio = float(sell_ratio_str)
                if profit_pct <= loss_pct:
                    sell_shares = int(shares * sell_ratio / 100) * 100
                    if sell_shares >= 100:
                        return sell_shares, f"固定止损触发 (盈亏 {profit_pct*100:.1f}%)"
            return 0, None

        if take_profit_enabled and profit_pct > 0:
            levels_str = self.config.get('Sell', 'take_profit_levels', fallback='')
            for level in levels_str.split(','):
                if ':' not in level:
                    continue
                gain_pct_str, sell_ratio_str = level.split(':')
                gain_pct = float(gain_pct_str)
                sell_ratio = float(sell_ratio_str)
                if profit_pct >= gain_pct:
                    sell_shares = int(shares * sell_ratio / 100) * 100
                    if sell_shares >= 100:
                        return sell_shares, f"固定止盈触发 (盈亏 {profit_pct*100:.1f}%)"
            return 0, None

        return 0, None