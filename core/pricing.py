import json
import urllib.request
import streamlit as st

from core.constants import MODEL_REGISTRY

LITELLM_PRICING_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)

# Maps our display names to litellm model IDs in the pricing JSON
MODEL_TO_LITELLM_ID: dict[str, str] = {
    "GPT-4o": "gpt-4o",
    "GPT-4o mini": "gpt-4o-mini",
    "o1": "o1",
    "o3 mini": "o3-mini",
    "Claude 3.5 Haiku": "claude-3-5-haiku-20241022",
    "Claude 3.5 Sonnet": "claude-3-5-sonnet-20241022",
    "Claude 3.7 Sonnet": "claude-3-7-sonnet-20250219",
    "Claude 3 Opus": "claude-3-opus-20240229",
    "Gemini 2.0 Flash": "gemini/gemini-2.0-flash",
    "Gemini 1.5 Flash": "gemini/gemini-1.5-flash",
    "Gemini 1.5 Pro": "gemini/gemini-1.5-pro",
    "Llama 3 (API)": "together_ai/togethercomputer/llama-3-8b-chat",
    "Llama 3.1 405B (API)": "together_ai/meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
    "Mistral Small": "mistral/mistral-small-latest",
    "Mistral Large": "mistral/mistral-large-latest",
    "DeepSeek V3": "deepseek/deepseek-chat",
    "DeepSeek R1": "deepseek/deepseek-reasoner",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_live_pricing() -> dict | None:
    """Fetch latest LLM pricing from litellm's public database. Cached for 1 hour."""
    try:
        with urllib.request.urlopen(LITELLM_PRICING_URL, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def build_model_registry(live_data: dict | None) -> tuple[dict, int]:
    """
    Merge live prices into a copy of MODEL_REGISTRY.

    Returns (registry, live_count) where live_count is the number of models
    whose prices were successfully updated from the live source.
    """
    registry = {name: {**info} for name, info in MODEL_REGISTRY.items()}
    live_count = 0

    if live_data is None:
        return registry, live_count

    for display_name, litellm_id in MODEL_TO_LITELLM_ID.items():
        if display_name not in registry:
            continue
        model_data = live_data.get(litellm_id)
        if model_data is None:
            continue
        input_cost = model_data.get("input_cost_per_token")
        output_cost = model_data.get("output_cost_per_token")
        if input_cost is not None and output_cost is not None:
            registry[display_name] = {
                **registry[display_name],
                "input_price_per_token": float(input_cost),
                "output_price_per_token": float(output_cost),
            }
            live_count += 1

    return registry, live_count
