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
)
from core.calculator import (
    calculate_cost_per_task,
    calculate_revenue,
    build_cost_volume_dataframe,
    build_pnl_snapshot,
)

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

# ── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("AgEcon Simulator")
st.sidebar.caption("Unit Economics for Agentic AI")

st.sidebar.header("Model Configuration")

model_name = st.sidebar.selectbox(
    "AI Model",
    options=list(MODEL_REGISTRY.keys()),
    key="model_name",
)
model_config = MODEL_REGISTRY[model_name]

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

st.sidebar.header("Revenue Model")

revenue_label = st.sidebar.radio(
    "Pricing Strategy",
    options=["Task-Based", "Subscription (Seat)"],
    key="revenue_model",
)
revenue_model = "task_based" if revenue_label == "Task-Based" else "subscription"

price_per_task = 0.0
seat_price = 0.0
num_seats = 0

if revenue_model == "task_based":
    price_per_task = st.sidebar.number_input(
        "Price per Task (USD)",
        min_value=0.01,
        value=DEFAULT_PRICE_PER_TASK,
        step=0.10,
        key="price_per_task",
    )
else:
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

# ── Calculations ─────────────────────────────────────────────────────────────

cost_per_task = calculate_cost_per_task(
    input_tokens=input_tokens,
    loop_tokens=loop_tokens,
    output_tokens=output_tokens,
    agentic_multiplier=agentic_multiplier,
    input_price_per_token=model_config["input_price_per_token"],
    output_price_per_token=model_config["output_price_per_token"],
)

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
)

df = build_cost_volume_dataframe(
    cost_per_task_api=cost_per_task,
    fixed_monthly_cost=fixed_monthly_cost if is_onprem else 0.0,
    price_per_task=price_per_task,
    revenue_model=revenue_model,
    seat_price=seat_price,
    num_seats=num_seats,
)

# ── Main Area ─────────────────────────────────────────────────────────────────

st.title("AgEcon Simulator")
st.caption(f"Model: **{model_name}** · Provider: {model_config['provider']} · Hosting: {hosting_label}")

# KPI Cards
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
        gm_str = "N/A"
        gm_delta = None
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
        bev_cost = fixed_monthly_cost  # at break-even, both lines intersect here
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
    yaxis_title="Cost / Revenue (USD)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=420,
    margin=dict(t=40, b=40),
)

st.plotly_chart(fig1, use_container_width=True)

# ── Chart 2: Margin Analysis ──────────────────────────────────────────────────

st.subheader("Unit Economics Snapshot — Monthly P&L at Current Volume")

gross_profit = pnl["gross_profit"]
bar_colors = ["#00CC96", "#EF553B", "#636EFA" if gross_profit >= 0 else "#FF6692"]

fig2 = go.Figure(
    data=[
        go.Bar(
            x=["Revenue", "COGS", "Gross Profit"],
            y=[pnl["revenue"], pnl["cogs"], gross_profit],
            marker_color=bar_colors,
            text=[f"${pnl['revenue']:,.0f}", f"${pnl['cogs']:,.0f}", f"${gross_profit:,.0f}"],
            textposition="outside",
        )
    ]
)

if gm is not None:
    fig2.add_annotation(
        x="Gross Profit",
        y=max(gross_profit, 0) + pnl["revenue"] * 0.05,
        text=f"<b>GM: {gm:.1f}%</b>",
        showarrow=False,
        font=dict(size=13, color="#FFD700"),
    )

fig2.update_layout(
    template="plotly_dark",
    yaxis_title="USD",
    height=380,
    margin=dict(t=40, b=40),
    showlegend=False,
)

st.plotly_chart(fig2, use_container_width=True)

# ── P&L Table ─────────────────────────────────────────────────────────────────

pnl_data = {
    "Line Item": ["Revenue", "Cost of Goods Sold (COGS)", "Gross Profit", "Gross Margin %"],
    "Amount": [
        f"${pnl['revenue']:,.2f}",
        f"(${pnl['cogs']:,.2f})",
        f"${gross_profit:,.2f}",
        f"{gm:.1f}%" if gm is not None else "N/A",
    ],
}

pnl_df = pd.DataFrame(pnl_data)


def highlight_rows(row):
    if row["Line Item"] == "Gross Profit":
        color = "#1a4a2e" if gross_profit >= 0 else "#4a1a1a"
        return [f"background-color: {color}; font-weight: bold"] * 2
    if row["Line Item"] == "Gross Margin %":
        return ["font-weight: bold"] * 2
    return [""] * 2


st.dataframe(
    pnl_df.style.apply(highlight_rows, axis=1),
    use_container_width=True,
    hide_index=True,
)
