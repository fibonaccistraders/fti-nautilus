import gradio as gr
import yfinance as yf
import pandas as pd
import numpy as np


# --- CORE TRADING ENGINE (UNCHANGED) ---

def calculate_nautilus(ticker, timeframe, risk_usd):
    tf_map = {
        "1m": "1d",
        "5m": "5d",
        "15m": "7d",
        "4hrs": "60d",
        "Daily": "max",
        "Weekly": "max",
    }
    tf_inv = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "4hrs": "1h",
        "Daily": "1d",
        "Weekly": "1wk",
    }

    try:
        df = yf.download(
            ticker,
            period=tf_map[timeframe],
            interval=tf_inv[timeframe],
            auto_adjust=False,
            progress=False,
        )
    except Exception as e:
        return f"Error downloading data: {e}", None, None, None

    if df.empty:
        return "Error: No data found for ticker.", None, None, None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # SuperTrend & ATR Logic
    h, l, c = df["High"], df["Low"], df["Close"]

    tr = pd.concat(
        [
            h - l,
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.rolling(13).mean()
    hl2 = (h + l) / 2
    up = hl2 + (1.1 * atr)
    dn = hl2 - (1.1 * atr)

    st_line = np.zeros(len(df))
    trend = np.zeros(len(df))

    for i in range(1, len(df)):
        if c.iloc[i] > up.iloc[i - 1]:
            trend[i] = 1
        elif c.iloc[i] < dn.iloc[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]

        if trend[i] == 1:
            st_line[i] = (
                max(dn.iloc[i], dn.iloc[i - 1]) if trend[i - 1] == 1 else dn.iloc[i]
            )
        else:
            st_line[i] = (
                min(up.iloc[i], up.iloc[i - 1]) if trend[i - 1] == -1 else up.iloc[i]
            )

    # Extract latest values
    cp = df["Close"].iloc[-1]
    ct = trend[-1]
    cs = st_line[-1]
    ca = atr.iloc[-1]

    # Volatility
    ap = (ca / cp) * 100
    if ap <= 1.0:
        vol_s = "LOW"
    elif ap <= 2.5:
        vol_s = "MED"
    elif ap <= 5.0:
        vol_s = "HIGH"
    else:
        vol_s = "EXTREME"

    # Risk & Targets
    dist = abs(cp - cs)
    shares = int(risk_usd / dist) if dist > 0 else 0

    if ct == 1:
        tp1 = cp + dist * 1.5
        tp2 = cp + dist * 3.0
    else:
        tp1 = cp - dist * 1.5
        tp2 = cp - dist * 3.0

    bias = "BULLISH 🟢" if ct == 1 else "BEARISH 🔴"

    plan_md = f"""
### SIGNAL BIAS: {bias}

**MARKET PRICE:** ${cp:,.2f}

**ATR (13):** {ca:.2f}

**VOLATILITY:** {vol_s} ({ap:.2f}%)

**STOP LOSS:** ${cs:,.2f}

**UNIT SIZE:** {shares} Units

**TARGET 1 (1.5R):** ${tp1:,.2f}

**TARGET 2 (3.0R):** ${tp2:,.2f}
"""

    return plan_md, cp, cs, tp1


# --- GRADIO TERMINAL UI ---

def build_interface():
    # Custom CSS for institutional terminal look
    custom_css = """
    .sidebar {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid rgba(255, 121, 0, 0.2);
    }
    .brand-block {
        background: linear-gradient(135deg, rgba(255, 121, 0, 0.1) 0%, rgba(0, 173, 181, 0.1) 100%);
        border-radius: 12px;
        padding: 16px;
        border: 2px solid rgba(255, 121, 0, 0.3);
        text-align: center;
        margin-bottom: 20px;
    }
    .guardian-card {
        background: rgba(30, 30, 46, 0.8);
        border-radius: 12px;
        padding: 16px;
        border: 1px solid rgba(0, 255, 0, 0.3);
        margin-bottom: 16px;
    }
    .tier-card {
        background: rgba(30, 30, 46, 0.8);
        border-radius: 12px;
        padding: 16px;
        border: 1px solid rgba(255, 121, 0, 0.4);
        margin-bottom: 16px;
    }
    .conviction-strip {
        background: linear-gradient(90deg, rgba(255, 121, 0, 0.15) 0%, rgba(0, 173, 181, 0.15) 100%);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 20px;
        border-left: 4px solid #FF7900;
    }
    .signal-card {
        background: rgba(30, 30, 46, 0.6);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    .status-pill {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .status-active {
        background: rgba(0, 255, 0, 0.2);
        color: #00ff00;
        border: 1px solid #00ff00;
    }
    .status-locked {
        background: rgba(255, 0, 0, 0.2);
        color: #ff6b6b;
        border: 1px solid #ff6b6b;
    }
    """

    theme = gr.themes.Glass(
        primary_hue="orange",
        secondary_hue="blue",
        neutral_hue="slate",
    ).set(
        body_background_fill="linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%)",
        block_background_fill="rgba(30, 30, 46, 0.4)",
        block_border_color="rgba(255, 121, 0, 0.2)",
    )

    with gr.Blocks(theme=theme, css=custom_css, title="FTI Nautilus – Institutional Trading Terminal") as app:
        
        # State management
        current_tier = gr.State("Trial")
        guardian_active = gr.State(True)
        automation_enabled = gr.State(False)
        
        with gr.Row():
            # LEFT SIDEBAR (~25%)
            with gr.Column(scale=1, elem_classes="sidebar"):
                # Brand Block
                with gr.Group(elem_classes="brand-block"):
                    gr.Markdown("# 🧭 FTI NAUTILUS")
                    gr.Markdown("*Institutional Trading Intelligence*")
                
                # Guardian Card
                with gr.Group(elem_classes="guardian-card"):
                    gr.Markdown("### 🛡️ GUARDIAN")
                    guardian_status = gr.Markdown("**Status:** <span class='status-pill status-active'>ACTIVE</span>")
                    gr.Markdown("**Daily Loss:** -$0.00 / $500")
                    gr.Markdown("**Risk Check:** ✅ PASSED")
                
                # Tier Card
                with gr.Group(elem_classes="tier-card"):
                    gr.Markdown("### 🔰 SUBSCRIPTION")
                    tier_display = gr.Markdown("**Tier:** Trial")
                    gr.Markdown("**Days Remaining:** 14")
                    gr.Markdown("**Features:** Basic signals only")
                    upgrade_btn = gr.Button("⬆️ Upgrade Plan", variant="primary", size="sm")
                
                # Navigation (simplified)
                gr.Markdown("---")
                gr.Markdown("### 📍 NAVIGATION")
                gr.Markdown("🎯 **Nautilus Engine**")
                gr.Markdown("📊 Dashboard 🔒")
                gr.Markdown("⚡ Quick Trade 🔒")
                gr.Markdown("📈 Analytics 🔒")
                gr.Markdown("⚙️ Settings")
            
            # RIGHT MAIN CONTENT (~75%)
            with gr.Column(scale=3):
                # Conviction Strip Header
                with gr.Group(elem_classes="conviction-strip"):
                    gr.Markdown("## 🧭 NAUTILUS ENGINE")
                    with gr.Row():
                        connection_status = gr.Markdown("🟢 **Connected** | Real-time Market Data")
                        automation_toggle = gr.Checkbox(label="Automation", value=False, scale=0)
                
                # Main Signal Card
                with gr.Group(elem_classes="signal-card"):
                    gr.Markdown("### 📡 SIGNAL PARAMETERS")
                    
                    with gr.Row():
                        ticker_input = gr.Textbox(
                            label="Ticker Symbol",
                            value="AAPL",
                            placeholder="e.g., AAPL, TSLA, SPY",
                            scale=2
                        )
                        timeframe_input = gr.Dropdown(
                            choices=["1m", "5m", "15m", "4hrs", "Daily", "Weekly"],
                            label="Timeframe",
                            value="Daily",
                            scale=1
                        )
                        risk_input = gr.Number(
                            label="Risk per Trade (USD)",
                            value=100,
                            minimum=10,
                            maximum=10000,
                            scale=1
                        )
                    
                    with gr.Row():
                        generate_btn = gr.Button("🚀 Generate Nautilus Plan", variant="primary", size="lg", scale=2)
                        clear_btn = gr.Button("🗑️ Clear", variant="secondary", size="lg", scale=1)
                
                # Confirmation Modal (using Accordion as modal substitute)
                with gr.Accordion("⚠️ EXECUTION CONFIRMATION", open=False, visible=False) as confirm_modal:
                    confirm_details = gr.Markdown("")
                    with gr.Row():
                        confirm_execute_btn = gr.Button("✅ CONFIRM EXECUTE", variant="primary")
                        confirm_cancel_btn = gr.Button("❌ CANCEL", variant="secondary")
                
                # Output Card
                with gr.Group(elem_classes="signal-card"):
                    gr.Markdown("### 📊 TRADE PLAN OUTPUT")
                    plan_output = gr.Markdown("*Awaiting signal generation...*")
                
                # Risk Summary Card
                with gr.Group(elem_classes="signal-card"):
                    gr.Markdown("### ⚠️ RISK MANAGEMENT")
                    risk_summary = gr.Markdown("""
**DTFE Status:** ✅ Within limits  
**ATGS Grade:** A (Minimum: B required)  
**Guardian Lock:** 🔓 Unlocked  
**Daily Trades:** 0 / 50
                    """)

        # --- INTERACTION LOGIC ---
        
        def show_confirmation(ticker, tf, risk):
            """Show confirmation modal before generating plan"""
            confirm_text = f"""
### Review Trade Parameters

**Symbol:** {ticker}  
**Timeframe:** {tf}  
**Risk Amount:** ${risk:.2f}  
**Guardian Status:** Active ✅  

⚠️ **This will generate a live trading signal. Confirm to proceed.**
            """
            return {
                confirm_modal: gr.Accordion(open=True, visible=True),
                confirm_details: confirm_text
            }
        
        def execute_plan(ticker, tf, risk):
            """Execute the Nautilus engine"""
            plan, cp, cs, tp1 = calculate_nautilus(ticker, tf, risk)
            return {
                plan_output: plan,
                confirm_modal: gr.Accordion(open=False, visible=False)
            }
        
        def cancel_execution():
            """Cancel the execution"""
            return {
                confirm_modal: gr.Accordion(open=False, visible=False)
            }
        
        def clear_outputs():
            """Clear all outputs"""
            return {
                plan_output: "*Awaiting signal generation...*",
                ticker_input: "AAPL",
                timeframe_input: "Daily",
                risk_input: 100
            }
        
        def toggle_automation(enabled):
            """Toggle automation state"""
            status = "🟢 **Automation ENABLED**" if enabled else "🔴 **Automation DISABLED**"
            return status
        
        # Wire up interactions
        generate_btn.click(
            fn=show_confirmation,
            inputs=[ticker_input, timeframe_input, risk_input],
            outputs=[confirm_modal, confirm_details]
        )
        
        confirm_execute_btn.click(
            fn=execute_plan,
            inputs=[ticker_input, timeframe_input, risk_input],
            outputs=[plan_output, confirm_modal]
        )
        
        confirm_cancel_btn.click(
            fn=cancel_execution,
            outputs=[confirm_modal]
        )
        
        clear_btn.click(
            fn=clear_outputs,
            outputs=[plan_output, ticker_input, timeframe_input, risk_input]
        )
        
        upgrade_btn.click(
            fn=lambda: gr.Info("Upgrade modal would open here (Stripe integration required)"),
            inputs=None,
            outputs=None
        )

    return app


if __name__ == "__main__":
    app = build_interface()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
