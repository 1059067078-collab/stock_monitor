import pandas as pd
import numpy as np
from configparser import ConfigParser

class Strategy:
    def __init__(self, config=None):
        self.config = config or ConfigParser()
        self.fast_ma = self.config.getint('Strategy', 'fast_ma', fallback=5)
        self.slow_ma = self.config.getint('Strategy', 'slow_ma', fallback=20)
        self.long_ma = self.config.getint('Strategy', 'long_ma', fallback=60)
        self.rsi_period = self.config.getint('Strategy', 'rsi_period', fallback=14)
        self.volume_ma = self.config.getint('Strategy', 'volume_ma', fallback=20)
        self.atr_period = self.config.getint('ATR', 'atr_period', fallback=14)
        self.enable_trend_filter = self.config.getboolean('Filter', 'enable_trend_filter', fallback=False)
        self.market_index = self.config.get('Filter', 'market_index', fallback='000300.SH')
        self.market_long_ma = self.config.getint('Filter', 'market_long_ma', fallback=60)

    def compute_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def compute_atr(self, high, low, close, period=14):
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def is_uptrend(self, prices, ma_period=60):
        if len(prices) < ma_period + 5:
            return True
        ma = prices.rolling(ma_period).mean()
        ma_up = ma.iloc[-1] > ma.iloc[-6] if len(ma) >= 6 else True
        price_above_ma = prices.iloc[-1] > ma.iloc[-1]
        return ma_up and price_above_ma

    def generate_signal(self, hist_df, current_price, current_volume, market_df=None):
        if hist_df is None or len(hist_df) < self.long_ma:
            return 'hold', '数据不足', None

        df = hist_df.copy()
        df['ma_fast'] = df['close'].rolling(self.fast_ma).mean()
        df['ma_slow'] = df['close'].rolling(self.slow_ma).mean()
        df['ma_long'] = df['close'].rolling(self.long_ma).mean()
        df['volume_ma'] = df['volume'].rolling(self.volume_ma).mean()
        df['rsi'] = self.compute_rsi(df['close'], self.rsi_period)
        df['atr'] = self.compute_atr(df['high'], df['low'], df['close'], self.atr_period)

        latest_ma_fast = df['ma_fast'].iloc[-1]
        latest_ma_slow = df['ma_slow'].iloc[-1]
        latest_ma_long = df['ma_long'].iloc[-1]
        latest_rsi = df['rsi'].iloc[-1]
        latest_volume_ma = df['volume_ma'].iloc[-1]
        latest_atr = df['atr'].iloc[-1]

        prev_ma_fast = df['ma_fast'].iloc[-2] if len(df) > 1 else latest_ma_fast
        prev_ma_slow = df['ma_slow'].iloc[-2] if len(df) > 1 else latest_ma_slow

        price = current_price
        volume = current_volume

        stock_uptrend = self.is_uptrend(df['close'], self.long_ma)

        market_uptrend = True
        if self.enable_trend_filter and market_df is not None:
            market_uptrend = self.is_uptrend(market_df['close'], self.market_long_ma)

        buy_conditions = []
        if prev_ma_fast <= prev_ma_slow and latest_ma_fast > latest_ma_slow:
            buy_conditions.append("5日均线上穿20日均线")
        if price > latest_ma_long:
            buy_conditions.append("价格站上60日均线")
        if latest_rsi < 70:
            buy_conditions.append(f"RSI={latest_rsi:.1f}<70")
        if volume > latest_volume_ma * 1.2:
            buy_conditions.append("成交量放大20%")
        if stock_uptrend:
            buy_conditions.append("个股处于上升趋势")
        if market_uptrend:
            buy_conditions.append("大盘处于上升趋势")

        sell_conditions = []
        if prev_ma_fast >= prev_ma_slow and latest_ma_fast < latest_ma_slow:
            sell_conditions.append("5日均线下穿20日均线")
        if price < latest_ma_long:
            sell_conditions.append("价格跌破60日均线")
        if latest_rsi > 80:
            sell_conditions.append(f"RSI超买({latest_rsi:.1f}>80)")
        if volume < latest_volume_ma * 0.5:
            sell_conditions.append("成交量萎缩50%")

        if len(buy_conditions) >= 4:
            signal = 'buy'
            reason = '买入信号：' + '；'.join(buy_conditions)
        elif len(sell_conditions) >= 2:
            signal = 'sell'
            reason = '卖出信号：' + '；'.join(sell_conditions)
        else:
            signal = 'hold'
            reason = '持有观望'

        reason += f"；ATR={latest_atr:.2f}"
        return signal, reason, latest_atr