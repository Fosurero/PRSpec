"""Tests for configuration loading and env-var precedence."""

import contextlib
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config, get_config

CONFIG_YAML = textwrap.dedent("""\
    llm:
      provider: openai
      gemini:
        model: gemini-test
        max_output_tokens: 111
        temperature: 0.2
      openai:
        model: gpt-test
        max_tokens: 222
        temperature: 0.3
      azure:
        endpoint: https://config.example/anthropic/v1/messages
        model: config-deployment
        max_tokens: 333
        temperature: 0.4
        anthropic_version: "2024-01-01"
    repositories:
      go-ethereum:
        url: https://github.com/ethereum/go-ethereum
        branch: master
    analysis:
      focus_areas:
        - base_fee_calculation
        - gas_limit_validation
    eips:
      1559:
        focus_areas:
          - fee_burn
      4844: {}
    output:
      format: markdown
      directory: reports
""")

# Env vars the Config reads; cleared so a developer's real environment (or a
# .env file picked up by load_dotenv) cannot leak into assertions.
_ENV_KEYS = [
    "LLM_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "AZURE_AI_API_KEY",
    "GITHUB_TOKEN", "AZURE_AI_ENDPOINT", "AZURE_AI_DEPLOYMENT",
    "AZURE_AI_ANTHROPIC_VERSION", "AZURE_AI_VERIFY_DEPLOYMENT",
]


@contextlib.contextmanager
def _clean_env(**overrides):
    """Run with only the given PRSpec env vars set, and no .env side effects."""
    env = {k: v for k, v in os.environ.items() if k not in _ENV_KEYS}
    env.update(overrides)
    with mock.patch.dict(os.environ, env, clear=True), \
            mock.patch("src.config.load_dotenv"):
        yield


