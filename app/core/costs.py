from dataclasses import dataclass
from typing import Optional


# USD per 1M tokens (OpenAI pricing)
PRICING_USD_PER_1M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 5.00, "output": 15.00},
}


@dataclass
class CostsMetrics:
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cost_usd: Optional[float]


class CostCalculator:
    @staticmethod
    def calculate(
        model_name: str,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
    ) -> CostsMetrics:
        if input_tokens is None or output_tokens is None:
            return CostsMetrics(input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=None)

        pricing = PRICING_USD_PER_1M.get(model_name)
        if not pricing:
            return CostsMetrics(input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=None)

        cost = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]
        return CostsMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 8),
        )
