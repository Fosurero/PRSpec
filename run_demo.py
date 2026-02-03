#!/usr/bin/env python3
"""
PRSpec Demo Script
Author: Safi El-Hassanine

Demonstrates the PRSpec Ethereum specification compliance checker
using Google Gemini 1.5 Pro for analysis.
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


def print_banner():
    """Print the PRSpec banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   ██████╗ ██████╗ ███████╗██████╗ ███████╗ ██████╗               ║
║   ██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝               ║
║   ██████╔╝██████╔╝███████╗██████╔╝█████╗  ██║                    ║
║   ██╔═══╝ ██╔══██╗╚════██║██╔═══╝ ██╔══╝  ██║                    ║
║   ██║     ██║  ██║███████║██║     ███████╗╚██████╗               ║
║   ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝     ╚══════╝ ╚═════╝               ║
║                                                                   ║
║   Ethereum Specification Compliance Checker                       ║
║   Author: Safi El-Hassanine                                       ║
║   LLM: Google Gemini 2.5 Pro                                      ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def run_demo():
    """Run a demonstration of PRSpec capabilities"""
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
        print(f"❌ Import error: {e}")
        print("Make sure you've installed requirements: pip install -r requirements.txt")
        return
    
    # Check for Rich library
    try:
        from rich.console import Console
        from rich.progress import Progress, SpinnerColumn, TextColumn
        from rich.panel import Panel
        from rich.table import Table
        console = Console()
        use_rich = True
    except ImportError:
        console = None
        use_rich = False
        print("Note: Install 'rich' for better output formatting")
    
    # Load configuration
    print("\n📋 Loading configuration...")
    try:
        config = Config()
        print(f"   ✓ Provider: {config.llm_provider}")
        print(f"   ✓ Config loaded from: {config.config_path}")
    except Exception as e:
        print(f"   ❌ Error loading config: {e}")
        return
    
    # Check API key
    print("\n🔑 Checking API credentials...")
    try:
        api_key = config.gemini_api_key
        print(f"   ✓ Gemini API key found")
    except ValueError as e:
        print(f"   ❌ {e}")
        print("   Please set GEMINI_API_KEY in your .env file")
        return
    
    # Initialize components
    print("\n🚀 Initializing components...")
    
    spec_fetcher = SpecFetcher(github_token=config.github_token)
    code_fetcher = CodeFetcher(github_token=config.github_token)
    parser = CodeParser()
    
    gemini_config = config.gemini_config
    analyzer = GeminiAnalyzer(
        api_key=api_key,
        model=gemini_config.get("model", "gemini-1.5-pro-latest"),
        max_output_tokens=gemini_config.get("max_output_tokens", 8192),
        temperature=gemini_config.get("temperature", 0.1)
    )
    
    print(f"   ✓ Analyzer: {analyzer.get_model_info()['model']}")
    print(f"   ✓ Context window: {analyzer.get_model_info()['context_window']}")
    
    # Fetch EIP-1559 specification
    print("\n📚 Fetching EIP-1559 specification...")
    try:
        spec_data = spec_fetcher.fetch_eip1559_spec()
        eip_content = spec_data.get("eip_markdown", "")
        print(f"   ✓ EIP-1559 markdown: {len(eip_content)} characters")
        
        if spec_data.get("execution_spec"):
            print(f"   ✓ Execution spec: {len(spec_data['execution_spec'])} characters")
    except Exception as e:
        print(f"   ❌ Error fetching spec: {e}")
        return
    
    # Fetch go-ethereum implementation
    print("\n💻 Fetching go-ethereum implementation...")
    try:
        code_files = code_fetcher.fetch_geth_eip1559()
        print(f"   ✓ Found {len(code_files)} implementation files:")
        for path, content in code_files.items():
            lines = len(content.split('\n'))
            print(f"      - {path} ({lines} lines)")
    except Exception as e:
        print(f"   ❌ Error fetching code: {e}")
        # Continue with mock data for demo
        code_files = {}
    
    # If no files fetched, use sample code for demo
    if not code_files:
        print("\n📝 Using sample code for demonstration...")
        code_files = {
            "sample/eip1559.go": '''
package eip1559

import "math/big"

// CalcBaseFee calculates the basefee of the header.
func CalcBaseFee(config *ChainConfig, parent *Header) *big.Int {
    // If the current block is the first EIP-1559 block, return the InitialBaseFee.
    if !config.IsLondon(parent.Number) {
        return new(big.Int).SetUint64(InitialBaseFee)
    }

    parentGasTarget := parent.GasLimit / ElasticityMultiplier
    
    // If the parent gasUsed is the same as the target, the baseFee remains unchanged.
    if parent.GasUsed == parentGasTarget {
        return new(big.Int).Set(parent.BaseFee)
    }

    if parent.GasUsed > parentGasTarget {
        // If the parent block used more gas than its target, the baseFee should increase.
        gasUsedDelta := new(big.Int).SetUint64(parent.GasUsed - parentGasTarget)
        x := new(big.Int).Mul(parent.BaseFee, gasUsedDelta)
        y := x.Div(x, new(big.Int).SetUint64(parentGasTarget))
        baseFeeDelta := math.BigMax(y.Div(y, new(big.Int).SetUint64(BaseFeeChangeDenominator)), common.Big1)
        return new(big.Int).Add(parent.BaseFee, baseFeeDelta)
    } else {
        // Otherwise if the parent block used less gas than its target, the baseFee should decrease.
        gasUsedDelta := new(big.Int).SetUint64(parentGasTarget - parent.GasUsed)
        x := new(big.Int).Mul(parent.BaseFee, gasUsedDelta)
        y := x.Div(x, new(big.Int).SetUint64(parentGasTarget))
        baseFeeDelta := y.Div(y, new(big.Int).SetUint64(BaseFeeChangeDenominator))
        return math.BigMax(new(big.Int).Sub(parent.BaseFee, baseFeeDelta), common.Big0)
    }
}
'''
        }
    
    # Parse the code
    print("\n🔍 Parsing implementation code...")
    for path, content in code_files.items():
        blocks = parser.find_eip1559_functions(content, "go")
        print(f"   ✓ {path}: Found {len(blocks)} EIP-1559 related functions")
        for block in blocks[:3]:  # Show first 3
            print(f"      - {block.name} (lines {block.start_line}-{block.end_line})")
    
    # Run analysis
    print("\n🤖 Running Gemini analysis...")
    print("   This may take a moment...")
    
    results = []
    
    # Extract specification section
    spec_sections = spec_fetcher.extract_eip_sections(eip_content)
    spec_text = spec_sections.get("specification", eip_content[:10000])
    
    for file_path, code_content in code_files.items():
        print(f"\n   Analyzing: {file_path}")
        
        context = {
            "file_name": file_path,
            "function_name": "EIP-1559 Base Fee Calculation",
            "language": "go",
            "focus_areas": config.focus_areas
        }
        
        try:
            result = analyzer.analyze_compliance(spec_text, code_content, context)
            
            result_dict = result.to_dict()
            result_dict["file_name"] = file_path
            results.append(result_dict)
            
            # Print result
            status_emoji = {
                "FULL_MATCH": "✅",
                "PARTIAL_MATCH": "⚠️",
                "MISSING": "❌",
                "UNCERTAIN": "❓",
                "ERROR": "💥"
            }.get(result.status, "❓")
            
            print(f"   {status_emoji} Status: {result.status}")
            print(f"   📊 Confidence: {result.confidence}%")
            print(f"   📝 Summary: {result.summary[:100]}...")
            
            if result.issues:
                print(f"   ⚠️  Issues found: {len(result.issues)}")
                for issue in result.issues[:2]:
                    severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(issue.get("severity", ""), "⚪")
                    print(f"      {severity_emoji} [{issue.get('severity', 'N/A')}] {issue.get('type', 'Issue')}")
                    
        except Exception as e:
            print(f"   ❌ Analysis error: {e}")
            results.append({
                "file_name": file_path,
                "status": "ERROR",
                "confidence": 0,
                "issues": [],
                "summary": str(e)
            })
    
    # Generate report
    print("\n📊 Generating report...")
    
    report_gen = ReportGenerator(config.output_config.get("directory", "output"))
    metadata = ReportMetadata(
        title="EIP-1559 Compliance Report - go-ethereum",
        eip_number=1559,
        client="go-ethereum",
        timestamp=datetime.now(),
        analyzer=f"Gemini ({analyzer.get_model_info()['model']})",
        author="Safi El-Hassanine"
    )
    
    # Generate all formats
    for fmt in ["json", "markdown", "html"]:
        try:
            report_path = report_gen.generate_report(results, metadata, fmt)
            print(f"   ✓ {fmt.upper()} report: {report_path}")
        except Exception as e:
            print(f"   ❌ Error generating {fmt} report: {e}")
    
    # Print summary
    if use_rich and results:
        console.print("\n")
        report_gen.print_summary(results, metadata)
    
    print("\n" + "=" * 70)
    print("🎉 Demo completed!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Check the 'output' directory for generated reports")
    print("  2. Run 'python -m src.cli analyze --help' for CLI options")
    print("  3. Customize config.yaml for different EIPs or clients")
    print("\n")


def quick_test():
    """Quick test of Gemini API connection"""
    print("🔬 Quick API Test")
    print("-" * 40)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return False
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel("gemini-2.5-pro")
        response = model.generate_content("Say 'PRSpec is ready!' in exactly those words.")
        
        print(f"✅ Gemini API connected successfully")
        print(f"   Response: {response.text.strip()}")
        return True
        
    except Exception as e:
        print(f"❌ API Error: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    arg_parser = argparse.ArgumentParser(description="PRSpec Demo")
    arg_parser.add_argument("--test", action="store_true", help="Quick API test only")
    args = arg_parser.parse_args()
    
    if args.test:
        quick_test()
    else:
        run_demo()
