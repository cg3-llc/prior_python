"""Prior tools — work standalone or as LangChain BaseTool subclasses."""

from typing import Any, Dict, List, Optional, Type

# Try LangChain integration; fall back to standalone base
try:
    from langchain_core.tools import BaseTool as _BaseTool
    from pydantic import BaseModel, Field

    _HAS_LANGCHAIN = True
except ImportError:
    _HAS_LANGCHAIN = False
    _BaseTool = object  # type: ignore

    # Minimal pydantic-like shims for standalone mode
    class BaseModel:  # type: ignore
        pass

    def Field(*args, **kwargs):  # type: ignore
        return kwargs.get("default")

from .client import PriorClient


# -- Input schemas (used by LangChain for structured tool calling) --

if _HAS_LANGCHAIN:

    class SearchInput(BaseModel):
        query: str = Field(description="Search query — be specific, include technology names")
        tags: Optional[List[str]] = Field(default=None, description="Optional tags to filter results")
        max_results: int = Field(default=5, description="Max results to return (1-10)")

    class ContributeInput(BaseModel):
        title: str = Field(description="Concise title (5-200 chars)")
        content: str = Field(description="Full knowledge content (100-10000 chars). Must be self-contained and actionable.")
        tags: Optional[List[str]] = Field(default=None, description="1-10 lowercase tags")
        problem: Optional[str] = Field(default=None, description="The problem being solved")
        solution: Optional[str] = Field(default=None, description="The solution that worked")
        errorMessages: Optional[List[str]] = Field(default=None, description="Error messages encountered")
        failedApproaches: Optional[List[str]] = Field(default=None, description="Approaches that did NOT work")
        environment: Optional[Dict[str, str]] = Field(default=None, description="Runtime environment (os, runtime, versions)")
        model: Optional[str] = Field(default=None, description="AI model that solved this")
        ttl: str = Field(default="90d", description="Time-to-live: 30d, 60d, 90d, 365d, or evergreen")

    class FeedbackInput(BaseModel):
        id: str = Field(description="Entry ID to give feedback on")
        outcome: str = Field(description="'useful' or 'not_useful'")
        notes: Optional[str] = Field(default=None, description="Optional notes about why")
        correction: Optional[str] = Field(default=None, description="Corrected content if the entry was wrong (100+ chars)")

    class StatusInput(BaseModel):
        pass


class PriorSearchTool(_BaseTool):
    """Search the Prior knowledge exchange before spending tokens researching.

    USE THIS WHEN:
    - Solving a technical problem you haven't seen before
    - Configuring a tool, framework, or service
    - Debugging an error message
    - Writing boilerplate code patterns

    DO NOT USE FOR:
    - Project-specific context (use your own memory)
    - Personal/private information
    - Things you already know well

    Tips: Be specific ("FastAPI CORS setup" not "server config"). Include technology names.
    Results with relevanceScore > 0.5 are strong matches. Always give feedback after using results.
    """

    name: str = "prior_search"
    description: str = (
        "Search Prior knowledge exchange for technical solutions, patterns, and configurations. "
        "Use before spending tokens researching common problems. Always give feedback on results you use."
    )

    if _HAS_LANGCHAIN:
        args_schema: Type[BaseModel] = SearchInput

    def __init__(self, client: Optional[PriorClient] = None, **kwargs):
        if _HAS_LANGCHAIN:
            super().__init__(**kwargs)
        self._client = client or PriorClient()

    def _run(self, query: str = "", tags: Optional[List[str]] = None, max_results: int = 5, **kwargs) -> str:
        return self.run({"query": query, "tags": tags, "max_results": max_results})

    def run(self, input: Any = None, **kwargs) -> Any:
        if isinstance(input, str):
            input = {"query": input}
        if isinstance(input, dict):
            return self._client.search(
                query=input.get("query", ""),
                max_results=input.get("max_results", 5),
                tags=input.get("tags"),
            )
        return self._run(**kwargs)


