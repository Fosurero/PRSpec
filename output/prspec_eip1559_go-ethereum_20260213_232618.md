# EIP-1559 Compliance Report — go-ethereum

## Report Information

| Field | Value |
|-------|-------|
| EIP | 1559 |
| Client | go-ethereum |
| Analyzer | Gemini (gemini-2.5-pro) |
| Generated | 2026-02-13 23:26:18 |
| Version | 1.3.0 |

## Executive Summary

- **Overall Status**: ⚠️ ISSUES FOUND
- **Confidence**: 65%
- **Files Analyzed**: 3
- **Total Issues**: 3
- **High Severity**: 2
- **Medium Severity**: 1
- **Low Severity**: 0

## Detailed Findings

### 1. consensus/misc/eip1559.go

**Status**: ERROR | **Confidence**: 0%

Gemini analysis failed: Invalid operation: The `response.text` quick accessor requires the response to contain a valid `Part`, but none were returned. The candidate's [finish_reason](https://ai.google.dev/api/generate-content#finishreason) is 2.

✅ No issues found in this file.

---

### 2. core/types/transaction.go

**Status**: PARTIAL_MATCH | **Confidence**: 95%

The provided Go implementation correctly calculates the effective gas tip (priority fee) according to the specification, including the check that the transaction's `max_fee_per_gas` is sufficient to cover the block's `base_fee_per_gas`. However, the code snippet is missing a critical validation check from the specification: ensuring that a transaction's `max_priority_fee_per_gas` does not exceed its `max_fee_per_gas`.

#### Issues Found

**1. 🔴 [HIGH] MISSING_CHECK**

- **Description**: The EIP-1559 specification requires that a transaction's `max_fee_per_gas` must be greater than or equal to its `max_priority_fee_per_gas`. The provided Go code, which defines the transaction types and related helper functions, does not perform this fundamental validation check. While functions like `calcEffectiveGasTip` behave correctly even with invalid inputs where the tip exceeds the fee cap, the transaction itself is malformed and should be rejected as early as possible.
- **Spec Reference**: `assert transaction.max_fee_per_gas >= transaction.max_priority_fee_per_gas`
- **Code Location**: `core/types/transaction.go`
- **Potential Impact**: If this validation were missing entirely from a client implementation, it could lead to consensus issues. Nodes might disagree on the validity of a block containing such a transaction. It would also allow malformed transactions to propagate on the network and potentially poison transaction pools of nodes that do not perform this check, violating a key invariant of EIP-1559 transactions.
- **Suggestion**: Implement a validation method for the `DynamicFeeTx` struct that is called upon transaction creation or decoding. This method should enforce the invariant `tx.GasTipCap() <= tx.GasFeeCap()`. For example: `if tx.GasTipCap().Cmp(tx.GasFeeCap()) > 0 { return errTipAboveFeeCap }`.

---

### 3. core/types/tx_dynamic_fee.go

**Status**: PARTIAL_MATCH | **Confidence**: 100%

The provided Go code correctly implements the EIP-1559 transaction data structure, RLP encoding, and signature hashing scheme. However, the snippet represents only a partial implementation of the full specification, as it omits the critical block and transaction validation logic detailed in the reference implementation's `validate_block` function. The absence of these validation checks, particularly for fee parameters, could lead to severe consensus failures if not correctly implemented in the state transition code that utilizes this transaction type.

#### Issues Found

**1. 🔴 [HIGH] MISSING_CHECK**

- **Description**: The provided Go code defines the EIP-1559 transaction type and a helper function `effectiveGasPrice` to calculate fees. This function calculates the miner's tip (priority fee) based on the formula `min(max_fee_per_gas - base_fee, max_priority_fee_per_gas)`. The specification requires a validation check to ensure `max_fee_per_gas` is always greater than or equal to the block's `base_fee_per_gas`. If this check is missing from the calling logic, and a transaction with `max_fee_per_gas < base_fee` is processed, the term `max_fee_per_gas - base_fee` becomes negative. This results in a negative priority fee, which would cause the block producer's balance to be debited instead of credited, a critical flaw.
- **Spec Reference**: `assert transaction.max_fee_per_gas >= block.base_fee_per_gas`
- **Code Location**: `This check is missing from the provided code snippet, but should be implemented in the block validation logic that uses the `DynamicFeeTx` type (e.g., in the state transition function).`
- **Potential Impact**: If the validation is not performed by the state transition logic, it could lead to a consensus failure. Malicious transactions could be crafted to drain the balance of block producers. Different client implementations handling this edge case differently would result in a chain split.
- **Suggestion**: Ensure that the state transition logic that processes blocks containing EIP-1559 transactions strictly validates that `tx.GasFeeCap` is greater than or equal to the parent block's `base_fee_per_gas` before the transaction is executed, as mandated by the specification. This check is crucial for the security of the fee market mechanism.

**2. 🟡 [MEDIUM] MISSING_CHECK**

- **Description**: The specification includes a sanity check to ensure a transaction's `max_fee_per_gas` is greater than or equal to its `max_priority_fee_per_gas`. This ensures the transaction parameters are logical, as the priority fee is a component of the total fee. The provided code snippet for the transaction type does not contain this validation. While the fee calculation mathematics do not break if this invariant is violated, accepting such a transaction into a block is a deviation from the specified protocol rules.
- **Spec Reference**: `assert transaction.max_fee_per_gas >= transaction.max_priority_fee_per_gas`
- **Code Location**: `This check is missing from the provided code snippet, but should be implemented in the transaction validation logic that uses the `DynamicFeeTx` type.`
- **Potential Impact**: Allowing logically malformed transactions on-chain can lead to protocol non-compliance and may cause issues for downstream tooling, explorers, and wallets that rely on this invariant holding true. It represents a deviation from the strict transaction validity conditions defined in the EIP.
- **Suggestion**: Incorporate the validation `tx.GasFeeCap.Cmp(tx.GasTipCap) >= 0` into the transaction validation logic to reject malformed transactions and ensure strict compliance with the EIP-1559 specification.

---


## Methodology

This report was generated using PRSpec, an Ethereum specification compliance checker.
The analysis was performed using Gemini (gemini-2.5-pro) to compare the implementation
against the official EIP-1559 specification.

---

*Generated by PRSpec v1.3.0 | *
