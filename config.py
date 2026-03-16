import json
import os

CONFIG_FILE = "stocks.json"
DEFAULT_STOCKS = ["000001", "600519"]

def load_stocks():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        save_stocks(DEFAULT_STOCKS)
        return DEFAULT_STOCKS.copy()

def save_stocks(stocks):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(stocks, f)

def add_stock(code):
    stocks = load_stocks()
    if code not in stocks:
        stocks.append(code)
        save_stocks(stocks)
        return True
    return False

def remove_stock(code):
    stocks = load_stocks()
    if code in stocks:
        stocks.remove(code)
        save_stocks(stocks)
        return True
    return False

def list_stocks():
    return load_stocks()