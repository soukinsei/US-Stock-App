import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 設定網頁標題與排版
st.set_page_config(
    page_title="美股智慧看盤與損益試算系統",
    page_icon="🇺🇸",
    layout="centered"
)

st.title("🇺🇸 美股智慧看盤與損益試算")
st.markdown("輸入美股代碼，即時分析**週 KD、RSI、成交量動態（2倍量增 / 0.5倍量縮）與均線分析**，並試算您的庫存損益！")

# ==========================================
# 側邊欄：使用者輸入區
# ==========================================
st.sidebar.header("🔍 查詢設定")
stock_code = st.sidebar.text_input("美股代碼", value="NVDA", max_chars=10).strip().upper()

st.sidebar.markdown("---")
st.sidebar.header("💰 庫存損益試算 (選填)")
enable_pnl = st.sidebar.checkbox("啟用損益試算", value=False)
buy_price = 0.0
shares = 0.0

if enable_pnl:
    buy_price = st.sidebar.number_input("平均買進成本 (美元)", min_value=0.0, value=120.0, step=1.0)
    shares = st.sidebar.number_input("持有股數", min_value=0.0, value=10.0, step=1.0)

query_btn = st.sidebar.button("開始分析", type="primary")

# ==========================================
# 主程式邏輯
# ==========================================
if query_btn or stock_code:
    ticker_symbol = stock_code
    
    with st.spinner(f"正在載入 {ticker_symbol} 歷史數據..."):
        try:
            stock = yf.Ticker(ticker_symbol)
            df = stock.history(period="6mo")
            
            if df.empty:
                st.error(f"⚠️ 查無美股代碼 `{stock_code}` 的資料，請確認美股代碼是否正確（例如 NVIDIA 請輸入 NVDA、蘋果請輸入 AAPL）。")
                st.stop()
        except Exception as e:
            st.error(f"連線或抓取資料失敗: {e}")
            st.stop()

    # 1. 成交量與 2 倍量增 / 0.5 倍量縮計算
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
    latest_volume = df['Volume'].iloc[-1]
    avg_volume_5 = df['Vol_MA5'].iloc[-2] if len(df) > 5 else latest_volume
    
    is_volume_2x = latest_volume >= (avg_volume_5 * 2)
    is_volume_shrink_05 = latest_volume <= (avg_volume_5 * 0.5)

    # 日均線計算 (MA5, MA20)
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()

    # 2. 14 日 RSI 計算
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    latest_rsi = df['RSI'].iloc[-1]

    # 3. 週 KD 與週均線計算
    df_weekly = df.resample('W').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

    low_9 = df_weekly['Low'].rolling(window=9).min()
    high_9 = df_weekly['High'].rolling(window=9).max()
    rsv = (df_weekly['Close'] - low_9) / (high_9 - low_9) * 100
    df_weekly['K'] = rsv.ewm(com=2, adjust=False).mean()
    df_weekly['D'] = df_weekly['K'].ewm(com=2, adjust=False).mean()
    
    # 週均線 (MA5w, MA20w)
    df_weekly['MA5w'] = df_weekly['Close'].rolling(window=5).mean()
    df_weekly['MA20w'] = df_weekly['Close'].rolling(window=20).mean()

    latest_k = df_weekly['K'].iloc[-1]
    latest_d = df_weekly['D'].iloc[-1]
    prev_k = df_weekly['K'].iloc[-2]
    prev_d = df_weekly['D'].iloc[-2]

    kd_signal = "盤整無交叉"
    signal_color = "normal"
    if prev_k <= prev_d and latest_k > latest_d:
        kd_signal = "🟢 週 KD 黃金交叉 (K 向上穿越 D)"
        signal_color = "success"
    elif prev_k >= prev_d and latest_k < latest_d:
        kd_signal = "🔴 週 KD 死亡交叉 (K 向下跌破 D)"
        signal_color = "error"

    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close) * 100

    # ==========================================
    # 畫面呈現 (Metrics 區塊)
    # ==========================================
    st.markdown(f"### 📊 【美股代碼: {stock_code}】技術分析報告")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("最新收盤價", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
    col2.metric("14日 RSI", f"{latest_rsi:.2f}")
    col3.metric("週 K / D 值", f"{latest_k:.1f} / {latest_d:.1f}")

    # 訊號狀態提示
    if signal_color == "success":
        st.success(f"**指標狀態**：{kd_signal}")
    elif signal_color == "error":
        st.error(f"**指標狀態**：{kd_signal}")
    else:
        st.info(f"**指標狀態**：{kd_signal}")

    # 成交量警示
    st.markdown("#### 📈 成交量動態")
    v_col1, v_col2 = st.columns(2)
    v_col1.metric("今日成交量", f"{latest_volume:,.0f} 股")
    v_col2.metric("近5日均量", f"{avg_volume_5:,.0f} 股")

    if is_volume_2x:
        st.warning("🔥 **【成交量警示】** 今日成交量放大達 2 倍以上（量增）！")
    elif is_volume_shrink_05:
        st.info("❄️ **【成交量提示】** 今日成交量量縮至 0.5 倍以下（低於 5 日均量的 50%）。")
    else:
        st.info("💡 **【成交量提示】** 今日成交量處於一般常態區間。")

    # ==========================================
    # 損益試算結果呈現
    # ==========================================
    if enable_pnl and shares > 0:
        st.markdown("---")
        st.markdown("### 💰 庫存損益試算結果")
        total_cost = buy_price * shares
        market_value = current_price * shares
        gross_profit = market_value - total_cost
        return_rate = (gross_profit / total_cost) * 100

        p1, p2, p3 = st.columns(3)
        p1.metric("持有部位總成本", f"US$ {total_cost:,.2f}")
        p2.metric("目前總市值", f"US$ {market_value:,.2f}")
        p3.metric("未實現損益", f"US$ {gross_profit:+,.2f}", f"{return_rate:+.2f}%")

    # ==========================================
    # 技術指標圖表繪製 (含日/週均線、KD、RSI)
    # ==========================================
    st.markdown("---")
    st.markdown("### 📉 技術指標與均線圖表分析")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📉 收盤價與日均線", 
        "📅 週均線走勢", 
        "📊 週 KD 指標", 
        "📈 14 日 RSI"
    ])

    with tab1:
        st.caption("每日收盤價走勢與日均線（包含 MA5、MA20）")
        st.line_chart(df[['Close', 'MA5', 'MA20']])

    with tab2:
        st.caption("週收盤價走勢與週均線（包含 MA5w、MA20w）")
        st.line_chart(df_weekly[['Close', 'MA5w', 'MA20w']])

    with tab3:
        st.caption("週 K 線與 D 線雙線對比圖（藍線：K值，橘線：D值）")
        st.line_chart(df_weekly[['K', 'D']])

    with tab4:
        st.caption("14 日 RSI 走勢圖（70 以上超買，30 以下超賣）")
        st.line_chart(df['RSI'])