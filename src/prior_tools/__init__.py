"""prior-tools — Python SDK for Prior, the knowledge exchange for AI agents."""

import warnings
# Suppress Pydantic V1 deprecation warning from langchain on Python 3.14+
# (langchain is an optional dependency; this warning is not actionable by us)
warnings.filterwarnings("ignore", message=".*Pydantic V1.*")

from .tools import PriorSearchTool, PriorContributeTool, PriorFeedbackTool, PriorStatusTool, PriorGetTool, PriorRetractTool
from .client import PriorClient
from .config import load_config, save_config

__version__ = "0.5.4"
__all__ = [
    "PriorSearchTool",
    "PriorContributeTool",
    "PriorFeedbackTool",
    "PriorStatusTool",
    "PriorGetTool",
    "PriorRetractTool",
    "PriorClient",
    "load_config",
    "save_config",
]
