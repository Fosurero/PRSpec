"""Configuration management for PRSpec."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
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
        
        raise FileNotFoundError("config.yaml not found")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    @property
    def llm_provider(self) -> str:
        """Get the active LLM provider (gemini or openai)"""
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
    def github_token(self) -> Optional[str]:
        """Get GitHub token from environment (optional)"""
        return os.getenv("GITHUB_TOKEN")
    
    @property
    def gemini_config(self) -> Dict[str, Any]:
        """Get Gemini-specific configuration"""
        return self._config.get("llm", {}).get("gemini", {
            "model": "gemini-2.5-flash",
            "max_output_tokens": 8192,
            "temperature": 0.1
        })
    
    @property
    def openai_config(self) -> Dict[str, Any]:
        """Get OpenAI-specific configuration"""
        return self._config.get("llm", {}).get("openai", {
            "model": "gpt-4-turbo-preview",
            "max_tokens": 4096,
            "temperature": 0.1
        })
    
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
