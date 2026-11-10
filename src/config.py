"""Configuration management for PRSpec."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


class Config:
    """Configuration manager for PRSpec"""

    def __init__(self, config_path: Optional[str] = None):
        """Load config from YAML + environment. Searches cwd if no path given."""
        # Load environment variables
        load_dotenv()

        # Find config file
        if config_path is None:
            config_path = self._find_config_file()

        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _find_config_file(self) -> str:
        """Find config.yaml in current or parent directories"""
        search_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd().parent / "config.yaml",
            Path(__file__).parent.parent / "config.yaml",
        ]

        for path in search_paths:
            if path.exists():
                return str(path)

        # Installed package (pip install): fall back to the bundled defaults.
        bundled = Path(__file__).parent / "default_config.yaml"
        if bundled.exists():
            return str(bundled)

        raise FileNotFoundError("config.yaml not found")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    @property
    def llm_provider(self) -> str:
        """Get the active LLM provider."""
        # Environment variable takes precedence
        env_provider = os.getenv("LLM_PROVIDER")
        if env_provider:
            return env_provider.lower()
        return self._config.get("llm", {}).get("provider", "gemini")

    @property
    def gemini_api_key(self) -> str:
        """Get Gemini API key from environment"""
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY not set in environment")
        return key

    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key from environment"""
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        return key

    @property
    def meta_api_key(self) -> str:
        """Get the Meta Model API key from the environment."""
        key = os.getenv("MODEL_API_KEY")
        if not key:
            raise ValueError("MODEL_API_KEY not set in environment")
        return key

    @property
    def meta_config(self) -> Dict[str, Any]:
        """Meta Model API configuration; META_MODEL overrides the model id."""
        conf = dict(self._config.get("llm", {}).get("meta") or {})
        conf.setdefault("model", "muse-spark-1.3")
        conf.setdefault("base_url", "https://api.meta.ai/v1")
        if os.getenv("META_MODEL"):
            conf["model"] = os.environ["META_MODEL"]
        return conf

    @property
    def azure_api_key(self) -> str:
        """Get Azure AI Foundry API key from environment"""
        key = os.getenv("AZURE_AI_API_KEY")
        if not key:
            raise ValueError("AZURE_AI_API_KEY not set in environment")
        return key

    @property
    def github_token(self) -> Optional[str]:
        """Get GitHub token from environment (optional)"""
        return os.getenv("GITHUB_TOKEN")

    @property
    def gemini_config(self) -> Dict[str, Any]:
        """Gemini configuration; ``GEMINI_MODEL`` overrides the model id."""
        conf = dict(self._config.get("llm", {}).get("gemini") or {})
        conf.setdefault("model", "gemini-3.8-flash")
        if os.getenv("GEMINI_MODEL"):
            conf["model"] = os.environ["GEMINI_MODEL"]
        return conf

    @property
    def local_config(self) -> Dict[str, Any]:
        """OpenAI-compatible local server (Ollama, vLLM, llama.cpp ...).

        ``PRSPEC_LOCAL_BASE_URL`` / ``PRSPEC_LOCAL_MODEL`` override the YAML."""
        conf = dict(self._config.get("llm", {}).get("local") or {})
        conf.setdefault("base_url", "http://localhost:11434/v1")
        conf.setdefault("model", "qwen3-coder:30b")
        if os.getenv("PRSPEC_LOCAL_BASE_URL"):
            conf["base_url"] = os.environ["PRSPEC_LOCAL_BASE_URL"]
        if os.getenv("PRSPEC_LOCAL_MODEL"):
            conf["model"] = os.environ["PRSPEC_LOCAL_MODEL"]
        return conf

    @property
    def no_cloud(self) -> bool:
        """Privacy guard: refuse any provider that sends code off the machine."""
        env = os.getenv("PRSPEC_NO_CLOUD", "")
        if env:
            return env.lower() in ("1", "true", "yes")
        return bool(self._config.get("llm", {}).get("no_cloud", False))

    @property
    def openai_config(self) -> Dict[str, Any]:
        """Get OpenAI-specific configuration"""
        conf = dict(self._config.get("llm", {}).get("openai") or {})
        conf.setdefault("model", "gpt-6.1-sol")
        if os.getenv("OPENAI_BASE_URL") and "base_url" not in conf:
            conf["base_url"] = os.environ["OPENAI_BASE_URL"]
        return conf

    @property
    def azure_config(self) -> Dict[str, Any]:
        """Get Azure AI Foundry configuration.

        The endpoint and deployment name live in the environment (they are
        per-resource), while the generation params come from config.yaml.
        Returns kwargs ready to splat into ``AzureAIAnalyzer``.
        """
        base = self._config.get("llm", {}).get("azure", {})
        cfg: Dict[str, Any] = {
            "endpoint": os.getenv("AZURE_AI_ENDPOINT", base.get("endpoint", "")),
            "model": os.getenv("AZURE_AI_DEPLOYMENT", base.get("model", "")),
            "max_tokens": base.get("max_tokens", 4096),
        }
        # Only forward temperature when explicitly configured; newer Claude
        # models reject the parameter outright.
        if base.get("temperature") is not None:
            cfg["temperature"] = base["temperature"]
        anthropic_version = os.getenv("AZURE_AI_ANTHROPIC_VERSION",
                                      base.get("anthropic_version"))
        if anthropic_version:
            cfg["anthropic_version"] = anthropic_version
        return cfg

    @property
    def azure_verify_config(self) -> Optional[Dict[str, Any]]:
        """Config for a separate verification deployment, or None to reuse the
        primary one.

        Set ``AZURE_AI_VERIFY_DEPLOYMENT`` to run the skeptic rounds on a
        cheaper model (e.g. Sonnet) while the primary analysis uses a stronger
        one (e.g. Opus). The endpoint, key, and params are shared.
        """
        verify_deployment = os.getenv("AZURE_AI_VERIFY_DEPLOYMENT")
        if not verify_deployment:
            return None
        cfg = self.azure_config
        cfg["model"] = verify_deployment
        return cfg

    @property
    def repositories(self) -> Dict[str, Any]:
        """Get repository configurations"""
        return self._config.get("repositories", {})

    @property
    def analysis_config(self) -> Dict[str, Any]:
        """Get analysis configuration"""
        return self._config.get("analysis", {})

    @property
    def focus_areas(self) -> list:
        """Get default focus areas for analysis"""
        return self.analysis_config.get("focus_areas", [])

    def get_eip_focus_areas(self, eip_number: int) -> list:
        """Focus areas for a specific EIP, falling back to defaults."""
        eips_config = self._config.get("eips", {})
        eip_config = eips_config.get(eip_number, eips_config.get(str(eip_number), {}))
        areas = eip_config.get("focus_areas", [])
        return areas if areas else self.focus_areas

    @property
    def output_config(self) -> Dict[str, Any]:
        """Get output configuration"""
        return self._config.get("output", {
            "format": "json",
            "directory": "output"
        })

    def get_repo_config(self, repo_name: str) -> Dict[str, Any]:
        """Look up a named repository config block."""
        repos = self.repositories
        if repo_name not in repos:
            raise ValueError(f"Repository '{repo_name}' not found in config")
        return repos[repo_name]

    def __repr__(self) -> str:
        return f"Config(provider={self.llm_provider}, config_path={self.config_path})"


# Convenience function for quick config access
def get_config(config_path: Optional[str] = None) -> Config:
    """Get a Config instance"""
    return Config(config_path)
