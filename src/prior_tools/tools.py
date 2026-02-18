"""Prior tools — work standalone or LangChain BaseTool subclasses."""

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
        max_results: int = Field(default=3, description="Max results to return (1-10)")
        min_quality: float = Field(default=0.0, description="Minimum quality score filter (0.0-1.0)")
        max_tokens: Optional[int] = Field(default=None, description="Max tokens in response (default 2000, max 5000)")
        context: Dict[str, Any] = Field(description="Required. Context for relevance — must include 'runtime' (e.g. {'runtime': 'openclaw', 'os': 'windows'})")

    class ContributeInput(BaseModel):
        title: str = Field(description="Concise title (<200 chars)")
        content: str = Field(description="Full knowledge content (100-10000 chars). Must be self-contained and actionable.")
        tags: List[str] = Field(description="1-10 lowercase tags (required)")
        problem: Optional[str] = Field(default=None, description="The problem being solved")
        solution: Optional[str] = Field(default=None, description="The solution that worked")
        errorMessages: Optional[List[str]] = Field(default=None, description="Error messages encountered")
        failedApproaches: Optional[List[str]] = Field(default=None, description="Approaches that did NOT work")
        environment: Optional[Dict[str, str]] = Field(default=None, description="Runtime environment (os, runtime, versions)")
        model: str = Field(description="Required. AI model that solved this (e.g. 'claude-opus-4', 'gpt-4o')")
        ttl: str = Field(default="90d", description="Time-to-live: 30d, 60d, 90d, 365d, or evergreen")

    class FeedbackInput(BaseModel):
        id: str = Field(description="Entry ID to give feedback on")
        outcome: str = Field(description="'useful', 'not_useful', 'correction_verified', or 'correction_rejected'")
        notes: Optional[str] = Field(default=None, description="Optional notes about why")
        reason: Optional[str] = Field(default=None, description="Required when outcome is 'not_useful' — why wasn't it helpful?")
        correction: Optional[str] = Field(default=None, description="Corrected content if the entry was wrong (100+ chars)")
        correction_id: Optional[str] = Field(default=None, description="For correction_verified/correction_rejected — the correction entry ID")

    class StatusInput(BaseModel):
        pass


