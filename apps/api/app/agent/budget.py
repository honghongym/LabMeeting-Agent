from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    estimated_tokens: int
    degraded: bool
    reason: str | None = None


class TokenBudgetController:
    def __init__(self, per_call_limit: int = 12000, per_task_limit: int = 80000) -> None:
        self.per_call_limit = per_call_limit
        self.per_task_limit = per_task_limit

    def estimate_tokens(self, text: str) -> int:
        # Practical Chinese approximation for early validation; replaceable by vendor tokenizer.
        return max(1, int(len(text) / 1.7))

    def check_call(self, prompt_text: str, historical_memory: str = "") -> BudgetDecision:
        estimated = self.estimate_tokens(prompt_text + historical_memory)
        if estimated <= self.per_call_limit:
            return BudgetDecision(True, estimated, False)

        compressed_estimate = self.estimate_tokens(prompt_text) + min(
            400,
            self.estimate_tokens(historical_memory),
        )
        if compressed_estimate <= self.per_call_limit:
            return BudgetDecision(True, compressed_estimate, True, "historical_memory_compressed")

        return BudgetDecision(False, compressed_estimate, True, "chunk_requires_secondary_split")

    def should_degrade_reduce(self, consumed_tokens: int) -> bool:
        return consumed_tokens >= int(self.per_task_limit * 0.85)

