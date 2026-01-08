import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os

# --- 1. SYSTEM STATE & THEME ENGINE ---
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if "market_mood" not in st.session_state:
    st.session_state.market_mood = "neutral"

def inject_dacati_system():
    primary = "#f97316" # Dacati Orange
    secondary = "#0ea5e9" # Dacati Blue
    
    # Background reacts to Trend State (Neural Cortex)
    mood_colors = {
        "positive": "rgba(34, 197, 94, 0.15)", 
        "negative": "rgba(239, 68, 68, 0.15)", 
        "neutral": "rgba(14, 165, 233, 0.08)"
    }
    glow = mood_colors.get(st.session_state.market_mood, mood_colors["neutral"])
    
    is_dark = st.session_state.theme == "dark"
    bg = "#0f0f0f" if is_dark else "#f4f4f5"
    text = "#ffffff" if is_dark else "#18181b"
    surface = "rgba(26, 26, 26, 0.7)" if is_dark else "rgba(255, 255, 255, 0.8)"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono&display=swap');

    .stApp {{
        background-color: {bg};
        background-image: 
            radial-gradient(circle at 20% 20%, {glow} 0%, transparent 50%),
            radial-gradient(circle at 80% 80%, {glow} 0%, transparent 50%);
        color: {text};
        font-family: 'Inter', sans-serif;
        transition: all 0.8s ease;
    }}

    /* Institutional Metric Cards */
    [data-testid="stMetric"] {{
        background: {surface} !important;
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1.5rem !important;
    }}

    /* Action Hub Container */
    .action-hub {{
        background: {surface};
        border-radius: 24px;
        padding: 30px;
        border: 1px solid rgba(255,255,255,0.1);
        margin-top: 20px;
    }}

    .footer {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background: rgba(15, 15, 15, 0.95);
        text-align: center;
        padding: 12px;
        font-size: 11px;
        letter-spacing: 2px;
        border-top: 1px solid rgba(255,255,255,0.05);
        z-index: 999;
    }}
    </style>
    """, unsafe_allow_html=True)

inject_dacati_system()

# --- 2. CORE ENGINE ---
def calculate_engine(df, period=13, multiplier=1.1):
    h, l, c = df['High'], df['Low'], df['Close']
    tr = pd.concat([h - l, abs(h - c.shift(1)), abs(l - c.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    hl2 = (h + l) / 2
    up, dn = hl2 + (multiplier * atr), hl2 - (multiplier * atr)
    
    st_line, trend = np.zeros(len(df)), np.zeros(len(df))
    for i in range(1, len(df)):
        if c.iloc[i] > up.iloc[i-1]: trend[i] = 1
        elif c.iloc[i] < dn.iloc[i-1]: trend[i] = -1
        else: trend[i] = trend[i-1]
        
        if trend[i] == 1:
            st_line[i] = max(dn.iloc[i], dn.iloc[i-1]) if trend[i-1] == 1 else dn.iloc[i]
        else:
            st_line[i] = min(up.iloc[i], up.iloc[i-1]) if trend[i-1] == -1 else up.iloc[i]
    return st_line, trend, atr

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown("### The FTI Nautilus Lite")
    st.caption("Institutional Trading Terminal")
    
    t_col1, t_col2 = st.columns(2)
    if t_col1.button("🌙 Dark", use_container_width=True): st.session_state.theme = "dark"; st.rerun()
    if t_col2.button("☀️ Light", use_container_width=True): st.session_state.theme = "light"; st.rerun()
    
    st.divider()
    st.markdown("#### MISSION CONTROL")
    ticker = st.text_input("SYMBOL", value="NVDA").upper()
    tf_map = {"1m":"1d","5m":"5d","15m":"7d","4hrs":"60d","Daily":"max","Weekly":"max"}
    tf_inv = {"1m":"1m","5m":"5m","15m":"15m","4hrs":"1h","Daily":"1d","Weekly":"1wk"}
    tf_selection = st.selectbox("TIMEFRAME", list(tf_map.keys()), index=3)
    risk_val = st.number_input("RISK EXPOSURE ($)", value=100)

# --- 4. MAIN TERMINAL DATA DISPLAY ---
st.markdown(f"## {ticker} // Trading Plan")

try:
    df = yf.download(ticker, period=tf_map[tf_selection], interval=tf_inv[tf_selection])
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        st_line, trend_dir, atr_s = calculate_engine(df)
        cp, ct, cs, ca = df['Close'].iloc[-1], trend_dir[-1], st_line[-1], atr_s.iloc[-1]
        
        # Update Market Mood
        st.session_state.market_mood = "positive" if ct == 1 else "negative"
        
        # Volatility Calc
        ap = (ca / cp) * 100
        vol_s, vol_c = ("LOW", "#39ff14") if ap <= 1.0 else ("MED", "#f97316") if ap <= 2.5 else ("HIGH", "#ff00f2") if ap <= 5.0 else ("EXTREME", "#ef4444")
        
        # Risk & Targets
        dist = abs(cp - cs)
        shares = int(risk_val / dist) if dist > 0 else 0
        tp1, tp2 = (cp + dist*1.5, cp + dist*3.0) if ct == 1 else (cp - dist*1.5, cp - dist*3.0)

        # HUD DISPLAY
        h1, h2, h3 = st.columns(3)
        h1.metric("MARKET PRICE", f"{cp:,.2f}")
        h2.metric("SIGNAL BIAS", "BULLISH" if ct == 1 else "BEARISH", delta="LONG" if ct == 1 else "SHORT")
        h3.metric("ATR (13)", f"{ca:.2f}")

        # DEPLOYMENT HUB (Card Replacement for Chart)
        st.markdown(f"""
            <div class="action-hub">
                <h3 style='margin-top:0; color:#f97316;'>ACTIVE DEPLOYMENT STRATEGY</h3>
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 20px;'>
                    <div style='background:rgba(255,255,255,0.03); padding:20px; border-radius:12px; border:1px solid rgba(255,255,255,0.05);'>
                        <p style='color:#888; margin-bottom:5px; font-size:12px;'>RISK PARAMETERS</p>
                        <p style='margin:5px 0;'><b>STOP LOSS:</b> <span style='color:#ef4444;'>{cs:,.2f}</span></p>
                        <p style='margin:5px 0;'><b>UNIT SIZE:</b> {shares} Units</p>
                        <p style='margin:5px 0;'><b>VOLATILITY:</b> <span style='color:{vol_c};'>{vol_s} ({ap:.2f}%)</span></p>
                    </div>
                    <div style='background:rgba(255,255,255,0.03); padding:20px; border-radius:12px; border:1px solid rgba(255,255,255,0.05);'>
                        <p style='color:#888; margin-bottom:5px; font-size:12px;'>PROFIT TARGETS</p>
                        <p style='margin:5px 0;'><b>TARGET 1 (1.5R):</b> <span style='color:#39ff14;'>{tp1:,.2f}</span></p>
                        <p style='margin:5px 0;'><b>TARGET 2 (3.0R):</b> <span style='color:#bcff00;'>{tp2:,.2f}</span></p>
                        <p style='margin:5px 0;'><b>RR RATIO:</b> 1 : 3.0</p>
                    </div>
                </div>
                <div style='margin-top:20px; padding:15px; border-radius:12px; background:rgba(249, 115, 22, 0.1); border:1px solid #f97316;'>
                    <p style='margin:0; font-size:13px; color:#f97316;'><b>EXECUTION ADVISORY:</b> Trend is currently {'BULLISH' if ct==1 else 'BEARISH'}. 
                    Ensure entry is validated by institutional volume profiles at {cp:,.2f}.</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"SYSTEM FAULT: {e}")

# --- 5. FOOTER ---
st.markdown(f"""
    <div class="footer">
        Powered By <a href="https://Fibonaccis-Traders.com" target="_blank" style="color:#f97316; text-decoration:none; font-weight:bold;">Fibonaccis-Traders.com</a>
    </div>
""", unsafe_allow_html=True)