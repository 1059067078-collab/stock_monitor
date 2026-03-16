from datetime import datetime

def format_account_summary(account, prices):
    total_assets, total_cash, total_stock_value, total_cost, total_profit, total_profit_pct, details = account.get_summary(prices)
    lines = [
        f"💰 总资产: {total_assets:.2f} | 总现金: {total_cash:.2f} | 总持仓市值: {total_stock_value:.2f} | 总成本: {total_cost:.2f} | 总盈亏: {total_profit:+.2f} ({total_profit_pct:+.1f}%)"
    ]
    if details:
        lines.append("📈 各股票明细:")
        for code, info in details.items():
            pct = (info['total'] / total_assets * 100) if total_assets > 0 else 0
            price_str = f"{info['price']:.2f}" if info['price'] else "N/A"
            profit_str = f"{info['profit']:+.2f} ({info['profit_pct']:+.1f}%)" if info['shares'] > 0 else "--"
            lines.append(
                f"   {code}: 现金 {info['cash']:.2f} | 持仓 {info['shares']}股 @ {price_str} "
                f"= {info['stock_value']:.2f} | 成本 {info['cost']:.2f} | 盈亏 {profit_str} | 合计 {info['total']:.2f} ({pct:.1f}%)"
            )
    return "\n".join(lines)

def format_output(code, name, signal, reason):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    name_display = name if name else "未知名称"
    if signal is None:
        return f"[{timestamp}] {code}（{name_display}）：分析失败 - {reason}"
    emoji = {'buy': '🟢', 'sell': '🔴', 'hold': '⚪'}
    return f"[{timestamp}] {emoji[signal]} {code}（{name_display}） 策略建议：{signal.upper()} - {reason}"