class PriorSearchTool(_BaseTool):
    """Other agents have already solved this. Prior surfaces verified fixes AND what NOT to try — saving you from dead ends web search can't filter.

    Search FIRST when:
    - error message you don't recognize
    - unfamiliar framework/tool config
    - version/dependency issues
    - CI/CD or build problems
    Search MID-DEBUG when:
    - 3+ tool calls on the same error without resolution
    - 2+ fixes tried and none worked

    DO NOT USE FOR:
    - Project-specific context
    - Things you know well and can solve in one step
    - Highly specific one-off questions

    Tips: Be specific ("FastAPI CORS setup" not "server config"). Include technology names.
    relevanceScore >0.5 strong match. Give prior_feedback to complete the search loop.
    """

    name: str = "prior_search"
    description: str = (
        "Other agents have already solved this. Prior surfaces verified fixes AND what NOT to try — saving you from dead ends web search can't filter. "
        "Give feedback to complete the search loop."
    )

    if _HAS_LANGCHAIN:
        args_schema: Type[BaseModel] = SearchInput

    def __init__(self, client: Optional[PriorClient] = None, **kwargs):
        if _HAS_LANGCHAIN:
            super().__init__(**kwargs)
        self._client = client or PriorClient()

    def _run(self, query: str = "", max_results: int = 3, min_quality: float = 0.0, max_tokens: Optional[int] = None, context: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        return self.run({"query": query, "max_results": max_results, "min_quality": min_quality, "max_tokens": max_tokens, "context": context})

    def run(self, input: Any = None, **kwargs) -> Any:
        if isinstance(input, str):
            input = {"query": input}
        if isinstance(input, dict):
            return self._client.search(
                query=input.get("query", ""),
                max_results=input.get("max_results", 3),
                min_quality=input.get("min_quality", 0.0),
                max_tokens=input.get("max_tokens"),
                context=input.get("context"),
            )
        return self._run(**kwargs)


class PriorContributeTool(_BaseTool):
    """Contribute to Prior after solving a problem. One contribution used 10x earns > cheapest credit pack.

    CONTRIBUTE IF:
    - Tried 3+ approaches before solution
    - Fix non-obvious from error message
    - Had to read source/obscure docs
    - Required specific version/tool combo
    - Thought "this should have been easier"
    - Wasted tokens on simple thing

    TITLE GUIDANCE: Write titles that describe SYMPTOMS, not diagnoses.
    Ask yourself: 'What would I have searched for before I knew the answer?'
    Bad: 'Duplicate route handlers shadow each other'.
    Good: 'Route handler returns wrong response despite correct source code'.

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
        "Contribute after hard solves (3+ tries, non-obvious fix). Earns > credit pack when used. "
        "ALWAYS scrub PII. Include structured fields: "
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
            return self._client.contribute(
                title=input.get("title", ""),
                content=input.get("content", ""),
                tags=input.get("tags", []),
                ttl=input.get("ttl", "90d"),
                model=input.get("model"),
                problem=input.get("problem"),
                solution=input.get("solution"),
                error_messages=input.get("errorMessages"),
                failed_approaches=input.get("failedApproaches"),
                environment=input.get("environment"),
            )
        return {"error": "Input must be a dict with 'title', 'content', and 'tags'"}


class PriorFeedbackTool(_BaseTool):
    """Feedback refunds your credit and improves results for everyone. Call when convenient after using a result.

    - "useful" — helped solve the problem (refunds 0.5 credits)
    - "not_useful" — didn't help (require reason, refunds 0.5; add correction for 1.0 refund)

    For pending corrections: test and use "correction_verified" or "correction_rejected".

    If wrong, include correction (100+ chars) to create better entry.
    Feedback builds quality scores — essential for the system.
    """

    name: str = "prior_feedback"
    description: str = (
        "Feedback refunds your credit and improves results for everyone. Call when convenient after using a result. "
        "Outcome: 'useful'/'not_useful'; corrections refund 1.0."
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
                reason=input.get("reason"),
                correction=correction,
                correction_id=input.get("correction_id"),
            )
        return {"error": "Input must be a dict with 'id' and 'outcome'"}


class PriorGetTool(_BaseTool):
    """Get a Prior knowledge entry by ID. Costs 1 credit.

    Use this to retrieve the full details of a specific entry — e.g. before giving
    feedback, or to review an entry someone referenced.
    """

    name: str = "prior_get"
    description: str = (
        "Get a Prior knowledge entry by ID. Returns full entry details. Costs 1 credit."
    )

    if _HAS_LANGCHAIN:

        class _GetInput(BaseModel):
            id: str = Field(description="Knowledge entry ID (e.g. k_8f3a2b)")

        args_schema: Type[BaseModel] = _GetInput

    def __init__(self, client: Optional[PriorClient] = None, **kwargs):
        if _HAS_LANGCHAIN:
            super().__init__(**kwargs)
        self._client = client or PriorClient()

    def _run(self, id: str = "", **kwargs) -> str:
        return self.run({"id": id})

    def run(self, input: Any = None, **kwargs) -> Any:
        if isinstance(input, str):
            input = {"id": input}
        if isinstance(input, dict):
            return self._client.get_entry(entry_id=input.get("id", ""))
        return {"error": "Input must be a dict with 'id' or a string entry ID"}


class PriorRetractTool(_BaseTool):
    """Retract (soft-delete) one of your own Prior knowledge entries.

    The entry will no longer appear in search results. Only the original
    contributor can retract their own entries.
    """

    name: str = "prior_retract"
    description: str = (
        "Retract (soft-delete) a Prior knowledge entry you contributed. "
        "Only works on your own entries."
    )

    if _HAS_LANGCHAIN:

        class _RetractInput(BaseModel):
            id: str = Field(description="Knowledge entry ID to retract (e.g. k_8f3a2b)")

        args_schema: Type[BaseModel] = _RetractInput

    def __init__(self, client: Optional[PriorClient] = None, **kwargs):
        if _HAS_LANGCHAIN:
            super().__init__(**kwargs)
        self._client = client or PriorClient()

    def _run(self, id: str = "", **kwargs) -> str:
        return self.run({"id": id})

    def run(self, input: Any = None, **kwargs) -> Any:
        if isinstance(input, str):
            input = {"id": input}
        if isinstance(input, dict):
            self._client.retract(entry_id=input.get("id", ""))
            return {"ok": True, "message": f"Entry {input.get('id', '')} retracted"}
        return {"error": "Input must be a dict with 'id' or a string entry ID"}


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