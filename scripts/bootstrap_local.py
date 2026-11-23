"""Bootstrap script for local Lemmy and Ghost testing environment."""
import sys
import httpx


def bootstrap_lemmy(base_url: str = "http://localhost:1236") -> dict:
    print(f"Connecting to Lemmy at {base_url}...")
    try:
        resp = httpx.get(f"{base_url}/api/v3/site", timeout=5.0)
        if resp.status_code == 200:
            print("Lemmy site is reachable.")
            return {"status": "ok", "url": base_url}
    except Exception as exc:
        print(f"Lemmy not reachable: {exc}")
    return {"status": "unreachable", "url": base_url}


def bootstrap_ghost(base_url: str = "http://localhost:2368") -> dict:
    print(f"Connecting to Ghost at {base_url}...")
    try:
        resp = httpx.get(f"{base_url}/ghost/api/admin/site/", timeout=5.0)
        print(f"Ghost responded with status {resp.status_code}")
        return {"status": "ok", "url": base_url}
    except Exception as exc:
        print(f"Ghost not reachable: {exc}")
    return {"status": "unreachable", "url": base_url}


if __name__ == "__main__":
    print("IncuBrix Local Platform Bootstrap")
    lemmy_res = bootstrap_lemmy()
    ghost_res = bootstrap_ghost()
    print("Bootstrap summary:", {"lemmy": lemmy_res, "ghost": ghost_res})
