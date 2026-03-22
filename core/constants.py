MODEL_REGISTRY = {
    # ── OpenAI ────────────────────────────────────────────────────────────────
    "GPT-4o": {
        "input_price_per_token": 2.50 / 1_000_000,
        "output_price_per_token": 10.00 / 1_000_000,
        "provider": "OpenAI",
    },
    "GPT-4o mini": {
        "input_price_per_token": 0.15 / 1_000_000,
        "output_price_per_token": 0.60 / 1_000_000,
        "provider": "OpenAI",
    },
    # ── Anthropic ─────────────────────────────────────────────────────────────
    "Claude 3.5 Haiku": {
        "input_price_per_token": 0.80 / 1_000_000,
        "output_price_per_token": 4.00 / 1_000_000,
        "provider": "Anthropic",
    },
    "Claude 3.5 Sonnet": {
        "input_price_per_token": 3.00 / 1_000_000,
        "output_price_per_token": 15.00 / 1_000_000,
        "provider": "Anthropic",
    },
    "Claude 3 Opus": {
        "input_price_per_token": 15.00 / 1_000_000,
        "output_price_per_token": 75.00 / 1_000_000,
        "provider": "Anthropic",
    },
    # ── Google ────────────────────────────────────────────────────────────────
    "Gemini 2.0 Flash": {
        "input_price_per_token": 0.10 / 1_000_000,
        "output_price_per_token": 0.40 / 1_000_000,
        "provider": "Google",
    },
    "Gemini 1.5 Pro": {
        "input_price_per_token": 1.25 / 1_000_000,
        "output_price_per_token": 5.00 / 1_000_000,
        "provider": "Google",
    },
    # ── Meta ──────────────────────────────────────────────────────────────────
    "Llama 3 (API)": {
        "input_price_per_token": 0.18 / 1_000_000,
        "output_price_per_token": 0.18 / 1_000_000,
        "provider": "Meta / Together AI",
    },
}

DEFAULT_INPUT_TOKENS = 500
DEFAULT_LOOP_TOKENS = 300
DEFAULT_OUTPUT_TOKENS = 200
DEFAULT_AGENTIC_MULTIPLIER = 5.0
DEFAULT_VOLUME = 10_000
VOLUME_RANGE_MAX = 500_000
VOLUME_RANGE_STEPS = 500
DEFAULT_ONPREM_MONTHLY_COST = 5_000.0
DEFAULT_SEAT_PRICE = 49.0
DEFAULT_NUM_SEATS = 100
DEFAULT_PRICE_PER_TASK = 1.00
