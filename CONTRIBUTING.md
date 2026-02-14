# Contributing to PRSpec

Thank you for your interest in contributing to PRSpec! This project aims to improve Ethereum protocol security by automating specification compliance checking.

## Getting Started

1. **Fork** the repository and clone your fork.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your API key.
4. Run the test suite to make sure everything works:
   ```bash
   python -m pytest tests/ -v
   ```

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes. Follow the existing code style.
3. Add or update tests for any new functionality.
4. Run the full test suite:
   ```bash
   python -m pytest tests/ -v
   ```
5. Submit a pull request against `main`.

## What to Contribute

### High-Impact Areas
- **New EIP file mappings**: Add implementation file paths for EIPs we track (see `src/code_fetcher.py`).
- **New client support**: Add file registries for Prysm, Lighthouse, or other Ethereum clients.
- **Parser improvements**: Better regex or tree-sitter patterns for Go, C#, Java, Rust, Python.
- **Report enhancements**: Improved HTML/Markdown output, new visualizations.

### Adding a New Client
1. Add the client entry in `CodeFetcher.CLIENTS` in `src/code_fetcher.py`.
2. Add a language parser in `src/parser.py` if the language isn't supported yet.
3. Verify file paths exist via the GitHub API.
4. Add tests in `tests/test_multi_client.py`.

### Adding a New EIP
1. Add the EIP entry in `SpecFetcher.EIP_REGISTRY` in `src/spec_fetcher.py`.
2. Add file mappings per client in `CodeFetcher.CLIENTS` in `src/code_fetcher.py`.
3. Add EIP keywords in `CodeParser.EIP_KEYWORDS` in `src/parser.py`.
4. Add tests.

## Code Style

- Python 3.9+ compatible.
- Type hints on all public methods.
- Docstrings on all classes and public methods.
- No unnecessary dependencies.

## Testing

- All new code must have tests.
- Tests should not require an API key (use mocks for LLM calls).
- Run with: `python -m pytest tests/ -v`

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests.
- For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
