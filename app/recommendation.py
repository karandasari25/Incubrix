from typing import Any


def rank_destinations(
    destinations: list[dict[str, Any]],
    audience: dict[str, Any],
) -> list[dict[str, Any]]:
    wanted = {str(tag).lower() for tag in audience.get("audience", [])}
    ranked = []
    for destination in destinations:
        tags = {str(tag).lower() for tag in destination.get("audience_tags", [])}
        overlap = len(wanted.intersection(tags))
        try:
            score = int(destination.get("relevance_score") or 1)
        except (TypeError, ValueError):
            score = 1
        score = max(1, min(5, score))
        ranked.append({**destination, "relevance_score": score,
                       "audience_overlap": overlap})
    ranked.sort(key=lambda item: (item["audience_overlap"], item["relevance_score"]),
                reverse=True)
    return ranked


def precision_at_10(recommended: list[str], relevant: set[str]) -> float:
    top = recommended[:10]
    if not top:
        return 0.0
    hits = sum(1 for item in top if item in relevant)
    return hits / len(top)
