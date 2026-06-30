"""PRSpec — Ethereum spec compliance checker."""

__version__ = "1.7.1"

from .analyzer import GeminiAnalyzer, OpenAIAnalyzer, get_analyzer
from .code_fetcher import CodeFetcher
from .config import Config
from .differential import ClientAnalysis, DifferentialEngine, DifferentialResult
from .parser import CodeParser
from .report_generator import ReportGenerator
from .spec_fetcher import SpecFetcher
from .verifier import FindingVerdict, SpecGrounding, VerificationEngine

__all__ = [
    "Config",
    "GeminiAnalyzer",
    "OpenAIAnalyzer",
    "get_analyzer",
    "SpecFetcher",
    "CodeFetcher",
    "CodeParser",
    "ReportGenerator",
    "DifferentialEngine",
    "DifferentialResult",
    "ClientAnalysis",
    "VerificationEngine",
    "SpecGrounding",
    "FindingVerdict",
]
