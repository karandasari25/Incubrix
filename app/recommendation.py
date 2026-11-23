from typing import Any
from app.rules import evaluate_post_rules


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


def recommend_destinations_for_content(
    destinations: list[dict[str, Any]],
    content: dict[str, Any],
) -> list[dict[str, Any]]:
    """Rank destinations for a specific content item with fit reasons and rule checks."""
    content_tags = {str(t).lower().lstrip("#") for t in content.get("tags", [])}
    content_lang = (content.get("language") or "en").lower()

    ranked = []
    for dest in destinations:
        # Exclude demoted, paused, or explicitly excluded destinations
        if dest.get("status") in {"demoted", "paused"} or dest.get("excluded"):
            continue

        dest_tags = {str(t).lower().lstrip("#") for t in dest.get("audience_tags", [])}
        overlap = len(content_tags.intersection(dest_tags))
        
        try:
            relevance_score = int(dest.get("relevance_score") or 1)
        except (TypeError, ValueError):
            relevance_score = 1
        relevance_score = max(1, min(5, relevance_score))

        # Check rules compatibility
        rule_check = evaluate_post_rules(content, dest, [])
        is_blocked = rule_check.get("decision") == "blocked"

        # Language match
        dest_lang = (dest.get("language") or "en").lower()
        lang_match = dest_lang == content_lang

        # Calculate composite score (out of 100)
        fit_score = (overlap * 20) + (relevance_score * 10) + (15 if lang_match else 0)
        if is_blocked:
            fit_score = max(0, fit_score - 40)
            reason = f"Rule warning: {', '.join(rule_check.get('reasons', []))}; tag overlap {overlap}; score {relevance_score}/5"
        else:
            reason = f"Compatible rules; tag overlap {overlap}; relevance {relevance_score}/5"
            if lang_match:
                reason += f"; matching language '{dest_lang}'"

        ranked.append({
            "id": dest.get("id"),
            "name": dest.get("name"),
            "url": dest.get("url"),
            "platform_key": dest.get("platform_key"),
            "connector_key": dest.get("connector_key"),
            "surface": dest.get("surface"),
            "level": dest.get("level", "L0"),
            "fit_score": fit_score,
            "audience_overlap": overlap,
            "relevance_score": relevance_score,
            "rules_compatible": not is_blocked,
            "recommendation_reason": reason,
        })

    ranked.sort(key=lambda d: (d["rules_compatible"], d["fit_score"]), reverse=True)
    return ranked


def precision_at_10(recommended: list[str], relevant: set[str]) -> float:
    top = recommended[:10]
    if not top:
        return 0.0
    hits = sum(1 for item in top if item in relevant)
    return hits / len(top)
