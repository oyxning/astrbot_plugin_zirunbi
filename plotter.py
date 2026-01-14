import mplfinance as mpf
import pandas as pd
import io
import matplotlib.pyplot as plt

def plot_kline(history_data, title="K-Line"):
    if not history_data:
        return None
        
    data = []
    for h in history_data:
        # Ensure timestamp is string for mpf to handle it correctly without auto-conversion issues
        # h.timestamp should be timezone-aware (China Time) if coming from database.py logic
        # But if sqlite stored it naive, we might need to assume it's China time.
        # Since we want "reality China time" on chart, formatting it explicitly is safest.
        
        # If h.timestamp is naive, it's already China time (as stored).
        # If it's aware, strftime works too.
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
    
    try:
        mpf.plot(df, type='candle', style='charles', title=title, volume=True, savefig=buf, datetime_format='%Y-%m-%d %H:%M')
        buf.seek(0)
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
