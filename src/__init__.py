"""
PRSpec - Ethereum Specification Compliance Checker
Author: Safi El-Hassanine

A tool to analyze Ethereum client implementations against official specifications
using LLM-powered analysis (Google Gemini 1.5 Pro / OpenAI GPT-4).
"""

__version__ = "1.0.0"
__author__ = "Safi El-Hassanine"

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
