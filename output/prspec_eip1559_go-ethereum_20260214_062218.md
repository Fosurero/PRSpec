# EIP-1559 Compliance Report -- go-ethereum

## Report Information

| Field | Value |
|-------|-------|
| EIP | 1559 |
| Client | go-ethereum |
| Analyzer | Gemini (gemini-2.5-pro) |
| Generated | 2026-02-14 06:22:18 |
| Version | 1.1.0 |

## Executive Summary

PRSpec analysed 3 files from go-ethereum's EIP-1559 implementation using Gemini (gemini-2.5-pro). Overall verdict: ISSUES FOUND at 63% average confidence. 2 issues detected (1 high, 1 medium).

consensus/misc/eip1559.go — ERROR (0 issues): Gemini analysis failed: 'NoneType' object has no attribute 'strip'
core/types/transaction.go — PARTIAL_MATCH (1 issues): The provided Go code from `transaction.go` is limited to transaction data structures and does not implement the block va
core/types/tx_dynamic_fee.go — PARTIAL_MATCH (1 issues): The provided go-ethereum code for the EIP-1559 transaction type correctly implements the data structure, signature hashi

| Metric | Value |
|--------|-------|
| Status | ISSUES FOUND |
| Confidence | 63% |
| Files analysed | 3 |
| Issues | 2 (H:1 M:1 L:0) |

## Detailed Findings

### 1. consensus/misc/eip1559.go

**Status**: ERROR | **Confidence**: 0%

Gemini analysis failed: 'NoneType' object has no attribute 'strip'

No issues found in this file.

---

### 2. core/types/transaction.go

**Status**: PARTIAL_MATCH | **Confidence**: 90%

The provided Go code from `transaction.go` is limited to transaction data structures and does not implement the block validation logic from the specification, such as base fee calculation or gas limit validation. For the parts it does cover, it correctly implements the priority fee calculation (`EffectiveGasTip`). However, a critical transaction validation check specified in the EIP, ensuring `max_fee_per_gas` is not less than `max_priority_fee_per_gas`, is absent from the provided file, constituting a partial match with the specification.

#### Issues Found

**1. [HIGH] MISSING_CHECK**

- **Description**: The provided code in `core/types/transaction.go` defines the EIP-1559 transaction structure and some fee-related helper functions. However, it lacks an explicit validation function to enforce the consensus-critical invariant that a transaction's `max_fee_per_gas` must be greater than or equal to its `max_priority_fee_per_gas`. While other fee-related calculations like `EffectiveGasTip` are present, this fundamental transaction validity check is not included within the provided file's scope.
- **Spec Reference**: `assert transaction.max_fee_per_gas >= transaction.max_priority_fee_per_gas`
- **Code Location**: `core/types/transaction.go`
- **Potential Impact**: If this check were missing from the entire client implementation (e.g., in the transaction pool or state transition logic), it would allow invalid transactions to propagate through the network and potentially cause a consensus split. Clients that enforce the check would reject blocks containing such transactions, while clients that do not would accept them, leading to a fork. This also breaks the economic logic of the fee market.
- **Suggestion**: Implement a validation method for the `DynamicFeeTx` struct (or a general `Transaction.Validate()` method) that includes the check `gasFeeCap >= gasTipCap`. This validation should be called upon transaction decoding and before the transaction is added to the transaction pool or included in a block.

---

### 3. core/types/tx_dynamic_fee.go

**Status**: PARTIAL_MATCH | **Confidence**: 100%

The provided go-ethereum code for the EIP-1559 transaction type correctly implements the data structure, signature hashing, and effective gas price logic as laid out in the specification. However, the scope of the provided code is limited to the transaction type definition and does not include the full block validation logic. A minor deviation was identified in the `effectiveGasPrice` function, which, unlike the reference implementation, does not validate that the transaction's fee cap is sufficient to cover the block's base fee, creating a reliance on upstream checks.

#### Issues Found

**1. [MEDIUM] DEVIATION**

- **Description**: The reference specification's `validate_block` function includes an assertion `transaction.max_fee_per_gas >= block.base_fee_per_gas` which ensures transaction processing halts if an invalid transaction is encountered. The Go implementation's `effectiveGasPrice` function does not perform this check internally. If it were ever called with `tx.GasFeeCap < baseFee` (an invalid state), it would proceed to calculate a negative `tip` (priority fee). This would result in an `effective_gas_price` lower than the `baseFee`, and the miner would be paid a negative priority fee, which violates the core EIP-1559 mechanism.
- **Spec Reference**: `assert transaction.max_fee_per_gas >= block.base_fee_per_gas`
- **Code Location**: `effectiveGasPrice`
- **Potential Impact**: While this check is performed elsewhere in the go-ethereum client before this function is called, its absence in this specific function represents a deviation from the reference implementation's defensive, fail-fast approach. If the upstream validation were ever bypassed due to a bug, this function would produce incorrect fee calculations, potentially leading to consensus splits or economic exploits where miners unknowingly pay fees to transaction senders.
- **Suggestion**: For improved robustness and adherence to the principle of defense-in-depth, consider adding a check at the beginning of `effectiveGasPrice` to ensure `tx.GasFeeCap.Cmp(baseFee) >= 0`. This would make the function more resilient to invalid inputs and align its behavior more closely with the reference specification's assertions.

---


## Methodology

This report was generated using PRSpec, an Ethereum specification compliance checker.
The analysis was performed using Gemini (gemini-2.5-pro) to compare the implementation
against the official EIP-1559 specification.

---

*Generated by PRSpec v1.1.0*