class ConfigTestCase(unittest.TestCase):
    """Base case that writes a config.yaml into a temp directory."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="prspec_config_")
        self.config_path = Path(self.tmpdir, "config.yaml")
        self.config_path.write_text(CONFIG_YAML)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _config(self):
        return Config(str(self.config_path))


class TestConfigLoading(ConfigTestCase):
    def test_loads_explicit_path(self):
        with _clean_env():
            cfg = self._config()
        self.assertEqual(cfg.config_path, self.config_path)

    def test_finds_config_in_cwd(self):
        with _clean_env(), mock.patch.object(Path, "cwd", return_value=Path(self.tmpdir)):
            cfg = Config()
        self.assertEqual(cfg.config_path, self.config_path)

    def test_finds_config_in_parent_dir(self):
        nested = Path(self.tmpdir, "nested")
        nested.mkdir()
        with _clean_env(), mock.patch.object(Path, "cwd", return_value=nested):
            cfg = Config()
        self.assertEqual(cfg.config_path, self.config_path)

    def test_missing_config_raises(self):
        empty = Path(self.tmpdir, "empty", "deep")
        empty.mkdir(parents=True)
        # Also point the package-relative fallback at a config-less directory.
        with _clean_env(), \
                mock.patch.object(Path, "cwd", return_value=empty), \
                mock.patch("src.config.__file__", str(empty / "src" / "config.py")):
            with self.assertRaises(FileNotFoundError):
                Config()

    def test_get_config_helper(self):
        with _clean_env():
            cfg = get_config(str(self.config_path))
        self.assertIsInstance(cfg, Config)

    def test_repr_includes_provider_and_path(self):
        with _clean_env():
            text = repr(self._config())
        self.assertIn("provider=openai", text)
        self.assertIn(str(self.config_path), text)


class TestProviderSelection(ConfigTestCase):
    def test_provider_from_yaml(self):
        with _clean_env():
            self.assertEqual(self._config().llm_provider, "openai")

    def test_env_overrides_yaml_and_is_lowercased(self):
        with _clean_env(LLM_PROVIDER="AZURE"):
            self.assertEqual(self._config().llm_provider, "azure")

    def test_defaults_to_gemini_when_unset(self):
        path = Path(self.tmpdir, "bare.yaml")
        path.write_text("output: {}\n")
        with _clean_env():
            self.assertEqual(Config(str(path)).llm_provider, "gemini")


class TestApiKeys(ConfigTestCase):
    def test_gemini_key_returned(self):
        with _clean_env(GEMINI_API_KEY="g-key"):
            self.assertEqual(self._config().gemini_api_key, "g-key")

    def test_gemini_key_missing_raises(self):
        with _clean_env():
            with self.assertRaises(ValueError):
                _ = self._config().gemini_api_key

    def test_openai_key_returned(self):
        with _clean_env(OPENAI_API_KEY="o-key"):
            self.assertEqual(self._config().openai_api_key, "o-key")

    def test_openai_key_missing_raises(self):
        with _clean_env():
            with self.assertRaises(ValueError):
                _ = self._config().openai_api_key

    def test_azure_key_returned(self):
        with _clean_env(AZURE_AI_API_KEY="a-key"):
            self.assertEqual(self._config().azure_api_key, "a-key")

    def test_azure_key_missing_raises(self):
        with _clean_env():
            with self.assertRaises(ValueError):
                _ = self._config().azure_api_key

    def test_github_token_optional(self):
        with _clean_env():
            self.assertIsNone(self._config().github_token)
        with _clean_env(GITHUB_TOKEN="gh-token"):
            self.assertEqual(self._config().github_token, "gh-token")


class TestProviderConfigs(ConfigTestCase):
    def test_gemini_config_from_yaml(self):
        with _clean_env():
            self.assertEqual(self._config().gemini_config["model"], "gemini-test")

    def test_openai_config_from_yaml(self):
        with _clean_env():
            self.assertEqual(self._config().openai_config["max_tokens"], 222)

    def test_provider_configs_fall_back_to_defaults(self):
        path = Path(self.tmpdir, "bare.yaml")
        path.write_text("output: {}\n")
        with _clean_env():
            cfg = Config(str(path))
            self.assertEqual(cfg.gemini_config["model"], "gemini-2.5-pro")
            self.assertEqual(cfg.openai_config["model"], "gpt-4-turbo-preview")

    def test_azure_config_from_yaml(self):
        with _clean_env():
            azure = self._config().azure_config
        self.assertEqual(azure["endpoint"], "https://config.example/anthropic/v1/messages")
        self.assertEqual(azure["model"], "config-deployment")
        self.assertEqual(azure["max_tokens"], 333)
        self.assertEqual(azure["temperature"], 0.4)
        self.assertEqual(azure["anthropic_version"], "2024-01-01")

    def test_azure_env_overrides_endpoint_and_deployment(self):
        with _clean_env(AZURE_AI_ENDPOINT="https://env.example/v1",
                        AZURE_AI_DEPLOYMENT="env-deployment",
                        AZURE_AI_ANTHROPIC_VERSION="2025-01-01"):
            azure = self._config().azure_config
        self.assertEqual(azure["endpoint"], "https://env.example/v1")
        self.assertEqual(azure["model"], "env-deployment")
        self.assertEqual(azure["anthropic_version"], "2025-01-01")

    def test_azure_config_omits_unset_temperature_and_version(self):
        path = Path(self.tmpdir, "bare.yaml")
        path.write_text("llm:\n  azure:\n    max_tokens: 10\n")
        with _clean_env():
            azure = Config(str(path)).azure_config
        self.assertNotIn("temperature", azure)
        self.assertNotIn("anthropic_version", azure)
        self.assertEqual(azure["endpoint"], "")
        self.assertEqual(azure["model"], "")

    def test_azure_verify_config_none_without_env(self):
        with _clean_env():
            self.assertIsNone(self._config().azure_verify_config)

    def test_azure_verify_config_swaps_only_the_deployment(self):
        with _clean_env(AZURE_AI_VERIFY_DEPLOYMENT="cheap-deployment"):
            cfg = self._config()
            verify = cfg.azure_verify_config
            self.assertEqual(verify["model"], "cheap-deployment")
            self.assertEqual(verify["endpoint"], cfg.azure_config["endpoint"])
            # The primary config must not be mutated by the verify lookup.
            self.assertEqual(cfg.azure_config["model"], "config-deployment")


class TestAnalysisAndOutputConfig(ConfigTestCase):
    def test_repositories(self):
        with _clean_env():
            repos = self._config().repositories
        self.assertIn("go-ethereum", repos)

    def test_get_repo_config(self):
        with _clean_env():
            repo = self._config().get_repo_config("go-ethereum")
        self.assertEqual(repo["branch"], "master")

    def test_get_repo_config_unknown_raises(self):
        with _clean_env():
            with self.assertRaises(ValueError):
                self._config().get_repo_config("erigon")

    def test_focus_areas(self):
        with _clean_env():
            self.assertEqual(self._config().focus_areas,
                             ["base_fee_calculation", "gas_limit_validation"])

    def test_eip_focus_areas_override_defaults(self):
        with _clean_env():
            self.assertEqual(self._config().get_eip_focus_areas(1559), ["fee_burn"])

    def test_eip_focus_areas_fall_back_to_defaults(self):
        with _clean_env():
            cfg = self._config()
            self.assertEqual(cfg.get_eip_focus_areas(4844), cfg.focus_areas)
            self.assertEqual(cfg.get_eip_focus_areas(9999), cfg.focus_areas)

    def test_eip_focus_areas_accept_string_keys(self):
        path = Path(self.tmpdir, "strkeys.yaml")
        path.write_text('eips:\n  "1559":\n    focus_areas: [from_string_key]\n')
        with _clean_env():
            self.assertEqual(Config(str(path)).get_eip_focus_areas(1559),
                             ["from_string_key"])

    def test_analysis_config(self):
        with _clean_env():
            self.assertIn("focus_areas", self._config().analysis_config)

    def test_output_config_from_yaml(self):
        with _clean_env():
            output = self._config().output_config
        self.assertEqual(output["directory"], "reports")

    def test_output_config_defaults(self):
        path = Path(self.tmpdir, "bare.yaml")
        path.write_text("llm: {}\n")
        with _clean_env():
            output = Config(str(path)).output_config
        self.assertEqual(output, {"format": "json", "directory": "output"})


if __name__ == "__main__":
    unittest.main()
