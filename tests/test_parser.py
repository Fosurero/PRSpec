"""Tests for code parsing paths not exercised by the per-EIP suites:
Python classes/docstrings, the generic fallback, tree-sitter, and lookups.
"""

import sys
import textwrap
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import CodeBlock, CodeParser

PYTHON_SOURCE = textwrap.dedent('''\
    # module level comment
    import math


    def calc_base_fee(parent_base_fee, gas_used):
        """Return the next base fee.

        Multi-line docstring.
        """
        return parent_base_fee * gas_used


    def verify_eip1559_header(header):
        # inline comment
        return header is not None
''')

PYTHON_CLASS_SOURCE = textwrap.dedent('''\
    class BaseFeeCalculator:
        """Computes the EIP-1559 base fee."""

        def __init__(self, parent):
            self.parent = parent

        def calc_base_fee(self, gas_used):
            return gas_used * 2


    class Other:
        pass
''')


class TestCodeBlock(unittest.TestCase):
    def test_to_dict_round_trip(self):
        block = CodeBlock(name="f", type="function", content="def f(): pass",
                          start_line=1, end_line=1, language="python",
                          signature="def f():", docstring=None)
        self.assertEqual(block.to_dict()["name"], "f")
        self.assertEqual(set(block.to_dict()), {
            "name", "type", "content", "start_line", "end_line", "language",
            "signature", "docstring"})


class TestPythonParsing(unittest.TestCase):
    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)
        self.blocks = self.parser.parse_file(PYTHON_SOURCE, "python")

    def _named(self, name):
        return next(b for b in self.blocks if b.name == name)

    def test_class_is_extracted_with_its_body(self):
        klass = self.parser.parse_file(PYTHON_CLASS_SOURCE, "python")[0]
        self.assertEqual(klass.name, "BaseFeeCalculator")
        self.assertEqual(klass.type, "class")
        self.assertIn("def calc_base_fee", klass.content)

    def test_indented_functions_are_methods(self):
        code = "if True:\n    def helper():\n        return 1\n"
        self.assertEqual(self.parser.parse_file(code, "python")[0].type, "method")

    def test_top_level_function_is_a_function(self):
        self.assertEqual(self._named("verify_eip1559_header").type, "function")

    def test_multiline_docstring_captured(self):
        docstring = self._named("calc_base_fee").docstring
        self.assertIn("Return the next base fee.", docstring)
        self.assertIn("Multi-line docstring.", docstring)

    def test_single_line_docstring_captured(self):
        code = 'def f():\n    """One liner."""\n    return 1\n'
        block = CodeParser().parse_file(code, "python")[0]
        self.assertEqual(block.docstring.strip(), '"""One liner."""')

    def test_function_without_docstring(self):
        self.assertIsNone(self._named("verify_eip1559_header").docstring)

    def test_consecutive_classes_are_both_found(self):
        names = [b.name for b in self.parser.parse_file(PYTHON_CLASS_SOURCE, "python")]
        self.assertEqual(names, ["BaseFeeCalculator", "Other"])


class TestGenericFallback(unittest.TestCase):
    def test_unknown_language_returns_whole_file(self):
        blocks = CodeParser().parse_file("a\nb\nc\n", "cobol")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].type, "file")
        self.assertEqual(blocks[0].language, "cobol")
        self.assertEqual(blocks[0].end_line, 4)


class TestRustEdgeCases(unittest.TestCase):
    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)

    def test_tuple_struct_is_a_single_line_block(self):
        blocks = self.parser.parse_file("pub struct BlobGas(u64);\n", "rust")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].name, "BlobGas")
        self.assertEqual(blocks[0].start_line, blocks[0].end_line)

    def test_multiline_signature_function(self):
        code = textwrap.dedent("""\
            pub fn calc_excess_blob_gas(
                parent_excess: u64,
                parent_used: u64,
            ) -> u64 {
                parent_excess + parent_used
            }
        """)
        blocks = self.parser.parse_file(code, "rust")
        self.assertEqual([b.name for b in blocks], ["calc_excess_blob_gas"])
        self.assertIn("parent_excess + parent_used", blocks[0].content)

    def test_comments_are_skipped(self):
        code = "// leading comment\n/* block */\nfn f() {\n    1\n}\n"
        self.assertEqual([b.name for b in self.parser.parse_file(code, "rust")], ["f"])


class TestBraceLanguageTopLevelFunctions(unittest.TestCase):
    def test_java_method_outside_a_class(self):
        code = textwrap.dedent("""\
            public static long computeBaseFee(long parentGasUsed)
            {
                return parentGasUsed * 2;
            }
        """)
        blocks = CodeParser().parse_file(code, "java")
        self.assertEqual([b.name for b in blocks], ["computeBaseFee"])
        self.assertEqual(blocks[0].type, "method")

    def test_csharp_method_outside_a_class(self):
        code = "public static UInt256 Calculate(BlockHeader h) {\n    return h.BaseFee;\n}\n"
        blocks = CodeParser().parse_file(code, "csharp")
        self.assertEqual([b.name for b in blocks], ["Calculate"])


