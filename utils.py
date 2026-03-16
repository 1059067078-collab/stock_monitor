import re
from datetime import time, datetime

def normalize_stock_code(code):
    code = re.sub(r'[^0-9]', '', str(code))
    return code

def is_trading_time():
    """判断当前时间是否在交易时段内（上午9:30-11:30，下午13:00-15:00）"""
    now = datetime.now()
    current_time = now.time()
    morning_start = time(9, 30, 0)
    morning_end = time(11, 30, 0)
    afternoon_start = time(13, 0, 0)
    afternoon_end = time(15, 0, 0)
    if (morning_start <= current_time <= morning_end) or (afternoon_start <= current_time <= afternoon_end):
        return True
    return False