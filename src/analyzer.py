"""LLM-based spec compliance analysis (Gemini, OpenAI, and Azure AI backends)."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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

    def analyze_multiple_files(self, spec_text: str, code_files: Dict[str, str],
                               context: dict) -> AnalysisResult:
        """Concatenate multiple files and analyze in one shot."""
        code_sections = []
        for file_path, code in code_files.items():
            code_sections.append(f"=== FILE: {file_path} ===\n{code}")
        combined_code = "\n\n".join(code_sections)
        return self.analyze_compliance(spec_text, combined_code, context)

    def _build_analysis_prompt(self, spec_text: str, code_text: str,
                               context: dict) -> str:
        """Build the analysis prompt.

        The prompt is EIP-agnostic: it reads the EIP number and title from
        *context* so the same method works for EIP-1559, EIP-4844, or any
        future EIP.
        """
        eip_number = context.get("eip_number", "")
        eip_title = context.get("eip_title", "")
        eip_label = f"EIP-{eip_number}" if eip_number else "the Ethereum specification"
        if eip_title:
            eip_label = eip_title

        return f"""
You are an expert Ethereum protocol security researcher and auditor.

TASK: Compare the {eip_label} specification with the implementation code and identify any compliance issues.

=== SPECIFICATION ===
{spec_text}

=== CODE IMPLEMENTATION ===
{code_text}

=== CONTEXT ===
- EIP: {eip_number or 'unknown'}
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

    def _build_refutation_prompt(self, finding: Dict[str, Any], spec_text: str,
                                 context: dict) -> str:
        """Frame a single finding for skeptical re-examination.

        Returns text suitable for the *spec_text* slot of
        :meth:`analyze_compliance`.  The idea is to hand a second, independent
        reviewer the original specification plus the claim a prior pass made,
        and ask them to verify it from scratch rather than trust it.  A real
        deviation comes back as an issue; a false positive comes back as
        FULL_MATCH with no issues.
        """
        claim = (
            f"- type: {finding.get('type', 'UNKNOWN')}\n"
            f"- severity: {finding.get('severity', 'UNKNOWN')}\n"
            f"- description: {finding.get('description', '')}\n"
            f"- claimed spec reference: \"{finding.get('spec_reference', '')}\"\n"
            f"- claimed code location: {finding.get('code_location', '')}"
        )

        return f"""{spec_text}

--- INDEPENDENT VERIFICATION TASK ---
A prior automated reviewer flagged the deviation below. Do not assume it is
correct. Re-check it yourself against the specification above and the code that
follows. Only report an issue if you can independently confirm a genuine
deviation; if the code actually satisfies the specification, return status
FULL_MATCH with an empty issues array. When the evidence is ambiguous, prefer
FULL_MATCH over repeating an unverified claim.

Flagged finding under review:
{claim}
"""

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks
        and truncated output from the model."""
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = re.sub(r'^```(?:json)?\s*\n?', '', text)
            text = re.sub(r'\n?```\s*$', '', text)

        # Strip surrounding prose — some models wrap JSON in explanation text
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract the outermost JSON object (greedy)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Attempt to repair truncated JSON (common with LLM output limits).
        brace_start = text.find('{')
        if brace_start != -1:
            fragment = text[brace_start:]
            # Try progressively more aggressive closings
            for suffix in [
                '}',
                '"}',
                '"]}',
                '"}]}',
                '"}}',
                '"} ]}',
                '"}],"summary":"Analysis truncated"}',
                '"}], "summary": "Analysis truncated"}',
                '"],"summary":"Analysis truncated"}',
                '"], "summary": "Analysis truncated"}',
                '"}, "summary": "Analysis truncated"}',
            ]:
                try:
                    return json.loads(fragment + suffix)
                except json.JSONDecodeError:
                    continue

            # Last resort: try to find just the first valid JSON object
            # by scanning closing braces from the end
            for end in range(len(fragment) - 1, 0, -1):
                if fragment[end] == '}':
                    try:
                        return json.loads(fragment[:end + 1])
                    except json.JSONDecodeError:
                        continue

        return {
            "status": "ERROR",
            "confidence": 0,
            "issues": [],
            "summary": f"Failed to parse response ({len(text)} chars). "
                       f"The model output may have been truncated."
        }


class GeminiAnalyzer(BaseAnalyzer):
    """Gemini-backed analyzer. Uses the large context window to compare
    full spec text against full source files in a single request."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro",
                 max_output_tokens: int = 8192, temperature: float = 0.1):
        """Configure the Gemini model and generation params."""
        try:
            from google import genai  # type: ignore[import-untyped]
            from google.genai import types as genai_types  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError("google-genai not installed. Run: pip install google-genai")

        self._genai_types = genai_types
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    def analyze_compliance(self, spec_text: str, code_text: str,
                          context: dict) -> AnalysisResult:
        """Send spec + code to Gemini and parse the structured JSON response."""
        prompt = self._build_analysis_prompt(spec_text, code_text, context)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=self._genai_types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                ),
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

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "provider": "gemini",
            "model": self.model_name,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
        }


