"""
LLM Analyzer for PRSpec
Author: Safi El-Hassanine

Analyzes specification compliance using LLM (Google Gemini or OpenAI GPT-4).
Primary: Google Gemini 1.5 Pro (supports up to 2M tokens!)
Alternative: OpenAI GPT-4
"""

import json
import re
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """Result of a compliance analysis"""
    status: str  # FULL_MATCH, PARTIAL_MATCH, MISSING, UNCERTAIN, ERROR
    confidence: int  # 0-100
    issues: List[Dict[str, Any]]
    summary: str
    raw_response: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "issues": self.issues,
            "summary": self.summary,
        }
    
    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0
    
    @property
    def high_severity_issues(self) -> List[Dict[str, Any]]:
        return [i for i in self.issues if i.get("severity") == "HIGH"]


class BaseAnalyzer(ABC):
    """Base class for LLM analyzers"""
    
    @abstractmethod
    def analyze_compliance(self, spec_text: str, code_text: str, 
                          context: dict) -> AnalysisResult:
        """Analyze code compliance with specification"""
        pass
    
    def _build_analysis_prompt(self, spec_text: str, code_text: str, 
                               context: dict) -> str:
        """Build the analysis prompt"""
        return f"""
You are an expert Ethereum protocol security researcher and auditor.

TASK: Compare the EIP-1559 specification with the implementation code and identify any compliance issues.

=== SPECIFICATION ===
{spec_text}

=== CODE IMPLEMENTATION ===
{code_text}

=== CONTEXT ===
- File: {context.get('file_name', 'unknown')}
- Function: {context.get('function_name', 'unknown')}
- Language: {context.get('language', 'unknown')}
- Focus Areas: {context.get('focus_areas', [])}

=== ANALYSIS REQUIREMENTS ===
1. Does the code fully implement ALL requirements from the specification?
2. Are there any deviations from the specified behavior?
3. Are there missing validation checks?
4. Are there edge cases not handled?
5. Could any deviation lead to security issues or consensus failures?

=== RESPONSE FORMAT ===
Respond ONLY with valid JSON in this exact format:
{{
    "status": "FULL_MATCH" | "PARTIAL_MATCH" | "MISSING" | "UNCERTAIN",
    "confidence": <integer 0-100>,
    "issues": [
        {{
            "type": "MISSING_CHECK" | "INCORRECT_LOGIC" | "EDGE_CASE" | "DEVIATION",
            "severity": "HIGH" | "MEDIUM" | "LOW",
            "spec_reference": "<exact text from specification>",
            "code_location": "<function name and approximate line>",
            "description": "<detailed explanation of the issue>",
            "potential_impact": "<what could go wrong>",
            "suggestion": "<how to fix>"
        }}
    ],
    "summary": "<2-3 sentence overall assessment>"
}}

Important: If the code correctly implements the spec, return status "FULL_MATCH" with empty issues array.
"""
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks"""
        text = response_text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```"):
            # Remove opening ```json or ```
            text = re.sub(r'^```(?:json)?\s*\n?', '', text)
            # Remove closing ```
            text = re.sub(r'\n?```\s*$', '', text)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            return {
                "status": "ERROR",
                "confidence": 0,
                "issues": [],
                "summary": f"Failed to parse response: {str(e)}"
            }


class GeminiAnalyzer(BaseAnalyzer):
    """
    Analyzer using Google Gemini 2.5 Pro
    
    Advantages:
    - Up to 1 million token context window (huge!)
    - Can analyze entire files or multiple files at once
    - Better for long code + spec comparison
    - More cost-effective than GPT-4
    """
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-pro",
                 max_output_tokens: int = 8192, temperature: float = 0.1):
        """
        Initialize Gemini analyzer.
        
        Args:
            api_key: Google API key from https://makersuite.google.com/app/apikey
            model: Gemini model to use
            max_output_tokens: Maximum tokens in response
            temperature: Temperature for generation (0.0-1.0)
        """
        try:
            import google.generativeai as genai
            self.genai = genai
        except ImportError:
            raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")
        
        genai.configure(api_key=api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
    
    def analyze_compliance(self, spec_text: str, code_text: str, 
                          context: dict) -> AnalysisResult:
        """
        Analyze code compliance with specification using Gemini.
        
        Args:
            spec_text: The specification text
            code_text: The implementation code
            context: Additional context (file_name, function_name, etc.)
            
        Returns:
            AnalysisResult with findings
        """
        prompt = self._build_analysis_prompt(spec_text, code_text, context)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                )
            )
            
            result = self._parse_json_response(response.text)
            
            return AnalysisResult(
                status=result.get("status", "UNCERTAIN"),
                confidence=result.get("confidence", 0),
                issues=result.get("issues", []),
                summary=result.get("summary", ""),
                raw_response=response.text
            )
            
        except Exception as e:
            return AnalysisResult(
                status="ERROR",
                confidence=0,
                issues=[],
                summary=f"Gemini analysis failed: {str(e)}"
            )
    
    def analyze_multiple_files(self, spec_text: str, code_files: Dict[str, str],
                               context: dict) -> AnalysisResult:
        """
        Analyze multiple code files against a specification.
        Gemini's large context window makes this feasible.
        
        Args:
            spec_text: The specification text
            code_files: Dictionary mapping file paths to code content
            context: Additional context
            
        Returns:
            AnalysisResult with findings across all files
        """
        # Build combined code section
        code_sections = []
        for file_path, code in code_files.items():
            code_sections.append(f"=== FILE: {file_path} ===\n{code}")
        
        combined_code = "\n\n".join(code_sections)
        
        return self.analyze_compliance(spec_text, combined_code, context)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "provider": "gemini",
            "model": self.model_name,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "context_window": "1M tokens"
        }


class OpenAIAnalyzer(BaseAnalyzer):
    """
    Analyzer using OpenAI GPT-4
    
    Alternative to Gemini, useful when:
    - You need GPT-4's specific reasoning patterns
    - Gemini API is unavailable
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview",
                 max_tokens: int = 4096, temperature: float = 0.1):
        """
        Initialize OpenAI analyzer.
        
        Args:
            api_key: OpenAI API key
            model: Model to use (gpt-4, gpt-4-turbo-preview, etc.)
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation
        """
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")
        
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
    
    def analyze_compliance(self, spec_text: str, code_text: str, 
                          context: dict) -> AnalysisResult:
        """
        Analyze code compliance with specification using OpenAI.
        
        Args:
            spec_text: The specification text
            code_text: The implementation code
            context: Additional context
            
        Returns:
            AnalysisResult with findings
        """
        prompt = self._build_analysis_prompt(spec_text, code_text, context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Ethereum protocol security researcher. Respond only with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            response_text = response.choices[0].message.content
            result = self._parse_json_response(response_text)
            
            return AnalysisResult(
                status=result.get("status", "UNCERTAIN"),
                confidence=result.get("confidence", 0),
                issues=result.get("issues", []),
                summary=result.get("summary", ""),
                raw_response=response_text
            )
            
        except Exception as e:
            return AnalysisResult(
                status="ERROR",
                confidence=0,
                issues=[],
                summary=f"OpenAI analysis failed: {str(e)}"
            )
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "provider": "openai",
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "context_window": "128K tokens (GPT-4 Turbo)"
        }


