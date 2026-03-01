"""HTTP client for the Prior API."""

import time
from typing import Any, Dict, List, Optional

import requests

from .config import load_config, save_config

USER_AGENT = "prior-python/0.5.1"


class PriorClient:
    """Low-level client for the Prior knowledge exchange API.

    Handles authentication, auto-registration, and all API calls.
    Auth precedence: OAuth token > API key > error.
    Config is loaded from ~/.prior/config.json (or env vars).
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        config = load_config()
        self.base_url = (base_url or config.get("base_url", "")).rstrip("/")
        self.api_key = api_key or config.get("api_key")
        self.agent_id = config.get("agent_id")
        self._tokens = config.get("tokens")

        if not self._get_auth_token():
            raise RuntimeError(
                "No auth configured. Run 'prior login' or set PRIOR_API_KEY. "
                "Get an API key at https://prior.cg3.io/account"
            )

    def _get_auth_token(self) -> Optional[str]:
        """Get the best available auth token (OAuth > API key)."""
        if self._tokens and self._tokens.get("access_token"):
            return self._tokens["access_token"]
        return self.api_key

    def _refresh_if_needed(self) -> None:
        """Refresh OAuth access token if expired."""
        if not self._tokens or not self._tokens.get("refresh_token"):
            return
        expires_at = self._tokens.get("expires_at", 0)
        if time.time() * 1000 < expires_at - 60000:
            return  # Not expired yet (with 60s buffer)

        try:
            resp = requests.post(
                f"{self.base_url}/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._tokens["refresh_token"],
                    "client_id": self._tokens.get("client_id", "prior-cli"),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            data = resp.json()
            if "access_token" in data:
                self._tokens["access_token"] = data["access_token"]
                if "refresh_token" in data:
                    self._tokens["refresh_token"] = data["refresh_token"]
                self._tokens["expires_at"] = time.time() * 1000 + data.get("expires_in", 3600) * 1000
                config = load_config()
                config["tokens"] = self._tokens
                save_config(config)
        except Exception:
            pass  # Fall through with existing token

    def _headers(self) -> Dict[str, str]:
        self._refresh_if_needed()
        token = self._get_auth_token()
        return {
            "Authorization": f"Bearer {token}" if token else "",
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