class TestTreeSitter(unittest.TestCase):
    def test_initialisation_registers_parsers(self):
        parser = CodeParser(use_tree_sitter=True)
        self.assertTrue(parser.use_tree_sitter)
        self.assertEqual(set(parser._ts_parsers), {"python", "go"})

    def test_unavailable_dependency_falls_back_to_regex(self):
        with mock.patch.dict(sys.modules, {"tree_sitter": None}):
            parser = CodeParser(use_tree_sitter=True)
        self.assertFalse(parser.use_tree_sitter)
        self.assertEqual(parser._ts_parsers, {})
        # Parsing still works through the regex path.
        self.assertEqual(
            [b.name for b in parser.parse_file("def f():\n    return 1\n", "python")],
            ["f"])

    def test_python_nested_definitions_are_all_reported(self):
        blocks = CodeParser(use_tree_sitter=True).parse_file(
            PYTHON_CLASS_SOURCE, "python")
        by_name = {b.name: b for b in blocks}
        self.assertEqual(by_name["BaseFeeCalculator"].type, "class")
        # Unlike the regex path, methods inside a class body are reported too.
        self.assertEqual(by_name["calc_base_fee"].type, "function")
        self.assertEqual(by_name["calc_base_fee"].start_line, 7)

    def test_go_functions(self):
        code = textwrap.dedent("""\
            package misc

            func CalcBaseFee(parent *Header) *big.Int {
                return parent.BaseFee
            }
        """)
        blocks = CodeParser(use_tree_sitter=True).parse_file(code, "go")
        self.assertEqual([b.name for b in blocks], ["CalcBaseFee"])
        self.assertEqual(blocks[0].start_line, 3)

    def test_unsupported_language_uses_generic_block(self):
        parser = CodeParser(use_tree_sitter=True)
        parser._ts_parsers["rust"] = parser._ts_parsers["go"]
        blocks = parser.parse_file("fn main() {}", "rust")
        self.assertEqual(blocks[0].type, "file")

    def test_missing_parser_falls_back_to_generic(self):
        parser = CodeParser(use_tree_sitter=True)
        self.assertEqual(parser._parse_with_tree_sitter("x", "java")[0].type, "file")


class TestLookups(unittest.TestCase):
    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)

    def test_find_function_by_name(self):
        block = self.parser.find_function(PYTHON_SOURCE, "calc_base_fee", "python")
        self.assertIsNotNone(block)
        self.assertEqual(block.name, "calc_base_fee")

    def test_find_function_missing_returns_none(self):
        self.assertIsNone(
            self.parser.find_function(PYTHON_SOURCE, "nope", "python"))

    def test_find_eip_functions_uses_registered_keywords(self):
        blocks = self.parser.find_eip_functions(PYTHON_SOURCE, "python", 1559)
        self.assertIn("calc_base_fee", [b.name for b in blocks])

    def test_find_eip_functions_unknown_eip_matches_the_number(self):
        code = "def handler():\n    # implements 9999\n    return 1\n"
        blocks = self.parser.find_eip_functions(code, "python", 9999)
        self.assertEqual([b.name for b in blocks], ["handler"])

    def test_eip1559_and_eip4844_shortcuts(self):
        self.assertEqual(
            [b.name for b in self.parser.find_eip1559_functions(PYTHON_SOURCE, "python")],
            [b.name for b in self.parser.find_eip_functions(PYTHON_SOURCE, "python", 1559)])
        blob = "def calc_excess_blob_gas():\n    return 0\n"
        self.assertEqual(
            [b.name for b in self.parser.find_eip4844_functions(blob, "python")],
            ["calc_excess_blob_gas"])


class TestComments(unittest.TestCase):
    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)

    def test_python_comments_and_docstrings(self):
        comments = self.parser.extract_comments(PYTHON_SOURCE, "python")
        singles = [c for c in comments if c["type"] == "single"]
        docstrings = [c for c in comments if c["type"] == "docstring"]
        self.assertIn("module level comment", [c["content"] for c in singles])
        self.assertIn("Return the next base fee.", docstrings[0]["content"])
        self.assertEqual(singles[0]["line"], 1)

    def test_go_single_and_multi_line_comments(self):
        code = "// CalcBaseFee docs\n/* block\ncomment */\nfunc CalcBaseFee() {}\n"
        comments = self.parser.extract_comments(code, "go")
        self.assertEqual([c["type"] for c in comments], ["single", "multi"])
        self.assertEqual(comments[0]["content"], "CalcBaseFee docs")
        self.assertIn("block", comments[1]["content"])

    def test_unsupported_language_has_no_comments(self):
        self.assertEqual(self.parser.extract_comments("-- sql comment", "sql"), [])


if __name__ == "__main__":
    unittest.main()
