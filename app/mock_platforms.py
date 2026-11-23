import time
from typing import Any
from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.responses import JSONResponse

app = FastAPI(title="IncuBrix Mock Platforms", docs_url=None, redoc_url=None)

# In-memory platform database
posts: dict[str, dict[str, Any]] = {}
lemmy_posts: dict[str, dict[str, Any]] = {}
ghost_posts: dict[str, dict[str, Any]] = {}
devto_posts: dict[str, dict[str, Any]] = {}
webhook_events: list[dict[str, Any]] = []


def check_fault(request: Request, x_mock_fault: str | None = None) -> Response | None:
    fault = x_mock_fault or request.headers.get("X-Mock-Fault") or request.query_params.get("fault")
    if not fault:
        return None

    fault = fault.strip().lower()
    if fault == "429":
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded", "message": "Too many requests", "retry_after": 30},
            headers={"Retry-After": "30", "X-RateLimit-Reset": "30"},
        )
    if fault == "401":
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Connection auth expired or invalid token"},
        )
    if fault == "422":
        return JSONResponse(
            status_code=422,
            content={"error": "unprocessable_entity", "message": "Platform content rejected: validation failed"},
        )
    if fault == "500":
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Platform internal server error"},
        )
    if fault == "503":
        return JSONResponse(
            status_code=503,
            content={"error": "service_unavailable", "message": "Platform service temporarily unavailable"},
        )
    if fault in {"timeout", "504"}:
        return JSONResponse(
            status_code=504,
            content={"error": "gateway_timeout", "message": "Platform upstream connection timed out"},
        )
    if fault == "quota":
        return JSONResponse(
            status_code=429,
            content={"error": "quota_exhausted", "message": "Monthly platform publishing quota exhausted"},
            headers={"X-Quota-Exhausted": "true"},
        )
    return None


