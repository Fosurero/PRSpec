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

  <img src="https://img.shields.io/badge/v1.1.0-Release-brightgreen?style=for-the-badge" />

  <a href="https://github.com/Fosurero/PRSpec/tree/development">
    <img src="https://img.shields.io/badge/Status-Active%20Development-blueviolet?style=for-the-badge" />
  </a>

  <a href="https://github.com/Fosurero/PRSpec/milestone/1">
    <img src="https://img.shields.io/badge/ESP-Grant%20Application-627EEA?style=for-the-badge&logo=ethereum&logoColor=white" />
  </a>

</div>
<br>



**Author:** Safi El-Hassanine

PRSpec is an LLM-powered tool for analyzing Ethereum client implementations against official EIP specifications. It uses **Google Gemini 2.5 Pro** (with OpenAI GPT-4 as an alternative) to intelligently compare specification documents with actual code implementations.

> **ESP RFP Context:** PRSpec is being developed under the Ethereum Foundation's ESP program for *Integrating LLMs into Ethereum Protocol Security Research*. See [GRANT_PROPOSAL.md](GRANT_PROPOSAL.md) for the full proposal.

## 🌟 Features

- **Multi-EIP Architecture**: Generalized registry-based pipeline — analyze any EIP, not just one
- **EIP-1559 & EIP-4844 Support**: Full file mappings, keywords, and focus areas for both
- **Multiple Clients**: Go-ethereum (with per-EIP file paths), Prysm, Lighthouse, Nethermind, Besu
- **Gemini 2.5 Pro**: Leverages 1M+ token context window for comprehensive analysis
- **Multiple Output Formats**: JSON, Markdown, and HTML reports
- **Intelligent Parsing**: Per-EIP keyword detection extracts relevant functions automatically
- **Consensus + Execution Specs**: Fetches from both `ethereum/EIPs`, `ethereum/execution-specs`, and `ethereum/consensus-specs`
- **CLI Interface**: Easy-to-use command line tool with Rich formatting

## 🎥 Demo