def get_analyzer(provider: str = "gemini", **kwargs) -> BaseAnalyzer:
    """
    Factory function to get the appropriate analyzer.
    
    Args:
        provider: "gemini" or "openai"
        **kwargs: Provider-specific configuration
        
    Returns:
        Configured analyzer instance
    """
    provider = provider.lower()
    
    if provider == "gemini":
        required = ["api_key"]
        for key in required:
            if key not in kwargs:
                raise ValueError(f"Missing required parameter: {key}")
        return GeminiAnalyzer(**kwargs)
    
    elif provider == "openai":
        required = ["api_key"]
        for key in required:
            if key not in kwargs:
                raise ValueError(f"Missing required parameter: {key}")
        return OpenAIAnalyzer(**kwargs)
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'gemini' or 'openai'.")


# Convenience function for quick analysis
def quick_analyze(spec_text: str, code_text: str, 
                  api_key: str, provider: str = "gemini") -> AnalysisResult:
    """
    Quick one-shot analysis.
    
    Args:
        spec_text: Specification text
        code_text: Code to analyze
        api_key: API key for the provider
        provider: LLM provider to use
        
    Returns:
        AnalysisResult
    """
    analyzer = get_analyzer(provider, api_key=api_key)
    return analyzer.analyze_compliance(spec_text, code_text, {})
