"""PRSpec — Ethereum spec compliance checker."""

__version__ = "1.4.0"

from .analyzer import GeminiAnalyzer, OpenAIAnalyzer, get_analyzer
from .code_fetcher import CodeFetcher
from .config import Config
from .parser import CodeParser
from .report_generator import ReportGenerator
from .spec_fetcher import SpecFetcher

__all__ = [
    "Config",
    "GeminiAnalyzer",
    "OpenAIAnalyzer",
    "get_analyzer",
    "SpecFetcher",
    "CodeFetcher",
    "CodeParser",
    "ReportGenerator",
]
