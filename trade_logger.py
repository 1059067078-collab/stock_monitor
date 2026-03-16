import csv
import os
from datetime import datetime

class TradeLogger:
    def __init__(self, log_file='trade_log.csv'):
        self.log_file = log_file
        self._ensure_header()

    def _ensure_header(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['时间', '股票代码', '操作', '价格', '数量', '金额', '持仓成本', '盈亏', '盈亏百分比'])

    def log(self, code, action, price, shares, cost_before, profit=0, profit_pct=0):
        amount = shares * price
        with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                code,
                action,
                f'{price:.2f}',
                shares,
                f'{amount:.2f}',
                f'{cost_before:.2f}',
                f'{profit:+.2f}',
                f'{profit_pct:+.1f}%'
            ])