#!/usr/bin/env python3
"""
Demo script for PRSpec — runs a full analysis pipeline against a single EIP.

Usage:
    python run_demo.py                  # Analyze EIP-1559 (default)
    python run_demo.py --eip 4844       # Analyze EIP-4844
    python run_demo.py --test           # Quick API connectivity test
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------------
# Sample code used when live GitHub fetch fails (keeps the demo self-contained)
# ---------------------------------------------------------------------------
SAMPLE_CODE = {
    1559: {
        "sample/eip1559.go": '''
package eip1559

import "math/big"

// CalcBaseFee calculates the basefee of the header.
func CalcBaseFee(config *ChainConfig, parent *Header) *big.Int {
    if !config.IsLondon(parent.Number) {
        return new(big.Int).SetUint64(InitialBaseFee)
    }

    parentGasTarget := parent.GasLimit / ElasticityMultiplier

    if parent.GasUsed == parentGasTarget {
        return new(big.Int).Set(parent.BaseFee)
    }

    if parent.GasUsed > parentGasTarget {
        gasUsedDelta := new(big.Int).SetUint64(parent.GasUsed - parentGasTarget)
        x := new(big.Int).Mul(parent.BaseFee, gasUsedDelta)
        y := x.Div(x, new(big.Int).SetUint64(parentGasTarget))
        baseFeeDelta := math.BigMax(y.Div(y, new(big.Int).SetUint64(BaseFeeChangeDenominator)), common.Big1)
        return new(big.Int).Add(parent.BaseFee, baseFeeDelta)
    } else {
        gasUsedDelta := new(big.Int).SetUint64(parentGasTarget - parent.GasUsed)
        x := new(big.Int).Mul(parent.BaseFee, gasUsedDelta)
        y := x.Div(x, new(big.Int).SetUint64(parentGasTarget))
        baseFeeDelta := y.Div(y, new(big.Int).SetUint64(BaseFeeChangeDenominator))
        return math.BigMax(new(big.Int).Sub(parent.BaseFee, baseFeeDelta), common.Big0)
    }
}
'''
    },
    4844: {
        "sample/tx_blob.go": '''
package types

import (
    "math/big"
    "github.com/ethereum/go-ethereum/common"
    "github.com/ethereum/go-ethereum/crypto/kzg4844"
)

// BlobTx represents an EIP-4844 transaction.
type BlobTx struct {
    ChainID    *uint256.Int
    Nonce      uint64
    GasTipCap  *uint256.Int
    GasFeeCap  *uint256.Int
    Gas        uint64
    To         common.Address
    Value      *uint256.Int
    Data       []byte
    BlobFeeCap *uint256.Int
    BlobHashes []common.Hash
    Sidecar    *BlobTxSidecar
}

// BlobTxSidecar contains the blobs of a blob transaction.
type BlobTxSidecar struct {
    Blobs       []kzg4844.Blob
    Commitments []kzg4844.Commitment
    Proofs      []kzg4844.Proof
}

// CalcBlobFee calculates the blob gas price from the excess blob gas.
func CalcBlobFee(excessBlobGas uint64) *big.Int {
    return fakeExponential(minBlobGasPrice, excessBlobGas, blobGasPriceUpdateFraction)
}

// ValidateBlobSidecar validates the blob sidecar against the transaction.
func ValidateBlobSidecar(hashes []common.Hash, sidecar *BlobTxSidecar) error {
    if len(sidecar.Blobs) != len(hashes) {
        return errors.New("blob count mismatch")
    }
    for i := range sidecar.Blobs {
        if err := kzg4844.VerifyBlobProof(sidecar.Blobs[i], sidecar.Commitments[i], sidecar.Proofs[i]); err != nil {
            return err
        }
    }
    return nil
}
'''
    },
}


def print_banner():
    print("\n  PRSpec — Ethereum Specification Compliance Checker\n")


def run_demo(eip_number: int = 1559, client: str = "go-ethereum"):
    """Run a demonstration of PRSpec capabilities for any supported EIP."""
    print_banner()

    # Import PRSpec components
    try:
        from src.config import Config
        from src.analyzer import GeminiAnalyzer, get_analyzer
        from src.spec_fetcher import SpecFetcher
        from src.code_fetcher import CodeFetcher
        from src.parser import CodeParser
        from src.report_generator import ReportGenerator, ReportMetadata
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you've installed requirements: pip install -r requirements.txt")
        return

    # Check for Rich library
    try:
        from rich.console import Console
        console = Console()
        use_rich = True
    except ImportError:
        console = None
        use_rich = False
        print("Note: Install 'rich' for better output formatting")

    # Load configuration
    print("\nLoading configuration...")
    try:
        config = Config()
        print(f"   ✓ Provider: {config.llm_provider}")
        print(f"   ✓ Config loaded from: {config.config_path}")
    except Exception as e:
        print(f"   Error loading config: {e}")
        return

    # Check API key
    print("\nChecking API credentials...")
    try:
        api_key = config.gemini_api_key
        print(f"   ✓ Gemini API key found")
    except ValueError as e:
        print(f"   {e}")
        print("   Please set GEMINI_API_KEY in your .env file")
        return

    # Validate EIP support
    spec_fetcher = SpecFetcher(github_token=config.github_token)
    code_fetcher = CodeFetcher(github_token=config.github_token)
    parser = CodeParser()

    if eip_number not in spec_fetcher.supported_eips():
        print(f"   EIP-{eip_number} is not in the registry. "
              f"Supported: {spec_fetcher.supported_eips()}")
        return

    eip_title = spec_fetcher.get_eip_title(eip_number)
    print(f"\nTarget: EIP-{eip_number} ({eip_title}) -- {client}")

    # Initialize analyzer
    gemini_config = config.gemini_config
    analyzer = GeminiAnalyzer(
        api_key=api_key,
        model=gemini_config.get("model", "gemini-2.5-pro"),
        max_output_tokens=gemini_config.get("max_output_tokens", 65536),
        temperature=gemini_config.get("temperature", 0.1),
    )
    print(f"   ✓ Analyzer: {analyzer.get_model_info()['model']}")
    print(f"   ✓ Context window: {analyzer.get_model_info()['context_window']}")

    # Fetch spec
    print(f"\nFetching EIP-{eip_number} specification...")
    try:
        spec_data = spec_fetcher.fetch_eip_spec(eip_number)
        eip_content = spec_data.get("eip_markdown", "")
        print(f"   ✓ EIP markdown: {len(eip_content)} characters")
        if spec_data.get("execution_spec"):
            print(f"   ✓ Execution spec: {len(spec_data['execution_spec'])} characters")
        if spec_data.get("consensus_spec"):
            print(f"   ✓ Consensus spec: {len(spec_data['consensus_spec'])} characters")
    except Exception as e:
        print(f"   Error fetching spec: {e}")
        return

    # Fetch client implementation
    print(f"\nFetching {client} implementation...")
    try:
        code_files = code_fetcher.fetch_eip_implementation(client, eip_number)
        print(f"   ✓ Found {len(code_files)} implementation files:")
        for path, content in code_files.items():
            lines = len(content.split("\n"))
            print(f"      - {path} ({lines} lines)")
    except Exception as e:
        print(f"   Error fetching code: {e}")
        code_files = {}

    # Fall back to sample code when live fetch fails
    if not code_files:
        if eip_number in SAMPLE_CODE:
            print("\nUsing sample code for demonstration...")
            code_files = SAMPLE_CODE[eip_number]
        else:
            print("   No sample code available for this EIP. Exiting.")
            return

    # Parse the code
    language = code_fetcher.client_language(client)
    print("\nParsing implementation code...")
    for path, content in code_files.items():
        blocks = parser.find_eip_functions(content, language, eip_number)
        print(f"   ✓ {path}: Found {len(blocks)} EIP-{eip_number} related functions")
        for block in blocks[:5]:
            print(f"      - {block.name} (lines {block.start_line}-{block.end_line})")

    # Run analysis
    print("\nRunning Gemini analysis...")
    print("   This may take a moment...")

    results = []

    spec_sections = spec_fetcher.extract_eip_sections(eip_content)
    spec_text = spec_sections.get("specification", eip_content[:10000])

    focus_areas = config.get_eip_focus_areas(eip_number)

    for file_path, code_content in code_files.items():
        print(f"\n   Analyzing: {file_path}")

        context = {
            "file_name": file_path,
            "function_name": f"EIP-{eip_number} {eip_title}",
            "language": language,
            "eip_number": eip_number,
            "eip_title": eip_title,
            "focus_areas": focus_areas,
        }

        try:
            result = analyzer.analyze_compliance(spec_text, code_content, context)

            result_dict = result.to_dict()
            result_dict["file_name"] = file_path
            results.append(result_dict)

            status_marker = {
                "FULL_MATCH": "[OK]",
                "PARTIAL_MATCH": "[!!]",
                "MISSING": "[MISS]",
                "UNCERTAIN": "[??]",
                "ERROR": "[ERR]",
            }.get(result.status, "[??]")

            print(f"   {status_marker} Status: {result.status}")
            print(f"   Confidence: {result.confidence}%")
            print(f"   Summary: {result.summary[:100]}...")
            if result.issues:
                print(f"   Issues found: {len(result.issues)}")
                for issue in result.issues[:3]:
                    sev = issue.get("severity", "")
                    print(f"      [{sev}] {issue.get('type', 'Issue')}")

        except Exception as e:
            print(f"   Analysis error: {e}")
            results.append({
                "file_name": file_path,
                "status": "ERROR",
                "confidence": 0,
                "issues": [],
                "summary": str(e),
            })

    # Generate report
    print("\nGenerating report...")

    report_gen = ReportGenerator(config.output_config.get("directory", "output"))
    metadata = ReportMetadata(
        title=f"EIP-{eip_number} Compliance Report -- {client}",
        eip_number=eip_number,
        client=client,
        timestamp=datetime.now(),
        analyzer=f"Gemini ({analyzer.get_model_info()['model']})",
    )

    for fmt in ["json", "markdown", "html"]:
        try:
            report_path = report_gen.generate_report(results, metadata, fmt)
            print(f"   {fmt.upper()}: {report_path}")
        except Exception as e:
            print(f"   Error generating {fmt} report: {e}")

    if use_rich and results:
        console.print("\n")
        report_gen.print_summary(results, metadata)

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)
    print(f"\nReports are in the 'output' directory.")
    print()


def quick_test():
    """Quick connectivity check for Gemini API."""
    print("API connectivity test")
    print("-" * 40)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set")
        return False
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel("gemini-2.5-pro")
        response = model.generate_content("Say 'PRSpec is ready!' in exactly those words.")
        
        print(f"OK — Gemini API connected")
        print(f"   Response: {response.text.strip()}")
        return True
        
    except Exception as e:
        print(f"API Error: {e}")
        return False


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser(description="PRSpec Demo")
    arg_parser.add_argument("--test", action="store_true", help="Quick API test only")
    arg_parser.add_argument("--eip", type=int, default=1559,
                            help="EIP number to analyze (default: 1559)")
    arg_parser.add_argument("--client", type=str, default="go-ethereum",
                            help="Client to analyze (default: go-ethereum)")
    args = arg_parser.parse_args()

    if args.test:
        quick_test()
    else:
        run_demo(eip_number=args.eip, client=args.client)
