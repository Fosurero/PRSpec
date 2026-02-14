# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.4.x   | Yes                |
| < 1.4   | No                 |

## Reporting a Vulnerability

PRSpec is a security research tool for the Ethereum ecosystem. We take security seriously.

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue.**
2. Email the maintainer directly (see contact info below).
3. Include a description of the vulnerability, steps to reproduce, and potential impact.
4. Allow up to 72 hours for an initial response.

## Security Considerations

### API Keys
- API keys are loaded from environment variables only, never hardcoded.
- The `.env` file is in `.gitignore` and is never committed.

### Data Handling
- PRSpec fetches publicly available source code from GitHub.
- Code is sent to the configured LLM provider (Gemini or OpenAI) for analysis.
- No code or analysis results are stored beyond the local `output/` directory.
- No telemetry or analytics are collected.

### LLM Provider Trust
- By default, PRSpec uses Google Gemini. Code snippets are sent to Google's API.
- For sensitive codebases, consider using a local LLM backend (planned for future releases).
- Review your LLM provider's data handling policies before analyzing private code.

## Contact

Maintainer: Safi El-Hassanine
GitHub: [@Fosurero](https://github.com/Fosurero)
