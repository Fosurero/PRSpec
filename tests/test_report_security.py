"""Tests for untrusted-input handling: HTML escaping, cache paths, clone args."""

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.code_fetcher import CodeFetcher
from src.code_fetcher import _cache_name as _code_cache_name
from src.report_generator import ReportGenerator, ReportMetadata
from src.spec_fetcher import _cache_name as _spec_cache_name

PAYLOAD = "<script>alert('xss')</script>"


def _result():
    return {
        "file_name": f"core/{PAYLOAD}.go",
        "status": PAYLOAD,
        "confidence": 90,
        "summary": f"Summary {PAYLOAD}",
        "issues": [{
            "type": PAYLOAD,
            "severity": "HIGH",
            "description": PAYLOAD,
            "spec_reference": PAYLOAD,
            "code_location": PAYLOAD,
            "potential_impact": PAYLOAD,
            "suggestion": PAYLOAD,
            "verification": {"verdict": "CONFIRMED",
                             "verification_score": PAYLOAD,
                             "grounded": True},
        }],
    }


class TestHtmlReportEscaping(unittest.TestCase):
    """Model output is untrusted — it must never reach the report as markup."""

    def test_no_raw_payload_in_html_report(self):
        outdir = tempfile.mkdtemp(prefix="prspec_report_")
        metadata = ReportMetadata(
            title=f"EIP-1559 Compliance Report - {PAYLOAD}",
            eip_number=1559,
            client=PAYLOAD,
            timestamp=datetime.now(),
            analyzer=PAYLOAD,
        )
        path = ReportGenerator(outdir).generate_report([_result()], metadata, "html")
        content = Path(path).read_text(encoding="utf-8")

        self.assertNotIn("<script>", content)
        self.assertIn("&lt;script&gt;", content)

    def test_report_filename_stays_in_output_dir(self):
        outdir = Path(tempfile.mkdtemp(prefix="prspec_report_"))
        metadata = ReportMetadata(
            title="EIP-1559 Compliance Report",
            eip_number=1559,
            client="../../escaped",
            timestamp=datetime.now(),
            analyzer="test",
        )
        generator = ReportGenerator(str(outdir))
        for fmt in ("json", "markdown", "html"):
            path = Path(generator.generate_report([_result()], metadata, fmt))
            self.assertEqual(path.resolve().parent, outdir.resolve())


class TestCacheFileNames(unittest.TestCase):
    """Remote-controlled path components must stay inside the cache directory."""

    def test_spec_cache_stays_in_cache_dir(self):
        cache_dir = Path(tempfile.mkdtemp(prefix="prspec_spec_cache_"))
        cache_file = cache_dir / _spec_cache_name("exec_spec", "master", "../../etc/passwd")
        self.assertEqual(cache_file.resolve().parent, cache_dir.resolve())

    def test_code_cache_stays_in_cache_dir(self):
        cache_dir = Path(tempfile.mkdtemp(prefix="prspec_code_cache_"))
        cache_file = cache_dir / _code_cache_name(
            "..", "..", "../../../etc/passwd", "../master"
        )
        self.assertEqual(cache_file.resolve().parent, cache_dir.resolve())


class TestCloneArgumentValidation(unittest.TestCase):
    """clone_repository must not accept git flags or command-running transports."""

    def test_rejects_ext_transport(self):
        with self.assertRaises(ValueError):
            CodeFetcher().clone_repository("ext::sh -c touch% /tmp/pwned")

    def test_rejects_option_like_url(self):
        with self.assertRaises(ValueError):
            CodeFetcher().clone_repository("--upload-pack=touch /tmp/pwned")

    def test_rejects_option_like_branch(self):
        with self.assertRaises(ValueError):
            CodeFetcher().clone_repository(
                "https://github.com/ethereum/go-ethereum", branch="--upload-pack=x"
            )


if __name__ == "__main__":
    unittest.main()