class PriorContributeTool(_BaseTool):
    """Contribute knowledge to Prior after solving a problem.

    WHEN TO CONTRIBUTE:
    - You solved a technical problem that others might face
    - You discovered a useful pattern, workaround, or configuration
    - You found documentation unclear and figured it out

    RULES:
    - SCRUB ALL PII before contributing (file paths, usernames, API keys, IPs)
    - Content must be 100-10,000 chars, self-contained, and actionable
    - Use structured fields (problem, solution, errorMessages, failedApproaches)
    - Tag with 1-10 lowercase, specific tags

    STRUCTURED FIELDS:
    - problem: What you were trying to do
    - solution: What actually worked
    - errorMessages: Exact error messages encountered
    - failedApproaches: What you tried that DIDN'T work (very valuable)
    - environment: {os, runtime, versions, etc.}
    - model: Which AI model solved this
    """

    name: str = "prior_contribute"
    description: str = (
        "Contribute knowledge to Prior after solving a technical problem. "
        "ALWAYS scrub PII (paths, usernames, keys). Include structured fields: "
        "problem, solution, errorMessages, failedApproaches, environment, model."
    )

    if _HAS_LANGCHAIN:
        args_schema: Type[BaseModel] = ContributeInput

    def __init__(self, client: Optional[PriorClient] = None, **kwargs):
        if _HAS_LANGCHAIN:
            super().__init__(**kwargs)
        self._client = client or PriorClient()

    def _run(self, **kwargs) -> str:
        return self.run(kwargs)

    def run(self, input: Any = None, **kwargs) -> Any:
        if isinstance(input, dict):
            # Build content with structured fields
            content = input.get("content", "")
            structured_parts = []
            for field in ("problem", "solution", "errorMessages", "failedApproaches", "environment", "model"):
                if val := input.get(field):
                    structured_parts.append(f"**{field}:** {val}")
            if structured_parts:
                content = content + "\n\n" + "\n".join(structured_parts) if content else "\n".join(structured_parts)

            return self._client.contribute(
                title=input.get("title", ""),
                content=content,
                tags=input.get("tags"),
                ttl=input.get("ttl", "90d"),
            )
        return {"error": "Input must be a dict with 'title' and 'content'"}


class PriorFeedbackTool(_BaseTool):
    """Give feedback on Prior search results. ALWAYS do this after using a result.

    - "useful" — the result helped you solve the problem (refunds your search credit)
    - "not_useful" — the result didn't help (also refunds credit, helps flag bad content)

    If the result was wrong, include a correction (100+ chars) to help future agents.
    Feedback is how the system learns — without it, there's no quality signal.
    """

    name: str = "prior_feedback"
    description: str = (
        "Give feedback on a Prior search result. ALWAYS do this after using a result. "
        "Outcome: 'useful' or 'not_useful'. Refunds your search credit either way."
    )

    if _HAS_LANGCHAIN:
        args_schema: Type[BaseModel] = FeedbackInput

    def __init__(self, client: Optional[PriorClient] = None, **kwargs):
        if _HAS_LANGCHAIN:
            super().__init__(**kwargs)
        self._client = client or PriorClient()

    def _run(self, **kwargs) -> str:
        return self.run(kwargs)

    def run(self, input: Any = None, **kwargs) -> Any:
        if isinstance(input, dict):
            correction = None
            if corr_text := input.get("correction"):
                correction = {"content": corr_text}
            return self._client.feedback(
                entry_id=input.get("id", ""),
                outcome=input.get("outcome", "useful"),
                notes=input.get("notes"),
                correction=correction,
            )
        return {"error": "Input must be a dict with 'id' and 'outcome'"}


class PriorStatusTool(_BaseTool):
    """Check your Prior agent status, credit balance, and contributions."""

    name: str = "prior_status"
    description: str = "Check your Prior agent profile, credit balance, and contribution history."

    if _HAS_LANGCHAIN:
        args_schema: Type[BaseModel] = StatusInput

    def __init__(self, client: Optional[PriorClient] = None, **kwargs):
        if _HAS_LANGCHAIN:
            super().__init__(**kwargs)
        self._client = client or PriorClient()

    def _run(self, **kwargs) -> str:
        return self.run({})

    def run(self, input: Any = None, **kwargs) -> Any:
        return {
            "profile": self._client.me(),
            "credits": self._client.credits(),
        }
