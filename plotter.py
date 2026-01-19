import mplfinance as mpf
import pandas as pd
import io
import matplotlib.pyplot as plt
import matplotlib

# Try to set Chinese font support
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'WenQuanYi Micro Hei', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

def plot_kline(history_data, title="K-Line"):
    if not history_data:
        return None
        
    data = []
    for h in history_data:
        # Ensure timestamp is formatted correctly
        ts = h.timestamp.strftime('%Y-%m-%d %H:%M')
        data.append({
            'Date': ts,
            'Open': h.open,
            'High': h.high,
            'Low': h.low,
            'Close': h.close,
            'Volume': h.volume
        })
    
    df = pd.DataFrame(data)
    # Convert 'Date' to datetime index
    df.index = pd.DatetimeIndex(df['Date'])
    
    buf = io.BytesIO()
    # Use non-interactive backend
    plt.switch_backend('Agg')
    
    # Custom Style: Red for Up, Green for Down (China Standard)
    mc = mpf.make_marketcolors(up='r', down='g', edge='i', wick='i', volume='in', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)
    
    try:
        # Use returnfig=True to allow adding text
        # datetime_format ensures X-axis is readable
        fig, axlist = mpf.plot(df, type='candle', style=s, title=title, volume=True, 
                               datetime_format='%m-%d %H:%M', returnfig=True)
        
        # Add Legend/Explanation in Chinese
        ax = axlist[0]
        legend_text = "图例说明:\n🟥 红色: 涨 (Up)\n🟩 绿色: 跌 (Down)\nO:开盘 H:最高\nL:最低 C:收盘"
        
        # Add text box at top left
        ax.text(0.02, 0.98, legend_text, transform=ax.transAxes, fontsize=9, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
        
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        print(f"Plot error: {e}")
        return None

def plot_holdings_multi(balance, holdings_data, title="User Holdings"):
    """
    holdings_data: dict {symbol: value}
    """
    labels = ['Cash']
    sizes = [balance]
    
    for sym, val in holdings_data.items():
        labels.append(sym)
        sizes.append(val)
    
    # Avoid empty pie if all are 0
    if sum(sizes) < 0.001:
        sizes = [1]
        labels = ['Empty']

    plt.switch_backend('Agg')
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
    ax.axis('equal')
    plt.title(title)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return buf
