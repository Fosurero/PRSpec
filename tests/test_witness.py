"""Deterministic witness + Fork Watch tests (no network, no LLM)."""

from pathlib import Path

import pytest

from src import witness as W

SPEC_OLD = """
| Constant | Value |
| - | - |
| `DATA_GAS_PER_BLOB` | `2**17` |
| `TARGET_DATA_GAS_PER_BLOCK` | `2**18` |
| `DATA_GASPRICE_UPDATE_FRACTION` | `2225652` |
| `BLOB_TX_TYPE` | `Bytes1(0x03)` |
"""
SPEC_NEW = """
| `GAS_PER_BLOB` | `2**17` |
| `TARGET_BLOB_GAS_PER_BLOCK` | `393216` |
| `BLOB_BASE_FEE_UPDATE_FRACTION` | `3338477` |
| `BLOB_TX_TYPE` | `Bytes1(0x03)` |
"""

BOOK = {"eip": 4844, "rules": [
    {"id": "GPB", "constant": "GAS_PER_BLOB", "aliases": ["DATA_GAS_PER_BLOB"],
     "anchors": {"x": {"file": "C.java", "pattern": r"BLOB_GAS_PER_BLOB\s*=\s*([^;]+);"}}},
    {"id": "TGT", "constant": "TARGET_BLOB_GAS_PER_BLOCK", "aliases": ["TARGET_DATA_GAS_PER_BLOCK"],
     "anchors": {"x": {"file": "S.java", "pattern": r"create\(\s*(\d+)", "multiply_by": "GAS_PER_BLOB"}}},
    {"id": "FRAC", "constant": "BLOB_BASE_FEE_UPDATE_FRACTION",
     "aliases": ["DATA_GASPRICE_UPDATE_FRACTION"],
     "anchors": {"x": {"file": "S.java", "pattern": r"create\(\s*\d+\s*,\s*\d+\s*,\s*(\d+)\)"}}},
    {"id": "TYPE", "constant": "BLOB_TX_TYPE", "anchors": {}},
]}
FILES = {"C.java": "private static final long BLOB_GAS_PER_BLOB = 1 << 17;",
         "S.java": "CANCUN = BlobSchedule.create(3, 6, 3338477);"}


def reader(files):
    return lambda rel: files.get(rel)


@pytest.mark.parametrize("raw,val", [
    ("2**17", 131072), ("1 << 17", 131072), ("8L", 8), ("1_000_000_000L", 10**9),
    ("Bytes20(0x0A)", 10), ("Wei.of(1_000_000_000L)", 10**9), ("1.GWei", 10**9),
    ("BigInteger.ONE", 1), ("50_000UL", 50000), ("0x49", 73),
    ("foo()", None), ("x + 1", None), ("2**100000", None)])
def test_eval_literal(raw, val):
    assert W.eval_literal(raw) == val


def test_extract_spec_constants_table_and_assign():
    c = W.extract_spec_constants(SPEC_NEW + "\nELASTICITY_MULTIPLIER = 2\nINITIAL_FORK_BLOCK_NUMBER = 10 # TBD\n")
    assert c["GAS_PER_BLOB"].value == 131072
    assert c["ELASTICITY_MULTIPLIER"].value == 2
    assert c["INITIAL_FORK_BLOCK_NUMBER"].value == 10


def test_check_pass_and_derived_value():
    res = {r.rule_id: r for r in W.check_rules(BOOK, SPEC_NEW, "x", reader(FILES))}
    assert res["GPB"].status == W.PASS
    assert res["TGT"].status == W.PASS and res["TGT"].actual == 393216
    assert res["FRAC"].status == W.PASS
    assert res["TYPE"].status == W.UNMAPPED


def test_check_detects_mutation():
    files = dict(FILES, **{"C.java": "BLOB_GAS_PER_BLOB = 1 << 16;"})
    res = {r.rule_id: r for r in W.check_rules(BOOK, SPEC_NEW, "x", reader(files))}
    assert res["GPB"].status == W.FAIL and res["GPB"].actual == 65536
    assert res["TGT"].status == W.FAIL  # derived from the wrong GAS_PER_BLOB


