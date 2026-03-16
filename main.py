import threading
import time
import schedule
from datetime import datetime
from configparser import ConfigParser
from git import Repo
import os

from config import load_stocks, add_stock as config_add, remove_stock as config_remove
from analyzer import Analyzer
from output import format_output, format_account_summary
from utils import normalize_stock_code, is_trading_time

config = ConfigParser()
config.read('config.ini', encoding='utf-8')

running = True
analyzer = Analyzer(config)


def generate_html_report(account, prices, signals):
    """生成美观的HTML报告，适配手机端"""
    total_assets, total_cash, total_stock_value, total_cost, total_profit, total_profit_pct, details = account.get_summary(
        prices)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>股票监控系统</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 16px; background: #f5f7fa; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 16px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
        h1 {{ font-size: 1.6rem; margin: 0 0 8px 0; }}
        h2 {{ font-size: 1.2rem; margin: 0 0 12px 0; color: #555; }}
        .time {{ color: #888; font-size: 0.9rem; margin-bottom: 16px; }}
        .summary-item {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }}
        .summary-item:last-child {{ border-bottom: none; }}
        .label {{ color: #666; }}
        .value {{ font-weight: 600; }}
        .profit {{ color: #e74c3c; }}
        .profit.positive {{ color: #2ecc71; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
        th {{ text-align: left; background: #f0f2f5; padding: 10px 8px; }}
        td {{ padding: 8px; border-bottom: 1px solid #eee; }}
        .signal-badge {{ display: inline-block; padding: 4px 8px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }}
        .buy {{ background: #e8f5e9; color: #2e7d32; }}
        .sell {{ background: #ffebee; color: #c62828; }}
        .hold {{ background: #fff3e0; color: #ef6c00; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📈 股票监控系统</h1>
            <div class="time">更新时间：{now}</div>
            <div class="summary-item">
                <span class="label">总资产</span>
                <span class="value">{total_assets:.2f}</span>
            </div>
            <div class="summary-item">
                <span class="label">总现金</span>
                <span class="value">{total_cash:.2f}</span>
            </div>
            <div class="summary-item">
                <span class="label">持仓市值</span>
                <span class="value">{total_stock_value:.2f}</span>
            </div>
            <div class="summary-item">
                <span class="label">总盈亏</span>
                <span class="value {'positive' if total_profit >= 0 else 'profit'}">{total_profit:+.2f} ({total_profit_pct:+.1f}%)</span>
            </div>
        </div>

        <div class="card">
            <h2>📊 最新信号</h2>
            <table>
                <tr>
                    <th>代码</th><th>名称</th><th>信号</th><th>说明</th>
                </tr>
    """
    for code, sig in signals.items():
        signal_class = sig['signal'] if sig['signal'] else 'hold'
        html += f"""
                <tr>
                    <td>{code}</td>
                    <td>{sig['name']}</td>
                    <td><span class="signal-badge {signal_class}">{sig['signal'].upper() if sig['signal'] else '--'}</span></td>
                    <td>{sig['reason'][:20]}…</td>
                </tr>
        """
    html += """
            </table>
        </div>

        <div class="card">
            <h2>📋 持仓明细</h2>
            <table>
                <tr><th>代码</th><th>持仓</th><th>现价</th><th>市值</th><th>盈亏%</th></tr>
    """
    for code, info in details.items():
        profit_class = 'positive' if info['profit'] >= 0 else 'profit'
        price_str = f"{info['price']:.2f}" if info['price'] else "N/A"
        html += f"""
                <tr>
                    <td>{code}</td>
                    <td>{info['shares']}</td>
                    <td>{price_str}</td>
                    <td>{info['stock_value']:.2f}</td>
                    <td class="{profit_class}">{info['profit_pct']:+.1f}%</td>
                </tr>
        """
    html += """
            </table>
        </div>
    </div>
</body>
</html>
    """
    with open('report.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("📄 HTML报告已生成")


def push_to_github(repo_path='.'):
    """将 report.html 自动推送到 GitHub"""
    try:
        repo = Repo(repo_path)
        if repo.is_dirty(path='report.html') or 'report.html' in repo.untracked_files:
            repo.git.add('report.html')
            repo.index.commit('🤖 自动更新交易报告')
            origin = repo.remote(name='origin')
            origin.push()
            print("✅ 报告已自动推送到 GitHub")
        else:
            print("ℹ️ 报告无变化，无需推送")
    except Exception as e:
        print(f"❌ 推送失败: {e}")


def job():
    print(f"\n--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始分析 ---")
    stocks = load_stocks()
    if not stocks:
        print("⚠️ 当前没有监控股票，请先添加")
        return

    if not analyzer.fetcher.is_trade_day():
        print("📅 今日非交易日，跳过分析")
        return

    if not is_trading_time():
        print("⏰ 当前非交易时段（9:30-11:30, 13:00-15:00），等待交易时间...")
        return

    quotes = analyzer.fetcher.get_realtime_quotes(stocks)
    if not quotes:
        print("❌ 批量获取实时数据失败")
        return

    prices = {}
    signals = {}
    for code in stocks:
        realtime = quotes.get(code)
        if realtime and realtime['price']:
            prices[code] = realtime['price']
        signal, reason, name = analyzer.analyze_stock(code)
        print(format_output(code, name, signal, reason))
        if realtime:
            signals[code] = {'signal': signal, 'reason': reason, 'name': name}

    if prices:
        print(format_account_summary(analyzer.account, prices))
        generate_html_report(analyzer.account, prices, signals)
        push_to_github()
    else:
        print("⚠️ 无有效价格数据，无法计算账户市值")
    print("--- 分析完成 ---\n")


def user_input_thread():
    global running
    print("📌 命令帮助：")
    print("  add <股票代码>           - 添加股票（如 add 600519）")
    print("  remove <代码>            - 移除股票（需先清仓）")
    print("  list                     - 列出当前监控股票")
    print("  cash <代码> <金额>       - 向指定股票追加资金（如 cash 000001 5000）")
    print("  exit                     - 退出程序")
    while running:
        cmd = input(">>> ").strip()
        if not cmd:
            continue
        parts = cmd.split()
        action = parts[0].lower()
        if action == 'exit':
            print("👋 正在退出...")
            running = False
            break
        elif action == 'list':
            stocks = load_stocks()
            if stocks:
                print("📋 当前监控股票：", ", ".join(stocks))
            else:
                print("📭 暂无监控股票")
        elif action == 'add' and len(parts) >= 2:
            code = normalize_stock_code(parts[1])
            if config_add(code):
                analyzer.account.add_stock_account(code)
                print(f"✅ 已添加股票 {code}，初始现金 20000 元")
            else:
                print(f"⚠️ 股票 {code} 已在监控列表中")
        elif action == 'remove' and len(parts) >= 2:
            code = normalize_stock_code(parts[1])
            shares = analyzer.account.get_shares(code)
            if shares > 0:
                print(f"❌ 股票 {code} 仍有持仓 {shares} 股，请先卖出")
            else:
                if config_remove(code):
                    success, msg = analyzer.account.remove_stock_account(code)
                    if success:
                        print(f"✅ 已移除股票 {code}")
                    else:
                        print(f"❌ {msg}")
                else:
                    print(f"⚠️ 股票 {code} 不在监控列表中")
        elif action == 'cash' and len(parts) >= 3:
            code = normalize_stock_code(parts[1])
            try:
                amount = float(parts[2])
                msg = analyzer.account.add_cash(code, amount)
                print(f"💰 {msg}")
            except ValueError:
                print("❌ 金额必须为数字")
        else:
            print("❌ 无效命令，请重试")


def main():
    print("🚀 股票实时监控系统启动（GitHub自动部署版）")
    stocks = load_stocks()
    if stocks:
        print(f"当前监控股票：{', '.join(stocks)}")
    else:
        print("当前无监控股票，请使用 add 命令添加")

    t = threading.Thread(target=user_input_thread, daemon=True)
    t.start()

    schedule.every(5).minutes.do(job)
    schedule.run_all()

    global running
    while running:
        schedule.run_pending()
        time.sleep(1)

    print("程序已退出")


if __name__ == "__main__":
    main()