# ==========================================
# Discourse Mock Endpoints
# ==========================================
@app.post("/discourse/posts.json")
@app.post("/discourse/t")
def create_discourse_topic(payload: dict, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    fault = x_mock_fault or request.headers.get("X-Mock-Fault")
    post_id = f"discourse-post-{len(posts) + 1}"
    posts[post_id] = {**payload, "status": "published"}

    if fault in {"timeout_after_create", "timeout-after-create"}:
        return JSONResponse(
            status_code=504,
            content={"error": "gateway_timeout", "message": "Timeout occurred after record was created"},
        )

    if fault == "rename_field":
        return {
            "legacy_identifier": post_id,
            "status": "published",
        }

    return {
        "platform_post_id": post_id,
        "id": len(posts),
        "live_url": f"http://mock-platforms:8080/discourse/t/{post_id}",
        "status": "published",
    }


@app.get("/discourse/t/{post_id}.json")
@app.get("/discourse/t/{post_id}")
def get_discourse_topic(post_id: str, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    clean_id = post_id.removesuffix(".json")
    if clean_id not in posts:
        return JSONResponse(status_code=404, content={"status": "not_found", "live_url": ""})
    return {
        "status": posts[clean_id].get("status", "published"),
        "live_url": f"http://mock-platforms:8080/discourse/t/{clean_id}",
        "views": 420,
        "like_count": 42,
        "posts_count": 5,
    }


@app.delete("/discourse/t/{post_id}.json")
@app.delete("/discourse/t/{post_id}")
def delete_discourse_topic(post_id: str, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    clean_id = post_id.removesuffix(".json")
    deleted = posts.pop(clean_id, None) is not None
    return {"deleted": deleted}


@app.get("/discourse/search.json")
def search_discourse(request: Request, q: str | None = None):
    # Marker search helper
    query_str = q or request.query_params.get("q", "")
    matched = []
    for pid, p in posts.items():
        raw_text = str(p.get("raw") or p.get("body") or "")
        if query_str and query_str in raw_text:
            matched.append({"id": pid, "title": p.get("title", "")})
    return {"posts": matched}


# ==========================================
# Lemmy Mock Endpoints
# ==========================================
@app.post("/lemmy/api/v3/post")
def create_lemmy_post(payload: dict, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    fault = x_mock_fault or request.headers.get("X-Mock-Fault")
    post_id = f"lemmy-post-{len(lemmy_posts) + 1}"
    lemmy_posts[post_id] = {**payload, "status": "published", "deleted": False}
    numeric_id = str(len(lemmy_posts))
    lemmy_posts[numeric_id] = lemmy_posts[post_id]

    if fault in {"timeout_after_create", "timeout-after-create"}:
        return JSONResponse(status_code=504, content={"error": "gateway_timeout"})

    if fault == "rename_field":
        return {"legacy_lemmy_id": post_id}

    return {
        "post_view": {
            "post": {
                "id": post_id,
                "name": payload.get("name", ""),
                "body": payload.get("body", ""),
                "deleted": False,
            },
            "counts": {"score": 10, "comments": 2},
        },
        "platform_post_id": post_id,
        "live_url": f"http://mock-platforms:8080/lemmy/post/{post_id}",
        "status": "published",
    }


@app.get("/lemmy/api/v3/post")
def get_lemmy_post(id: str = Query(...), request: Request = None, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    post = lemmy_posts.get(str(id))
    if not post or post.get("deleted"):
        return JSONResponse(status_code=404, content={"status": "not_found", "live_url": ""})
    return {
        "post_view": {
            "post": {
                "id": id,
                "name": post.get("name", ""),
                "body": post.get("body", ""),
                "deleted": post.get("deleted", False),
            },
            "counts": {"score": 10, "comments": 2},
        },
        "status": "published",
        "live_url": f"http://mock-platforms:8080/lemmy/post/{id}",
    }


@app.post("/lemmy/api/v3/post/delete")
def delete_lemmy_post(payload: dict, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    pid = str(payload.get("post_id", ""))
    if pid in lemmy_posts:
        lemmy_posts[pid]["deleted"] = True
        return {"post_view": {"post": {"id": pid, "deleted": True}}, "deleted": True}
    return JSONResponse(status_code=404, content={"deleted": False})


@app.get("/lemmy/api/v3/community")
def get_lemmy_community(name: str = Query("technology")):
    return {"community_view": {"community": {"id": 1, "name": name}}}


# ==========================================
# Ghost Mock Endpoints
# ==========================================
@app.post("/ghost/ghost/api/admin/posts/")
@app.post("/ghost/api/admin/posts/")
def create_ghost_post(payload: dict, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    fault = x_mock_fault or request.headers.get("X-Mock-Fault")
    post_id = f"ghost-post-{len(ghost_posts) + 1}"
    posts_list = payload.get("posts", [{}])
    first_post = posts_list[0] if posts_list else {}
    ghost_posts[post_id] = {**first_post, "status": "published"}

    if fault in {"timeout_after_create", "timeout-after-create"}:
        return JSONResponse(status_code=504, content={"error": "gateway_timeout"})

    if fault == "rename_field":
        return {"posts": [{"ghost_uuid": post_id}]}

    return {
        "posts": [
            {
                "id": post_id,
                "title": first_post.get("title", ""),
                "url": f"http://mock-platforms:8080/ghost/{post_id}",
                "status": "published",
            }
        ],
        "platform_post_id": post_id,
        "live_url": f"http://mock-platforms:8080/ghost/{post_id}",
        "status": "published",
    }


@app.get("/ghost/ghost/api/admin/posts/{post_id}/")
@app.get("/ghost/api/admin/posts/{post_id}/")
def get_ghost_post(post_id: str, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    clean_id = post_id.rstrip("/")
    if clean_id not in ghost_posts and post_id not in ghost_posts:
        return JSONResponse(status_code=404, content={"errors": [{"message": "Post not found"}]})
    p = ghost_posts.get(clean_id) or ghost_posts.get(post_id)
    return {
        "posts": [
            {
                "id": clean_id,
                "title": p.get("title", ""),
                "url": f"http://mock-platforms:8080/ghost/{clean_id}",
                "status": p.get("status", "published"),
            }
        ],
        "status": "published",
        "live_url": f"http://mock-platforms:8080/ghost/{clean_id}",
    }


@app.delete("/ghost/ghost/api/admin/posts/{post_id}/")
@app.delete("/ghost/api/admin/posts/{post_id}/")
def delete_ghost_post(post_id: str, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    clean_id = post_id.rstrip("/")
    deleted = (ghost_posts.pop(clean_id, None) is not None) or (ghost_posts.pop(post_id, None) is not None)
    if deleted:
        return Response(status_code=204)
    return JSONResponse(status_code=404, content={"errors": [{"message": "Post not found"}]})


# ==========================================
# Dev.to Mock Endpoints
# ==========================================
@app.post("/devto/api/articles")
def create_devto_article(payload: dict, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    fault = x_mock_fault or request.headers.get("X-Mock-Fault")
    post_id = f"devto-post-{len(devto_posts) + 1}"
    article = payload.get("article", payload)
    devto_posts[post_id] = {**article, "published": True}

    if fault in {"timeout_after_create", "timeout-after-create"}:
        return JSONResponse(status_code=504, content={"error": "gateway_timeout"})

    if fault == "rename_field":
        return {"devto_article_number": post_id}

    return {
        "id": post_id,
        "platform_post_id": post_id,
        "title": article.get("title", ""),
        "url": f"http://mock-platforms:8080/devto/{post_id}",
        "live_url": f"http://mock-platforms:8080/devto/{post_id}",
        "published": True,
        "status": "published",
    }


@app.get("/devto/api/articles/{post_id}")
def get_devto_article(post_id: str, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    if post_id not in devto_posts:
        return JSONResponse(status_code=404, content={"error": "not found"})
    a = devto_posts[post_id]
    return {
        "id": post_id,
        "title": a.get("title", ""),
        "url": f"http://mock-platforms:8080/devto/{post_id}",
        "live_url": f"http://mock-platforms:8080/devto/{post_id}",
        "published": a.get("published", True),
        "status": "published" if a.get("published") else "unpublished",
    }


@app.put("/devto/api/articles/{post_id}")
def update_devto_article(post_id: str, payload: dict, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    if post_id not in devto_posts:
        return JSONResponse(status_code=404, content={"error": "not found"})
    article = payload.get("article", payload)
    devto_posts[post_id].update(article)
    return {
        "id": post_id,
        "published": devto_posts[post_id].get("published", False),
        "status": "unpublished" if not devto_posts[post_id].get("published") else "published",
    }


# ==========================================
# Webhook Mock Endpoints
# ==========================================
@app.post("/webhook/inbox")
def webhook_inbox(payload: dict, request: Request, x_mock_fault: str | None = Header(None, alias="X-Mock-Fault")):
    fault_resp = check_fault(request, x_mock_fault)
    if fault_resp:
        return fault_resp

    post_id = f"webhook-event-{len(webhook_events) + 1}"
    webhook_events.append({"id": post_id, "payload": payload, "headers": dict(request.headers)})
    return {
        "received": True,
        "platform_post_id": post_id,
        "live_url": f"http://mock-platforms:8080/webhook/inbox/{post_id}",
        "status": "published",
        "payload": payload,
    }


@app.get("/webhook/inbox/{post_id}")
def get_webhook_event(post_id: str, request: Request):
    evt = next((e for e in webhook_events if e["id"] == post_id), None)
    if not evt:
        return JSONResponse(status_code=404, content={"status": "not_found"})
    return {"status": "published", "live_url": f"http://mock-platforms:8080/webhook/inbox/{post_id}"}


@app.delete("/webhook/inbox/{post_id}")
def delete_webhook_event(post_id: str, request: Request):
    for i, e in enumerate(webhook_events):
        if e["id"] == post_id:
            webhook_events.pop(i)
            return {"deleted": True}
    return JSONResponse(status_code=404, content={"deleted": False})
