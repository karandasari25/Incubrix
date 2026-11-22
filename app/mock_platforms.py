from fastapi import FastAPI


app = FastAPI(title="IncuBrix Mock Platforms", docs_url=None, redoc_url=None)
posts: dict[str, dict] = {}


@app.post("/discourse/t")
def create_discourse_topic(payload: dict):
    post_id = f"discourse-post-{len(posts) + 1}"
    posts[post_id] = payload
    return {
        "platform_post_id": post_id,
        "live_url": f"http://mock-platforms:8080/discourse/t/{post_id}",
        "status": "published",
    }


@app.get("/discourse/t/{post_id}")
def get_discourse_topic(post_id: str):
    if post_id not in posts:
        return {"status": "not_found", "live_url": ""}
    return {
        "status": "published",
        "live_url": f"http://mock-platforms:8080/discourse/t/{post_id}",
    }


@app.delete("/discourse/t/{post_id}")
def delete_discourse_topic(post_id: str):
    return {"deleted": posts.pop(post_id, None) is not None}


@app.post("/webhook/inbox")
def webhook_inbox(payload: dict, request_headers: dict | None = None):
    return {"received": True, "payload": payload}
