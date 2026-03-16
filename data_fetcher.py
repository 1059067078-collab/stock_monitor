import akshare_proxy_patch
akshare_proxy_patch.install_patch("101.201.173.125", "", 50)
import akshare as ak
import pandas as pd
from datetime import datetime, date
import os
import time
from configparser import ConfigParser

class DataFetcher:
    _realtime_cache = None
    _realtime_cache_time = None
    _hist_cache = {}
    _trade_cal_cache = None

    def __init__(self, config=None):
        self.config = config or ConfigParser()
        self.max_retries = 3
        self.retry_delay = 5
        self.test_mode = self.config.getboolean('Filter', 'test_mode', fallback=False)

    def is_trade_day(self):
        if self.test_mode:
            return True
        if self._trade_cal_cache is not None:
            return self._trade_cal_cache
        try:
            today = datetime.now().strftime('%Y%m%d')
            df = ak.tool_trade_date_hist_sina()
            trade_dates = df['trade_date'].astype(str).tolist()
            self._trade_cal_cache = today in trade_dates
        except Exception as e:
            print(f"⚠️ 获取交易日历失败，默认进行交易: {e}")
            self._trade_cal_cache = True
        return self._trade_cal_cache

    def _fetch_with_retry(self, func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"⚠️ 数据获取失败，第{attempt+1}次重试: {e}")
                time.sleep(self.retry_delay)
        raise Exception(f"数据获取失败，已重试{self.max_retries}次")

    def get_realtime_quotes(self, codes):
        if not self.is_trade_day():
            print("📅 今日非交易日，跳过实时数据获取")
            return {}

        now = datetime.now()
        if self._realtime_cache is not None and self._realtime_cache_time is not None:
            if (now - self._realtime_cache_time).seconds <= 300:
                df = self._realtime_cache
            else:
                df = self._fetch_with_retry(ak.stock_zh_a_spot_em)
                self._realtime_cache = df
                self._realtime_cache_time = now
        else:
            df = self._fetch_with_retry(ak.stock_zh_a_spot_em)
            self._realtime_cache = df
            self._realtime_cache_time = now

        result = {}
        for code in codes:
            row = df[df['代码'] == code]
            if not row.empty:
                result[code] = {
                    'price': float(row['最新价'].iloc[0]),
                    'volume': float(row['成交量'].iloc[0]),
                    'turnover': float(row['成交额'].iloc[0]),
                    'name': row['名称'].iloc[0],
                    'time': now
                }
            else:
                result[code] = None
                print(f"⚠️ 未找到股票 {code} 的实时数据")
        return result

    def get_realtime_quote(self, code):
        quotes = self.get_realtime_quotes([code])
        return quotes.get(code)

    def get_hist_data(self, code, days=100):
        today = date.today()
        cache_file = f"hist_cache/{code}_hist.csv"

        if code in self._hist_cache:
            cached_df, fetch_date = self._hist_cache[code]
            if fetch_date == today:
                return cached_df.tail(days)

        if os.path.exists(cache_file):
            try:
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(cache_file)).date()
                if file_mod_time == today:
                    df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                    self._hist_cache[code] = (df, today)
                    return df.tail(days)
            except Exception as e:
                print(f"⚠️ 读取缓存文件失败: {e}")

        try:
            end_date = datetime.now().strftime('%Y%m%d')
            df = self._fetch_with_retry(ak.stock_zh_a_hist, symbol=code, period='daily',
                                        start_date='', end_date=end_date, adjust='qfq')
            if df.empty:
                return None

            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume'
            })
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)

            os.makedirs('hist_cache', exist_ok=True)
            df.to_csv(cache_file)
            self._hist_cache[code] = (df, today)
            return df.tail(days)
        except Exception as e:
            print(f"❌ 股票 {code} 历史数据获取失败: {e}")
            return None

    def get_index_hist(self, index_code, days=100):
        cache_file = f"hist_cache/{index_code}_hist.csv"
        today = date.today()
        if os.path.exists(cache_file):
            try:
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(cache_file)).date()
                if file_mod_time == today:
                    df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                    return df.tail(days)
            except Exception as e:
                print(f"⚠️ 读取指数缓存失败: {e}")
        try:
            df = ak.stock_zh_index_daily(symbol=index_code)
            df = df.rename(columns={'date': 'date', 'open': 'open', 'close': 'close',
                                     'high': 'high', 'low': 'low', 'volume': 'volume'})
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            os.makedirs('hist_cache', exist_ok=True)
            df.to_csv(cache_file)
            return df.tail(days)
        except Exception as e:
            print(f"❌ 获取指数 {index_code} 失败: {e}")
            return None