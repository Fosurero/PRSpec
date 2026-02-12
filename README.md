<div align="center">

  <h1>PRSpec - Ethereum Specification Compliance Checker</h1>

  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  </a>

  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
  </a>

  <a href="https://ai.google.dev/">
    <img src="https://img.shields.io/badge/Powered%20by-Gemini%202.5%20Pro-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  </a>

  <img src="https://img.shields.io/badge/Stable-Release-brightgreen?style=for-the-badge" />

  <a href="https://github.com/Fosurero/PRSpec/tree/development">
    <img src="https://img.shields.io/badge/Status-Active%20Development-blueviolet?style=for-the-badge" />
  </a>

</div>
<br>



**Author:** Safi El-Hassanine

PRSpec is an LLM-powered tool for analyzing Ethereum client implementations against official EIP specifications. It uses **Google Gemini 2.5 Pro** (with OpenAI GPT-4 as an alternative) to intelligently compare specification documents with actual code implementations.

## 🌟 Features

- **Multi-EIP Support**: Analyze implementations of EIP-1559, EIP-4844, and more
- **Multiple Clients**: Support for go-ethereum, Prysm, Lighthouse, Nethermind, Besu
- **Gemini 1.5 Pro**: Leverages 2M token context window for comprehensive analysis
- **Multiple Output Formats**: JSON, Markdown, and HTML reports
- **Intelligent Parsing**: Extracts relevant functions using regex and tree-sitter
- **CLI Interface**: Easy-to-use command line tool with Rich formatting

## 🎥 Demo

### Video Demo
[![PRSpec Demo](https://img.youtube.com/vi/v7UtBAxigKc/0.jpg)](https://www.youtube.com/watch?v=v7UtBAxigKc)

*Click to watch PRSpec analyzing EIP-1559 compliance in real-time*

### Screenshot
![PRSpec Analysis Results](docs/demo-result.png)

*Live analysis of go-ethereum's EIP-1559 implementation showing detected issues*

## 📋 Project Structure

```
prspec/
├── src/
│   ├── __init__.py          # Package exports
│   ├── config.py            # Configuration management
│   ├── spec_fetcher.py      # Fetches EIP specifications
│   ├── code_fetcher.py      # Fetches client implementations
│   ├── parser.py            # Code parsing (Go, Python, etc.)
│   ├── analyzer.py          # LLM analysis (Gemini/OpenAI)
│   ├── report_generator.py  # Report generation
│   └── cli.py               # Command-line interface
├── tests/
│   └── test_eip1559.py      # Unit tests
├── output/                   # Generated reports
├── requirements.txt
├── config.yaml              # Configuration file
├── .env.example             # Environment template
├── .env                     # Your API keys (git-ignored)
├── run_demo.py              # Demo script
└── README.md
```

## 🚀 Quick Start

### 1. Installation

```bash
cd prspec

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

The project is pre-configured with a Gemini API key. You can also set up your own:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys
# GEMINI_API_KEY=your_key_here
```

Get your Gemini API key from: https://makersuite.google.com/app/apikey

### 3. Run the Demo

```bash
# Run the full demo
python run_demo.py

# Quick API test
python run_demo.py --test
```

### 4. Use the CLI

```bash
# Analyze EIP-1559 compliance in go-ethereum
python -m src.cli analyze --eip 1559 --client go-ethereum --output markdown

# Fetch an EIP specification
python -m src.cli fetch-spec --eip 1559

# List implementation files
python -m src.cli list-files --client go-ethereum --eip 1559

# Check configuration
python -m src.cli check-config
```

## 🔧 Configuration

### config.yaml

```yaml
llm:
  provider: gemini  # or "openai"
  
  gemini:
    model: gemini-1.5-pro-latest
    max_output_tokens: 8192
    temperature: 0.1
  
  openai:
    model: gpt-4-turbo-preview
    max_tokens: 4096
    temperature: 0.1

repositories:
  go_ethereum:
    url: https://github.com/ethereum/go-ethereum
    branch: master
    eip1559_paths:
      - consensus/misc/eip1559.go
      - core/types/transaction.go

analysis:
  focus_areas:
    - base_fee_calculation
    - gas_limit_validation
    - fee_cap_check
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Yes (if using Gemini) |
| `OPENAI_API_KEY` | OpenAI API key | Yes (if using OpenAI) |
| `GITHUB_TOKEN` | GitHub token for higher rate limits | No |
| `LLM_PROVIDER` | Override default provider | No |

## 📊 Analysis Output

### JSON Report
```json
{
  "status": "PARTIAL_MATCH",
  "confidence": 85,
  "issues": [
    {
      "type": "EDGE_CASE",
      "severity": "MEDIUM",
      "spec_reference": "base fee increase by 12.5%",
      "code_location": "CalcBaseFee, line 45",
      "description": "Edge case when gas used equals target not handled",
      "suggestion": "Add explicit check for equality case"
    }
  ],
  "summary": "Implementation mostly compliant with minor edge case handling issues"
}
```

### Markdown Report
Generated reports include:
- Executive summary with overall compliance status
- Detailed findings per file
- Issue severity breakdown (High/Medium/Low)
- Specific code locations and suggestions

### HTML Report
Beautiful, interactive HTML reports with:
- Summary cards
- Color-coded severity indicators
- Expandable issue details

## 🧪 Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_eip1559.py::TestAnalyzer -v

# Run with coverage
python -m pytest tests/ --cov=src
```

## 🔌 API Usage

### Programmatic Analysis

```python
from src.config import Config
from src.analyzer import GeminiAnalyzer
from src.spec_fetcher import SpecFetcher
from src.code_fetcher import CodeFetcher

# Initialize
config = Config()
analyzer = GeminiAnalyzer(api_key=config.gemini_api_key)

# Fetch spec and code
spec_fetcher = SpecFetcher()
code_fetcher = CodeFetcher()

spec = spec_fetcher.fetch_eip(1559)
code = code_fetcher.fetch_geth_file("consensus/misc/eip1559.go")

# Analyze
result = analyzer.analyze_compliance(
    spec_text=spec,
    code_text=code,
    context={"file_name": "eip1559.go", "language": "go"}
)

print(f"Status: {result.status}")
print(f"Confidence: {result.confidence}%")
for issue in result.issues:
    print(f"  [{issue['severity']}] {issue['description']}")
```

### Quick One-Shot Analysis

```python
from src.analyzer import quick_analyze

result = quick_analyze(
    spec_text="Base fee must increase by 12.5% when blocks are full",
    code_text="func CalcBaseFee(...) {...}",
    api_key="your_api_key",
    provider="gemini"
)
```

## 🤖 Why Gemini 2.5 Pro?

| Feature | Gemini 2.5 Pro | GPT-4 Turbo |
|---------|----------------|-------------|
| Context Window | **1M tokens** | 128K tokens |
| Code Analysis | Excellent | Excellent |
| Cost | Lower | Higher |
| Speed | Fast | Moderate |

Gemini's massive context window allows PRSpec to:
- Analyze entire files at once
- Compare multiple implementation files simultaneously
- Include full EIP specifications without truncation

## 📝 Supported EIPs

- **EIP-1559**: Fee market change (primary focus)
- **EIP-4844**: Shard Blob Transactions
- **EIP-2930**: Access lists
- More coming soon...

## 🔐 Security Notes

- Never commit your `.env` file
- API keys are loaded from environment variables
- Cached data is stored locally in `.spec_cache` and `.code_cache`

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

MIT.

## 👤 Author

**Safi El-Hassanine**

---

Built with ❤️ for the Ethereum ecosystem
