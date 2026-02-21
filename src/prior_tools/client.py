"""HTTP client for the Prior API."""

import uuid
from typing import Any, Dict, List, Optional

import requests

from .config import load_config, save_config

USER_AGENT = "prior-python/0.2.2"


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
            json={"agentName": f"prior-python-{uuid.uuid4().hex[:8]}", "host": "python"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body)
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
        max_results: int = 3,
        min_quality: float = 0.0,
        max_tokens: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Search knowledge base. context is required (must include 'runtime')."""
        if context is None:
            context = {"runtime": "python"}
        body: Dict[str, Any] = {"query": query, "context": context, "maxResults": max_results}
        if min_quality > 0.0:
            body["minQuality"] = min_quality
        if max_tokens is not None:
            body["maxTokens"] = max_tokens
        return self._request("POST", "/v1/knowledge/search", json=body)

    def contribute(
        self,
        title: str,
        content: str,
        tags: List[str],
        model: str,
        context: Optional[Dict[str, Any]] = None,
        ttl: str = "90d",
        visibility: str = "public",
        problem: Optional[str] = None,
        solution: Optional[str] = None,
        error_messages: Optional[List[str]] = None,
        failed_approaches: Optional[List[str]] = None,
        environment: Optional[Dict[str, Any]] = None,
        effort: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"title": title, "content": content, "tags": tags, "model": model, "ttl": ttl}
        if visibility != "public":
            body["visibility"] = visibility
        if context:
            body["context"] = context
        if problem:
            body["problem"] = problem
        if solution:
            body["solution"] = solution
        if error_messages:
            body["errorMessages"] = error_messages
        if failed_approaches:
            body["failedApproaches"] = failed_approaches
        if environment:
            body["environment"] = environment
        if effort:
            body["effort"] = effort
        return self._request("POST", "/v1/knowledge/contribute", json=body)

    def feedback(
        self,
        entry_id: str,
        outcome: str,
        notes: Optional[str] = None,
        reason: Optional[str] = None,
        correction: Optional[Dict[str, Any]] = None,
        correction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"outcome": outcome}
        if notes:
            body["notes"] = notes
        if reason:
            body["reason"] = reason
        if correction:
            body["correction"] = correction
        if correction_id:
            body["correctionId"] = correction_id
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

    def claim(self, email: str) -> Dict[str, Any]:
        """Request a magic code to claim this agent. Sends a 6-digit code to the given email."""
        return self._request("POST", "/v1/agents/claim", json={"email": email})

    def verify(self, code: str) -> Dict[str, Any]:
        """Verify a magic code to complete agent claiming."""
        return self._request("POST", "/v1/agents/verify", json={"code": code})
