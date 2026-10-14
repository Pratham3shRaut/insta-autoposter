"""Minimal Instagram Graph API client: publish an image post, check limits, refresh tokens.

Supports both setups Meta offers:
  - Instagram API with Instagram Login  -> GRAPH_HOST=graph.instagram.com (default)
  - Instagram API with Facebook Login   -> GRAPH_HOST=graph.facebook.com

Errors are printed from the response body only, never the request URL, so the
access token can't leak into GitHub Actions logs.
"""
from __future__ import annotations

import os
import time

import requests


class InstagramError(RuntimeError):
    pass


class Instagram:
    def __init__(self) -> None:
        self.token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
        if not self.token:
            raise InstagramError("IG_ACCESS_TOKEN is not set")
        self.host = os.environ.get("GRAPH_HOST", "graph.instagram.com").strip()
        self.version = os.environ.get("GRAPH_VERSION", "v25.0").strip()
        self.user_id = os.environ.get("IG_USER_ID", "").strip() or None

    # --- low level -------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"https://{self.host}/{self.version}/{path.lstrip('/')}"

    def _call(self, method: str, path: str, **data) -> dict:
        payload = {**data, "access_token": self.token}
        try:
            if method == "GET":
                r = requests.get(self._url(path), params=payload, timeout=60)
            else:
                r = requests.post(self._url(path), data=payload, timeout=120)
        except requests.RequestException as e:
            raise InstagramError(f"network error calling {path}: {type(e).__name__}") from None
        body = r.json() if r.headers.get("content-type", "").startswith(("application/json", "text/javascript")) else {}
        if r.status_code != 200 or "error" in body:
            err = body.get("error", {})
            raise InstagramError(
                f"{method} {path} failed ({r.status_code}): {err.get('message', r.text[:300])} "
                f"[type={err.get('type')}, code={err.get('code')}, subcode={err.get('error_subcode')}]"
            )
        return body

    # --- helpers ---------------------------------------------------------
    def ig_user_id(self) -> str:
        if self.user_id:
            return self.user_id
        if self.host == "graph.instagram.com":
            me = self._call("GET", "me", fields="user_id,username")
            self.user_id = str(me.get("user_id") or me["id"])
            return self.user_id
        raise InstagramError("Set IG_USER_ID (the Instagram business account id) when using graph.facebook.com")

    def whoami(self) -> dict:
        uid = self.ig_user_id()
        return self._call("GET", uid, fields="username,media_count")

    def publishing_quota(self) -> dict | None:
        try:
            res = self._call("GET", f"{self.ig_user_id()}/content_publishing_limit", fields="quota_usage,config")
            return (res.get("data") or [None])[0]
        except InstagramError as e:
            print(f"could not read publishing limit (continuing): {e}")
            return None

    # --- publishing ------------------------------------------------------
    def _check_quota(self) -> None:
        quota = self.publishing_quota()
        if quota and quota.get("config"):
            used, total = quota.get("quota_usage", 0), quota["config"].get("quota_total")
            print(f"publishing quota: {used}/{total} used in the last 24h")
            if total and used >= total:
                raise InstagramError("24-hour publishing limit reached; try again later")

    def _wait_until_ready(self, container_id: str) -> None:
        # Meta recommends polling status; give the image up to ~5 minutes to process.
        for _ in range(20):
            status = self._call("GET", container_id, fields="status_code").get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"media container {container_id} ended with status {status}")
            time.sleep(15)
        raise InstagramError(f"media container {container_id} not ready after 5 minutes")

    def publish_image(self, image_url: str, caption: str) -> str:
        uid = self.ig_user_id()
        self._check_quota()

        container = self._call("POST", f"{uid}/media", image_url=image_url, caption=caption)
        cid = container["id"]
        print(f"created media container {cid}")
        self._wait_until_ready(cid)

        published = self._call("POST", f"{uid}/media_publish", creation_id=cid)
        return published["id"]

    def publish_carousel(self, image_urls: list[str], caption: str) -> str:
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError(f"carousel needs 2-10 images, got {len(image_urls)}")

        uid = self.ig_user_id()
        self._check_quota()

        item_ids = []
        for url in image_urls:
            item = self._call("POST", f"{uid}/media", image_url=url, is_carousel_item="true")
            item_ids.append(item["id"])
            print(f"created carousel item {item['id']}")
        for item_id in item_ids:
            self._wait_until_ready(item_id)

        container = self._call(
            "POST", f"{uid}/media",
            media_type="CAROUSEL", children=",".join(item_ids), caption=caption,
        )
        cid = container["id"]
        print(f"created carousel container {cid}")
        self._wait_until_ready(cid)

        published = self._call("POST", f"{uid}/media_publish", creation_id=cid)
        return published["id"]

    # --- token refresh (Instagram Login tokens only) -----------------------
    def refresh_token(self) -> tuple[str, int]:
        if self.host != "graph.instagram.com":
            raise InstagramError("token refresh here only applies to Instagram Login tokens (graph.instagram.com)")
        try:
            r = requests.get(
                "https://graph.instagram.com/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": self.token},
                timeout=60,
            )
        except requests.RequestException as e:
            raise InstagramError(f"network error refreshing token: {type(e).__name__}") from None
        body = r.json()
        if r.status_code != 200 or "access_token" not in body:
            raise InstagramError(f"token refresh failed ({r.status_code}): {body.get('error', body)}")
        return body["access_token"], int(body.get("expires_in", 0))