def test_old_spec_uses_aliases_and_flags_drift():
    res = {r.rule_id: r for r in W.check_rules(BOOK, SPEC_OLD, "x", reader(FILES))}
    assert res["GPB"].status == W.PASS and "historical name" in res["GPB"].note
    assert res["TGT"].status == W.FAIL and res["TGT"].expected == 262144
    assert res["FRAC"].status == W.FAIL


def test_fail_closed_when_anchor_or_file_missing():
    res = {r.rule_id: r for r in W.check_rules(BOOK, SPEC_NEW, "x", reader({}))}
    assert res["GPB"].status == W.INCOMPLETE
    assert res["TGT"].status == W.INCOMPLETE
    moved = {"C.java": "// constant moved elsewhere", "S.java": FILES["S.java"]}
    res = {r.rule_id: r for r in W.check_rules(BOOK, SPEC_NEW, "x", reader(moved))}
    assert res["GPB"].status == W.INCOMPLETE and "not found" in res["GPB"].note


def test_missing_spec_constant_is_incomplete_not_pass():
    res = {r.rule_id: r for r in W.check_rules(BOOK, "no table here", "x", reader(FILES))}
    assert all(r.status == W.INCOMPLETE for r in res.values() if r.rule_id != "TYPE")


def test_fork_watch_changes_and_renames():
    ch = {c.name: c for c in W.fork_watch(SPEC_OLD, SPEC_NEW, BOOK)}
    assert ch["DATA_GAS_PER_BLOB"].kind == "renamed"
    assert ch["DATA_GAS_PER_BLOB"].new_name == "GAS_PER_BLOB"
    assert ch["DATA_GAS_PER_BLOB"].rules == ["GPB"]
    # value changed and renamed in one step: reported as removed + added,
    # and both sides still map to the rule through its aliases
    assert ch["TARGET_DATA_GAS_PER_BLOCK"].kind == "removed"
    assert ch["TARGET_DATA_GAS_PER_BLOCK"].rules == ["TGT"]
    assert ch["TARGET_BLOB_GAS_PER_BLOCK"].kind == "added"
    assert "BLOB_TX_TYPE" not in ch


def test_shipped_rulebooks_load_and_patterns_compile():
    import re
    for eip in W.available_rulebooks():
        book = W.load_rulebook(eip)
        assert book["eip"] == eip and book["rules"]
        for r in book["rules"]:
            for a in r.get("anchors", {}).values():
                assert re.compile(a["pattern"]).groups == 1, r["id"]


def test_witness_cli_exit_codes(tmp_path):
    from click.testing import CliRunner

    from src.cli import cli
    spec = tmp_path / "eip.md"
    spec.write_text("ELASTICITY_MULTIPLIER = 2\nBASE_FEE_MAX_CHANGE_DENOMINATOR = 8\nINITIAL_BASE_FEE = 1000000000\n")
    d = tmp_path / "besu"
    f = d / "ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/feemarket/LondonFeeMarket.java"
    f.parent.mkdir(parents=True)
    f.write_text("static final long DEFAULT_BASEFEE_MAX_CHANGE_DENOMINATOR = 8L;\n"
                 "static final long DEFAULT_SLACK_COEFFICIENT = 2L;\n")
    g = d / "config/src/main/java/org/hyperledger/besu/config/GenesisConfig.java"
    g.parent.mkdir(parents=True)
    g.write_text("public static final Wei BASEFEE_AT_GENESIS_DEFAULT_VALUE = Wei.of(1_000_000_000L);\n")
    args = ["witness", "--eip", "1559", "-t", f"besu={d}", "--spec-file", str(spec)]
    r = CliRunner().invoke(cli, args)
    assert r.exit_code == 0, r.output
    f.write_text(f.read_text().replace("= 2L", "= 3L"))
    assert CliRunner().invoke(cli, args).exit_code == 10
    g.unlink()
    assert CliRunner().invoke(cli, args).exit_code == 20
    assert Path(spec).exists()
