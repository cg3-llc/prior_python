"""HTTP client for the Prior API."""

import uuid
from typing import Any, Dict, List, Optional

import requests

from .config import load_config, save_config

USER_AGENT = "prior-python/0.1.0"


class PriorClient:
    """Low-level client for the Prior knowledge exchange API.

    Handles authentication, auto-registration, and all API calls.
    Config is loaded from ~/.prior/config.json (or env vars).
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        config = load_config()
        self.base_url = (base_url or config.get("base_url", "")).rstrip("/")
        self.api_key = api_key or config.get("api_key")
        self.agent_id = config.get("agent_id")

        if not self.api_key:
            self._auto_register()

    def _auto_register(self) -> None:
        """Register a new agent and persist credentials."""
        resp = requests.post(
            f"{self.base_url}/v1/agents/register",
            json={"name": f"prior-python-{uuid.uuid4().hex[:8]}"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self.api_key = data["apiKey"]
        self.agent_id = data["agentId"]
        save_config({
            "base_url": self.base_url,
            "api_key": self.api_key,
            "agent_id": self.agent_id,
        })

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=self._headers(),
            timeout=30,
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else None

    # -- Knowledge endpoints --

    def search(
        self,
        query: str,
        max_results: int = 5,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"query": query, "maxResults": max_results}
        if tags:
            body["tags"] = tags
        return self._request("POST", "/v1/knowledge/search", json=body)

    def contribute(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        ttl: str = "90d",
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"title": title, "content": content, "ttl": ttl}
        if tags:
            body["tags"] = tags
        if context:
            body["context"] = context
        return self._request("POST", "/v1/knowledge/contribute", json=body)

    def feedback(
        self,
        entry_id: str,
        outcome: str,
        notes: Optional[str] = None,
        correction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"outcome": outcome}
        if notes:
            body["notes"] = notes
        if correction:
            body["correction"] = correction
        return self._request("POST", f"/v1/knowledge/{entry_id}/feedback", json=body)

    def get_entry(self, entry_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/knowledge/{entry_id}")

    def retract(self, entry_id: str) -> None:
        self._request("DELETE", f"/v1/knowledge/{entry_id}")

    # -- Agent endpoints --

    def me(self) -> Dict[str, Any]:
        return self._request("GET", "/v1/agents/me")

    def credits(self) -> Dict[str, Any]:
        return self._request("GET", "/v1/agents/me/credits")

    def contributions(self) -> Dict[str, Any]:
        return self._request("GET", "/v1/agents/me/contributions")
