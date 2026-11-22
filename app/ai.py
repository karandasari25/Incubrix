from typing import Any


class MockAIAdapter:
    def capture_rules(self, text: str) -> dict[str, Any]:
        return {
            "status": "pending_confirmation",
            "candidate_rules": [
                {
                    "source": text,
                    "rule": "Human confirmation required before use",
                }
            ],
        }


def confirm_captured_rules(candidate: dict[str, Any]) -> str:
    if candidate.get("status") != "pending_confirmation":
        return "Captured rules cannot be confirmed without pending state"
    return "Use of captured AI rules requires human confirmation"
