"""PRSpec — Ethereum spec compliance checker."""

__version__ = "1.3.0"

from .config import Config
from .analyzer import GeminiAnalyzer, OpenAIAnalyzer, get_analyzer
from .spec_fetcher import SpecFetcher
from .code_fetcher import CodeFetcher
from .parser import CodeParser
from .report_generator import ReportGenerator

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