### Video Demo
[![PRSpec Demo](https://img.youtube.com/vi/v7UtBAxigKc/0.jpg)](https://www.youtube.com/watch?v=v7UtBAxigKc)

*Click to watch PRSpec analyzing EIP-1559 compliance in real-time*

### Screenshot
![PRSpec Analysis Results](docs/demo-result.png)

*Live analysis of go-ethereum's EIP-1559 implementation showing detected issues*

## 📝 Supported EIPs

| EIP | Title | Spec | Geth Files | Focus Areas |
|-----|-------|------|------------|-------------|
| **1559** | Fee market change | ✅ EIP + Execution | ✅ 3 files | base fee, gas limit, fee cap |
| **4844** | Shard Blob Transactions | ✅ EIP + Execution + Consensus | ✅ 5 files | blob gas, KZG, max blobs, sidecar |
| **4788** | Beacon block root in EVM | ✅ EIP + Execution | ✅ 1 file | beacon root |
| **2930** | Optional access lists | ✅ EIP + Execution | ✅ 2 files | access list validation |
| **7002** | Execution layer withdrawals | ✅ EIP + Execution | — | withdrawal requests |
| **7251** | Increase MAX_EFFECTIVE_BALANCE | ✅ EIP + Consensus | — | consolidation |

> Use `python -m src.cli list-eips` to see the live registry.

## 📋 Project Structure

```
PRSpec/
├── src/
│   ├── __init__.py          # Package exports
│   ├── config.py            # Configuration management + per-EIP focus areas
│   ├── spec_fetcher.py      # EIP registry + spec fetching (EIP/execution/consensus)
│   ├── code_fetcher.py      # Per-client per-EIP file registry + code fetching
│   ├── parser.py            # Code parsing with per-EIP keyword detection
│   ├── analyzer.py          # LLM analysis (Gemini/OpenAI) — EIP-agnostic prompt
│   ├── report_generator.py  # Report generation (JSON/MD/HTML)
│   └── cli.py               # Command-line interface
├── tests/
│   ├── test_eip1559.py      # EIP-1559 unit tests
│   └── test_eip4844.py      # EIP-4844 unit tests
├── output/                   # Generated reports
├── requirements.txt
├── config.yaml              # Configuration file (LLM + per-EIP focus areas)
├── .env.example             # Environment template
├── .env                     # Your API keys (git-ignored)
├── run_demo.py              # Demo script (EIP-1559 + EIP-4844)
├── GRANT_PROPOSAL.md        # ESP grant proposal
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

# Analyze EIP-4844 (Blob Transactions) compliance
python -m src.cli analyze --eip 4844 --client go-ethereum --output html

# Fetch an EIP specification
python -m src.cli fetch-spec --eip 4844

# List implementation files mapped for an EIP
python -m src.cli list-files --client go-ethereum --eip 4844

# List all registered EIPs and their metadata
python -m src.cli list-eips

# Check configuration
python -m src.cli check-config
```

## 🔧 Configuration

### config.yaml

```yaml
llm:
  provider: gemini  # or "openai"

  gemini:
    model: gemini-2.5-pro-preview-06-05
    max_output_tokens: 65536
    temperature: 0.1

  openai:
    model: gpt-4-turbo-preview
    max_tokens: 4096
    temperature: 0.1

repositories:
  go_ethereum:
    url: https://github.com/ethereum/go-ethereum
    branch: master
  consensus_specs:
    url: https://github.com/ethereum/consensus-specs
    branch: dev

eips:
  1559:
    focus_areas:
      - base_fee_calculation
      - gas_limit_validation
      - fee_cap_check
  4844:
    focus_areas:
      - blob_gas_price
      - kzg_commitment
      - max_blobs_per_block
      - sidecar_validation
      - excess_blob_gas

analysis:
  focus_areas:          # default fallback
    - parameter_validation
    - edge_case_handling
    - spec_compliance
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

### Programmatic Analysis (Generic Pipeline)

```python
from src.config import Config
from src.analyzer import GeminiAnalyzer
from src.spec_fetcher import SpecFetcher
from src.code_fetcher import CodeFetcher
from src.parser import CodeParser

# Initialize
config = Config()
analyzer = GeminiAnalyzer(api_key=config.gemini_api_key)

# Fetch spec and code for any supported EIP
spec_fetcher = SpecFetcher()
code_fetcher = CodeFetcher()
parser = CodeParser()

eip_number = 4844  # or 1559, 4788, 2930, ...

spec = spec_fetcher.fetch_eip_spec(eip_number)
files = code_fetcher.fetch_eip_implementation("go-ethereum", eip_number)
eip_functions = parser.find_eip_functions(
    files["core/types/tx_blob.go"], "go", eip_number
)

# Analyze with EIP-aware context
result = analyzer.analyze_compliance(
    spec_text=spec,
    code_text=files["core/types/tx_blob.go"],
    context={
        "file_name": "tx_blob.go",
        "language": "go",
        "eip_number": eip_number,
        "eip_title": spec_fetcher.get_eip_title(eip_number),
    }
)

print(f"Status: {result.status}")
print(f"Confidence: {result.confidence}%")
for issue in result.issues:
    print(f"  [{issue['severity']}] {issue['description']}")
```

### Discovering Supported EIPs and Clients

```python
from src.spec_fetcher import SpecFetcher
from src.code_fetcher import CodeFetcher

sf = SpecFetcher()
cf = CodeFetcher()

# All registered EIPs
print(sf.supported_eips())          # [1559, 2930, 4788, 4844, 7002, 7251]

# All clients with file mappings
print(cf.supported_clients())       # ['go-ethereum', 'prysm', ...]

# EIPs wired for a specific client
print(cf.supported_eips_for_client("go-ethereum"))  # [1559, 2930, 4788, 4844]
```

## 🤖 Why Gemini 2.5 Pro?

| Feature | Gemini 2.5 Pro | GPT-4 Turbo |
|---------|----------------|-------------|
| Context Window | **1M+ tokens** | 128K tokens |
| Code Analysis | Excellent | Excellent |
| Cost | Lower | Higher |
| Speed | Fast | Moderate |

Gemini's massive context window allows PRSpec to:
- Analyze entire files at once
- Compare multiple implementation files simultaneously
- Include full EIP specifications without truncation
- Handle consensus + execution specs together in a single prompt

## 🗺️ Roadmap (ESP Milestones)

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Multi-EIP architecture, EIP-4844 support | ✅ Complete |
| **Phase 2** | Multi-client analysis (Prysm, Lighthouse, etc.) | 🔜 Next |
| **Phase 3** | Cross-client differential analysis | Planned |
| **Phase 4** | Real-time monitoring & CI integration | Planned |

See [Milestones](https://github.com/Fosurero/PRSpec/milestones) for detailed issue tracking.

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