class OpenAIAnalyzer(BaseAnalyzer):
    """GPT-4 backed analyzer, alternative to Gemini."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview",
                 max_tokens: int = 4096, temperature: float = 0.1):
        """Configure the OpenAI client."""
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
        """Send spec + code to OpenAI and parse the JSON response."""
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
        }


class AzureAIAnalyzer(BaseAnalyzer):
    """Analyzer backed by a model deployed in your own Azure AI Foundry resource
    (e.g. Claude Sonnet/Opus).

    Foundry deployments expose an OpenAI-compatible chat-completions route, so
    this reuses the same request/response shape as :class:`OpenAIAnalyzer` while
    pointing the client at your private endpoint and key. The deployment name
    plays the role of the model id.
    """

    def __init__(self, api_key: str, endpoint: str, model: str,
                 api_version: Optional[str] = None, max_tokens: int = 4096,
                 temperature: float = 0.1):
        """Configure an OpenAI client aimed at the Foundry endpoint."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

        if not endpoint:
            raise ValueError("Azure AI endpoint URL is required (set AZURE_AI_ENDPOINT)")
        if not model:
            raise ValueError("Azure AI deployment name is required (set AZURE_AI_DEPLOYMENT)")

        # Foundry serves an OpenAI-compatible path; resources fronted by the
        # Azure gateway also expect the key in an `api-key` header and an
        # `api-version` query string. Sending both auth styles keeps this working
        # across the v1 endpoint and the classic gateway without extra config.
        default_query = {"api-version": api_version} if api_version else None
        self.client = OpenAI(
            api_key=api_key,
            base_url=endpoint.rstrip("/"),
            default_query=default_query,
            default_headers={"api-key": api_key},
        )
        self.model = model
        self.api_version = api_version
        self.max_tokens = max_tokens
        self.temperature = temperature

    def analyze_compliance(self, spec_text: str, code_text: str,
                          context: dict) -> AnalysisResult:
        """Send spec + code to the Foundry deployment and parse the JSON."""
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
                summary=f"Azure AI analysis failed: {str(e)}"
            )

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "provider": "azure",
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


def get_analyzer(provider: str = "gemini", **kwargs) -> BaseAnalyzer:
    """Factory: return a GeminiAnalyzer, OpenAIAnalyzer, or AzureAIAnalyzer."""
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

    elif provider == "azure":
        required = ["api_key", "endpoint", "model"]
        for key in required:
            if key not in kwargs:
                raise ValueError(f"Missing required parameter: {key}")
        return AzureAIAnalyzer(**kwargs)

    else:
        raise ValueError(
            f"Unknown provider: {provider}. Use 'gemini', 'openai', or 'azure'."
        )
