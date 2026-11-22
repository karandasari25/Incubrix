from typing import Any


def _truncate_words(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip()


def tailor_rendition(
    rendition: dict[str, Any],
    destination: dict[str, Any],
    limits: dict[str, int],
) -> dict[str, Any]:
    tailored = dict(rendition)
    if destination.get("surface") == "forum":
        body = str(tailored.get("body") or "")
        canonical = str(tailored.get("canonical_link") or "")
        if canonical and canonical not in body:
            body = f"{body.rstrip()}\n\nDiscussion: {canonical}".rstrip()
        body_limit = limits.get("body_max", 60000)
        if canonical and len(body) > body_limit:
            suffix = f"\n\nDiscussion: {canonical}"
            content_limit = max(0, body_limit - len(suffix))
            body = f"{_truncate_words(str(tailored.get('body') or ''), content_limit)}{suffix}"
        else:
            body = _truncate_words(body, body_limit)
        tailored["body"] = body

    title_limit = limits.get("title_max", 255)
    tailored["title"] = _truncate_words(str(tailored.get("title") or ""), title_limit)

    tags = tailored.get("tags") or []
    tailored["tags"] = [tag if str(tag).startswith("#") else f"#{tag}"
                        for tag in tags]
    return tailored
