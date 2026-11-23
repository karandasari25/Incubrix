import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from app.recommendation import precision_at_10, recommend_destinations_for_content


def run_eval() -> dict:
    eval_file = root / "data" / "labelled" / "recommender_eval.json"
    if not eval_file.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {eval_file}")

    data = json.loads(eval_file.read_text(encoding="utf-8"))
    status = data.get("status", "draft_needs_human_review")
    items = data.get("items", [])

    # Synthetic catalogue pool matching relevant labels
    catalogue_pool = [
        {"id": "huggingface", "name": "Hugging Face Models", "audience_tags": ["ai", "machine-learning"], "relevance_score": 5, "frequency_cap": "daily", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "devto", "name": "Dev.to Technical", "audience_tags": ["devto", "saas", "infrastructure", "ai", "webdev"], "relevance_score": 5, "frequency_cap": "daily", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "discourse-ai", "name": "AI Builders Forum", "audience_tags": ["ai", "machine-learning"], "relevance_score": 5, "frequency_cap": "weekly", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "lemmy-localllama", "name": "LocalLlama Lemmy", "audience_tags": ["ai", "open-source"], "relevance_score": 4, "frequency_cap": "daily", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "hashnode-tech", "name": "Hashnode Engineering", "audience_tags": ["saas", "backend", "webdev", "devto"], "relevance_score": 4, "frequency_cap": "weekly", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "indiehackers", "name": "Indie Hackers Community", "audience_tags": ["saas", "founders", "bootstrap", "business"], "relevance_score": 5, "frequency_cap": "daily", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "discourse-startups", "name": "Startups Discourse", "audience_tags": ["founders", "saas", "marketing"], "relevance_score": 4, "frequency_cap": "weekly", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "ghost-founders", "name": "Founder Stories Blog", "audience_tags": ["founders", "saas", "creators"], "relevance_score": 4, "frequency_cap": "weekly", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "mrss-video", "name": "Creator Video MRSS Feed", "audience_tags": ["video", "creators", "youtube"], "relevance_score": 5, "frequency_cap": "daily", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "creator-forum", "name": "Video Creators Discourse", "audience_tags": ["video", "creators", "hardware"], "relevance_score": 4, "frequency_cap": "weekly", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "kit-newsletter", "name": "Creator Economy Weekly", "audience_tags": ["creators", "marketing", "newsletter"], "relevance_score": 4, "frequency_cap": "weekly", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
        {"id": "ghost-marketing", "name": "Growth Engineering Ghost", "audience_tags": ["marketing", "seo", "saas"], "relevance_score": 4, "frequency_cap": "weekly", "self_promo_allowed": True, "link_policy": "allowed", "disclosure_required": False},
    ]

    scores = []
    for item in items:
        ranked = recommend_destinations_for_content(catalogue_pool, item)
        rec_ids = [d["id"] for d in ranked]
        relevant_set = set(item.get("relevant_destinations", []))
        p10 = precision_at_10(rec_ids, relevant_set)
        scores.append(p10)

    mean_p10 = sum(scores) / max(len(scores), 1)

    eval_result = {
        "status": status,
        "sample_count": len(items),
        "mean_precision_at_10": round(mean_p10, 3),
        "note": "Reported as draft until domain human validation.",
    }

    # Append to docs/benchmarks.md
    benchmarks_file = root / "docs" / "benchmarks.md"
    benchmarks_file.parent.mkdir(parents=True, exist_ok=True)
    section = (
        "## 2. Recommender Evaluation (Precision@10)\n\n"
        f"- **Dataset**: `{eval_file.relative_to(root)}`\n"
        f"- **Dataset Status**: `{status}`\n"
        f"- **Test Samples**: {len(items)} content items\n"
        f"- **Mean Precision@10**: {eval_result['mean_precision_at_10']}\n"
        f"- **Audit Status**: Subject to final human label review per assessment rules.\n"
    )
    if benchmarks_file.exists():
        existing = benchmarks_file.read_text(encoding="utf-8")
        if "## 2. Recommender Evaluation" not in existing:
            benchmarks_file.write_text(existing.rstrip() + "\n\n" + section, encoding="utf-8")
    else:
        benchmarks_file.write_text("# Performance Benchmarks\n\n" + section, encoding="utf-8")

    print(f"Recommender evaluation complete: Mean P@10 = {eval_result['mean_precision_at_10']} ({len(items)} items)")
    return eval_result


if __name__ == "__main__":
    run_eval()
