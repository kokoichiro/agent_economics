import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from core.constants import (
    MODEL_REGISTRY,
    DEFAULT_INPUT_TOKENS,
    DEFAULT_LOOP_TOKENS,
    DEFAULT_OUTPUT_TOKENS,
    DEFAULT_AGENTIC_MULTIPLIER,
    DEFAULT_VOLUME,
    VOLUME_RANGE_MAX,
    DEFAULT_ONPREM_MONTHLY_COST,
    DEFAULT_SEAT_PRICE,
    DEFAULT_NUM_SEATS,
    DEFAULT_PRICE_PER_TASK,
    DEFAULT_MARKUP_MULTIPLIER,
    DEFAULT_OPEX_MONTHLY,
    DEFAULT_TAX_RATE,
)
from core.calculator import (
    calculate_cost_per_task,
    calculate_revenue,
    build_cost_volume_dataframe,
    build_pnl_snapshot,
)
from core.pricing import fetch_live_pricing, build_model_registry

st.set_page_config(
    page_title="AgEcon Simulator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em; }
    .block-container { padding-top: 1.5rem; }
    .stAlert { border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Live Pricing ──────────────────────────────────────────────────────────────

st.sidebar.title("AgEcon Simulator")
st.sidebar.caption("Unit Economics for Agentic AI")

st.sidebar.header("LLM Pricing")

col_refresh, col_status = st.sidebar.columns([1, 2])
with col_refresh:
    if st.button("Refresh", key="refresh_pricing", help="Fetch latest prices from litellm"):
        fetch_live_pricing.clear()
        st.rerun()

live_data = fetch_live_pricing()
dynamic_registry, live_count = build_model_registry(live_data)

with col_status:
    if live_data is not None:
        st.success(f"Live ({live_count} models)", icon="✓")
    else:
        st.warning("Cached fallback", icon="⚠")

# ── Sidebar: Model Configuration ──────────────────────────────────────────────

st.sidebar.header("Model Configuration")

model_name = st.sidebar.selectbox(
    "AI Model",
    options=list(dynamic_registry.keys()),
    key="model_name",
)
model_config = dynamic_registry[model_name]

input_price = model_config["input_price_per_token"] * 1_000_000
output_price = model_config["output_price_per_token"] * 1_000_000
st.sidebar.caption(
    f"Input: **${input_price:.4f}** / 1M tokens · Output: **${output_price:.4f}** / 1M tokens"
)

agentic_multiplier = st.sidebar.slider(
    "Agentic Multiplier (μ)",
    min_value=1.0,
    max_value=50.0,
    value=DEFAULT_AGENTIC_MULTIPLIER,
    step=0.5,
    key="agentic_multiplier",
    help="Number of internal reasoning/tool-call loops per user request.",
)

input_tokens = st.sidebar.number_input(
    "Input Tokens per Request",
    min_value=1,
    max_value=100_000,
    value=DEFAULT_INPUT_TOKENS,
    step=100,
    key="input_tokens",
)
loop_tokens = st.sidebar.number_input(
    "Loop Tokens per Iteration",
    min_value=0,
    max_value=100_000,
    value=DEFAULT_LOOP_TOKENS,
    step=100,
    key="loop_tokens",
)
output_tokens = st.sidebar.number_input(
    "Output Tokens per Request",
    min_value=1,
    max_value=100_000,
    value=DEFAULT_OUTPUT_TOKENS,
    step=100,
    key="output_tokens",
)

# ── Sidebar: Hosting Strategy ─────────────────────────────────────────────────

st.sidebar.header("Hosting Strategy")

hosting_label = st.sidebar.radio(
    "Deployment Model",
    options=["API (Variable Cost)", "On-Premises (Fixed + Marginal)"],
    key="hosting_strategy",
)
is_onprem = hosting_label == "On-Premises (Fixed + Marginal)"
hosting_strategy = "onprem" if is_onprem else "api"

fixed_monthly_cost = 0.0
if is_onprem:
    fixed_monthly_cost = st.sidebar.number_input(
        "Fixed Monthly Cost (USD)",
        min_value=0.0,
        value=DEFAULT_ONPREM_MONTHLY_COST,
        step=500.0,
        key="fixed_monthly_cost",
        help="GPU node lease, depreciation, and operations cost per month.",
    )

# ── Sidebar: Revenue Model ────────────────────────────────────────────────────

st.sidebar.header("Revenue Model")

revenue_label = st.sidebar.radio(
    "Pricing Strategy",
    options=["Task-Based", "Subscription (Seat)", "API Markup"],
    key="revenue_model",
)

price_per_task = 0.0
seat_price = 0.0
num_seats = 0
markup_multiplier = 1.0

# Compute COGS per task early so markup can reference it
_cost_per_task_preview = calculate_cost_per_task(
    input_tokens=DEFAULT_INPUT_TOKENS,
    loop_tokens=DEFAULT_LOOP_TOKENS,
    output_tokens=DEFAULT_OUTPUT_TOKENS,
    agentic_multiplier=agentic_multiplier,
    input_price_per_token=model_config["input_price_per_token"],
    output_price_per_token=model_config["output_price_per_token"],
)

if revenue_label == "Task-Based":
    revenue_model = "task_based"
    price_per_task = st.sidebar.number_input(
        "Price per Task (USD)",
        min_value=0.01,
        value=DEFAULT_PRICE_PER_TASK,
        step=0.10,
        key="price_per_task",
    )
elif revenue_label == "Subscription (Seat)":
    revenue_model = "subscription"
    seat_price = st.sidebar.number_input(
        "Monthly Seat Price (USD)",
        min_value=1.0,
        value=DEFAULT_SEAT_PRICE,
        step=1.0,
        key="seat_price",
    )
    num_seats = st.sidebar.number_input(
        "Number of Seats",
        min_value=1,
        value=DEFAULT_NUM_SEATS,
        step=10,
        key="num_seats",
    )
else:  # API Markup
    revenue_model = "task_based"
    markup_multiplier = st.sidebar.slider(
        "Markup Multiplier (×)",
        min_value=1.0,
        max_value=20.0,
        value=DEFAULT_MARKUP_MULTIPLIER,
        step=0.1,
        key="markup_multiplier",
        help="Revenue per task = Cost per task × multiplier. E.g., 3× means you charge 3x what you pay the LLM provider.",
    )
    # price_per_task will be set after cost_per_task is computed below

# ── Sidebar: Operating Expenses ───────────────────────────────────────────────

st.sidebar.header("Operating Expenses")

monthly_opex = st.sidebar.number_input(
    "Monthly OpEx (USD)",
    min_value=0.0,
    value=DEFAULT_OPEX_MONTHLY,
    step=500.0,
    key="monthly_opex",
    help="Fixed operating expenses beyond COGS: infrastructure overhead, headcount, etc.",
)

tax_rate_pct = st.sidebar.slider(
    "Tax Rate (%)",
    min_value=0,
    max_value=50,
    value=int(DEFAULT_TAX_RATE * 100),
    step=1,
    key="tax_rate",
    help="Applied to positive operating profit only.",
)
tax_rate = tax_rate_pct / 100.0

# ── Sidebar: Current Volume ───────────────────────────────────────────────────

st.sidebar.header("Current Volume")

current_volume = st.sidebar.number_input(
    "Monthly Task Volume",
    min_value=1,
    max_value=VOLUME_RANGE_MAX,
    value=DEFAULT_VOLUME,
    step=1_000,
    key="current_volume",
    help="Snapshot volume used for P&L metrics and margin analysis.",
)

# ── Calculations ──────────────────────────────────────────────────────────────

cost_per_task = calculate_cost_per_task(
    input_tokens=input_tokens,
    loop_tokens=loop_tokens,
    output_tokens=output_tokens,
    agentic_multiplier=agentic_multiplier,
    input_price_per_token=model_config["input_price_per_token"],
    output_price_per_token=model_config["output_price_per_token"],
)

# For API Markup, revenue per task = cost_per_task * multiplier
if revenue_label == "API Markup":
    price_per_task = cost_per_task * markup_multiplier

revenue_snapshot = calculate_revenue(
    revenue_model=revenue_model,
    volume=current_volume,
    price_per_task=price_per_task,
    seat_price=seat_price,
    num_seats=num_seats,
)

pnl = build_pnl_snapshot(
    volume=current_volume,
    cost_per_task_api=cost_per_task,
    fixed_monthly_cost=fixed_monthly_cost,
    revenue=revenue_snapshot,
    hosting_strategy=hosting_strategy,
    monthly_opex=monthly_opex,
    tax_rate=tax_rate,
)

df = build_cost_volume_dataframe(
    cost_per_task_api=cost_per_task,
    fixed_monthly_cost=fixed_monthly_cost if is_onprem else 0.0,
    price_per_task=price_per_task,
    revenue_model=revenue_model,
    seat_price=seat_price,
    num_seats=num_seats,
    monthly_opex=monthly_opex,
    tax_rate=tax_rate,
)

# ── Main Area ─────────────────────────────────────────────────────────────────

st.title("AgEcon Simulator")
st.caption(
    f"Model: **{model_name}** · Provider: {model_config['provider']} · "
    f"Hosting: {hosting_label} · Pricing: {'Live' if live_data else 'Cached'}"
)

# ── KPI Row 1: Cost metrics ───────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Cost per Task",
        value=f"${pnl['cost_per_task']:.4f}",
        help="Variable cost to serve one task at the current Agentic Multiplier.",
    )

with col2:
    st.metric(
        label="Monthly COGS",
        value=f"${pnl['cogs']:,.2f}",
        help="Total Cost of Goods Sold at the current monthly task volume.",
    )

with col3:
    gm = pnl["gross_margin_pct"]
    if gm is None:
        gm_str, gm_delta = "N/A", None
    else:
        gm_str = f"{gm:.1f}%"
        gm_delta = "Healthy" if gm >= 60 else ("At Risk" if gm > 0 else "Negative")
    st.metric(
        label="Gross Margin",
        value=gm_str,
        delta=gm_delta,
        delta_color="normal" if (gm or 0) > 0 else "inverse",
        help="Gross Margin % = (Revenue − COGS) / Revenue × 100",
    )

with col4:
    bev = pnl["breakeven_volume"]
    if not is_onprem:
        bev_str = "N/A (API Mode)"
    elif bev is None:
        bev_str = "N/A (API Always Cheaper)"
    else:
        bev_str = f"{int(bev):,} tasks/mo"
    st.metric(
        label="Break-even Volume",
        value=bev_str,
        help="Monthly task volume at which On-Premises cost equals API cost.",
    )

# ── KPI Row 2: Profit metrics ─────────────────────────────────────────────────

col5, col6, col7, col8 = st.columns(4)

with col5:
    st.metric(
        label="Monthly Revenue",
        value=f"${pnl['revenue']:,.2f}",
        help="Total revenue at the current monthly task volume.",
    )

with col6:
    op = pnl["operating_profit"]
    st.metric(
        label="Operating Profit",
        value=f"${op:,.2f}",
        delta="Profitable" if op > 0 else "Loss",
        delta_color="normal" if op > 0 else "inverse",
        help="Gross Profit − Monthly OpEx",
    )

with col7:
    np_val = pnl["net_profit"]
    st.metric(
        label="Net Profit",
        value=f"${np_val:,.2f}",
        delta="Profitable" if np_val > 0 else "Loss",
        delta_color="normal" if np_val > 0 else "inverse",
        help="Operating Profit − Tax",
    )

with col8:
    nm = pnl["net_margin_pct"]
    nm_str = f"{nm:.1f}%" if nm is not None else "N/A"
    nm_delta = None if nm is None else ("Healthy" if nm >= 20 else ("At Risk" if nm > 0 else "Negative"))
    st.metric(
        label="Net Margin",
        value=nm_str,
        delta=nm_delta,
        delta_color="normal" if (nm or 0) > 0 else "inverse",
        help="Net Margin % = Net Profit / Revenue × 100",
    )

# Agentic Multiplier explainer
st.info(
    "**What is the Agentic Multiplier (μ)?**  \n"
    "Traditional LLM cost models assume one round-trip per user request. Agentic systems — "
    "those that invoke tools, run iterative reasoning chains (ReAct, chain-of-thought), or "
    "orchestrate sub-agents — consume significantly more tokens internally before returning a "
    "response. The Agentic Multiplier μ captures this amplification factor. At μ = 1.0, the "
    "system behaves like a standard chatbot. At μ = 20.0, each user request internally loops "
    "20 times (e.g., planning → tool call → observation → re-planning), consuming 20× the loop "
    "token budget before producing output. **This has a non-linear effect on unit economics at scale.**"
)

# ── Chart 1: Cost vs Volume ───────────────────────────────────────────────────

st.subheader("Cost Structure Analysis: API vs On-Premises at Scale")

fig1 = go.Figure()

fig1.add_trace(
    go.Scatter(
        x=df["volume"],
        y=df["api_cost"],
        name="API Cost (Variable)",
        line=dict(color="#EF553B", width=2),
    )
)

if is_onprem:
    fig1.add_trace(
        go.Scatter(
            x=df["volume"],
            y=df["onprem_cost"],
            name="On-Prem Cost (Fixed + Marginal)",
            line=dict(color="#636EFA", width=2),
        )
    )
    fig1.add_hline(
        y=fixed_monthly_cost,
        line_dash="dash",
        line_color="#636EFA",
        opacity=0.4,
        annotation_text=f"Fixed Monthly Cost: ${fixed_monthly_cost:,.0f}",
        annotation_position="bottom right",
    )
    if bev is not None:
        fig1.add_trace(
            go.Scatter(
                x=[int(bev)],
                y=[cost_per_task * bev],
                name=f"Break-even ({int(bev):,} tasks)",
                mode="markers",
                marker=dict(symbol="star", size=16, color="#FFA500"),
            )
        )

fig1.add_trace(
    go.Scatter(
        x=df["volume"],
        y=df["revenue"],
        name="Revenue",
        line=dict(color="#00CC96", width=2),
    )
)

fig1.add_trace(
    go.Scatter(
        x=df["volume"],
        y=df["api_net_profit"],
        name="Net Profit (API)",
        line=dict(color="#AB63FA", width=2, dash="dot"),
    )
)

fig1.add_vline(
    x=current_volume,
    line_dash="dot",
    line_color="white",
    opacity=0.5,
    annotation_text=f"Current Volume: {current_volume:,}",
    annotation_position="top right",
)

fig1.update_layout(
    template="plotly_dark",
    xaxis_title="Monthly Task Volume",
    yaxis_title="Cost / Revenue / Profit (USD)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=420,
    margin=dict(t=40, b=40),
)

st.plotly_chart(fig1, use_container_width=True)

# ── Chart 2: Full P&L Bar Chart ───────────────────────────────────────────────

st.subheader("Unit Economics Snapshot — Monthly P&L at Current Volume")

gross_profit = pnl["gross_profit"]
op_profit = pnl["operating_profit"]
net_profit_val = pnl["net_profit"]

bar_labels = ["Revenue", "COGS", "Gross Profit", "OpEx", "Operating Profit", "Tax", "Net Profit"]
bar_values = [
    pnl["revenue"],
    pnl["cogs"],
    gross_profit,
    monthly_opex,
    op_profit,
    pnl["tax_amount"],
    net_profit_val,
]
bar_colors = [
    "#00CC96",  # Revenue - green
    "#EF553B",  # COGS - red
    "#636EFA" if gross_profit >= 0 else "#FF6692",  # Gross Profit
    "#FFA15A",  # OpEx - orange
    "#636EFA" if op_profit >= 0 else "#FF6692",  # Operating Profit
    "#FECB52",  # Tax - yellow
    "#19D3F3" if net_profit_val >= 0 else "#FF6692",  # Net Profit
]

fig2 = go.Figure(
    data=[
        go.Bar(
            x=bar_labels,
            y=bar_values,
            marker_color=bar_colors,
            text=[f"${v:,.0f}" for v in bar_values],
            textposition="outside",
        )
    ]
)

if nm is not None:
    fig2.add_annotation(
        x="Net Profit",
        y=max(net_profit_val, 0) + pnl["revenue"] * 0.05,
        text=f"<b>NM: {nm:.1f}%</b>",
        showarrow=False,
        font=dict(size=13, color="#FFD700"),
    )

fig2.update_layout(
    template="plotly_dark",
    yaxis_title="USD",
    height=420,
    margin=dict(t=40, b=40),
    showlegend=False,
)

st.plotly_chart(fig2, use_container_width=True)

# ── P&L Table ─────────────────────────────────────────────────────────────────

pnl_data = {
    "Line Item": [
        "Revenue",
        "Cost of Goods Sold (COGS)",
        "Gross Profit",
        "Gross Margin %",
        "Operating Expenses (OpEx)",
        "Operating Profit",
        "Tax",
        "Net Profit",
        "Net Margin %",
    ],
    "Amount": [
        f"${pnl['revenue']:,.2f}",
        f"(${pnl['cogs']:,.2f})",
        f"${gross_profit:,.2f}",
        f"{gm:.1f}%" if gm is not None else "N/A",
        f"(${monthly_opex:,.2f})",
        f"${op_profit:,.2f}",
        f"(${pnl['tax_amount']:,.2f})",
        f"${net_profit_val:,.2f}",
        f"{nm:.1f}%" if nm is not None else "N/A",
    ],
}

pnl_df = pd.DataFrame(pnl_data)


def highlight_rows(row):
    if row["Line Item"] == "Gross Profit":
        color = "#1a4a2e" if gross_profit >= 0 else "#4a1a1a"
        return [f"background-color: {color}; font-weight: bold"] * 2
    if row["Line Item"] == "Net Profit":
        color = "#1a2a4a" if net_profit_val >= 0 else "#4a1a1a"
        return [f"background-color: {color}; font-weight: bold"] * 2
    if row["Line Item"] in ("Gross Margin %", "Net Margin %"):
        return ["font-weight: bold"] * 2
    return [""] * 2


st.dataframe(
    pnl_df.style.apply(highlight_rows, axis=1),
    use_container_width=True,
    hide_index=True,
)
