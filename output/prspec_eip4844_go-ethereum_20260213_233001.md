# EIP-4844 Compliance Report — go-ethereum

## Report Information

| Field | Value |
|-------|-------|
| EIP | 4844 |
| Client | go-ethereum |
| Analyzer | Gemini (gemini-2.5-pro) |
| Generated | 2026-02-13 23:30:01 |
| Version | 1.3.0 |

## Executive Summary

- **Overall Status**: ⚠️ ISSUES FOUND
- **Confidence**: 58%
- **Files Analyzed**: 5
- **Total Issues**: 3
- **High Severity**: 1
- **Medium Severity**: 2
- **Low Severity**: 0

## Detailed Findings

### 1. consensus/misc/eip4844.go

**Status**: FULL_MATCH | **Confidence**: 100%

The analyzed code in `consensus/misc/eip4844/eip4844.go` correctly and fully implements the corresponding sections of the EIP-4844 specification. The functions for calculating excess blob gas (`CalcExcessBlobGas`) and the blob gas price (`CalcBlobGasPrice` via `fakeExponential`) are direct and accurate translations of the specification's pseudocode. The header validation logic (`VerifyEIP4844Header`) also correctly implements its specified check. It is important to note that this file only contains a subset of the total EIP-4844 logic; other critical components like transaction validation, precompiles, and networking are implemented elsewhere in the codebase and were not part of this review.

✅ No issues found in this file.

---

### 2. core/types/tx_blob.go

**Status**: ERROR | **Confidence**: 0%

Failed to parse response: Unterminated string starting at: line 15 column 16 (char 1916)

✅ No issues found in this file.

---

### 3. core/types/blob_tx_sidecar.go

**Status**: UNCERTAIN | **Confidence**: 0%

The implementation code from 'core/types/blob_tx_sidecar.go' could not be fetched due to a 404 Not Found error. A compliance analysis against the EIP-4844 specification is impossible without the source code. Please provide the correct and accessible code for review.

✅ No issues found in this file.

---

### 4. crypto/kzg4844/kzg4844.go

**Status**: PARTIAL_MATCH | **Confidence**: 95%

The provided Go code correctly implements the data structures (Blob, Commitment, Proof) and the versioned hash calculation (`CalcBlobHashV1`) as per the EIP-4844 specification. However, the code is a high-level wrapper, and it is not possible to verify from the snippet alone that the critical, spec-mandated validation checks on cryptographic inputs (commitments, proofs, and field elements) are performed, as this logic is delegated to unseen backend implementations. This represents a significant potential compliance gap.

#### Issues Found

**1. 🔴 [HIGH] MISSING_CHECK**

- **Description**: The provided code in `kzg4844.go` is a high-level wrapper around cryptographic backends (`ckzg` and `gokzg`). The function signatures for `VerifyProof`, `VerifyBlobProof`, etc., accept `Commitment` and `Proof` types. However, the code does not show that the mandatory validation checks (e.g., on-curve and subgroup checks, as specified by the IETF BLS 'KeyValidate' check) are performed on these inputs. The specification for `KZGCommitment` and `KZGProof` types explicitly requires this validation. While this check might be performed in the delegated backend implementations, its absence from the visible code or its documentation makes it impossible to confirm compliance from this file alone.
- **Spec Reference**: `KZGCommitment | Bytes48 | Perform IETF BLS signature "KeyValidate" check but do allow the identity point`
- **Code Location**: `VerifyProof, VerifyBlobProof`
- **Potential Impact**: If the underlying cryptographic libraries do not perform these checks, the system could be vulnerable to attacks using invalid group elements. This could lead to application crashes (Denial of Service), incorrect verification results, or consensus failures if different Ethereum clients handle invalid points differently.
- **Suggestion**: Ensure that the backend implementations (`ckzgVerifyProof`, `gokzgVerifyProof`, etc.) perform the full 'KeyValidate' check on commitment and proof inputs. The documentation for the wrapper functions in `kzg4844.go` should also be updated to explicitly state that these validations are performed as per the EIP-4844 specification.

**2. 🟡 [MEDIUM] MISSING_CHECK**

- **Description**: The `VerifyProof` function, which is a core component for the Point Evaluation Precompile, accepts `point Point` and `claim Claim` as inputs. The specification mandates that these field elements (referred to as `z` and `y`) must be canonical, meaning their integer representation must be strictly less than `BLS_MODULUS`. The provided code for `kzg4844.go` does not show this validation being performed. The underlying consensus specification for `verify_kzg_proof` also requires this check, implying it should be part of the verification function itself.
- **Spec Reference**: `The precompile MUST reject non-canonical field elements (i.e. provided field elements MUST be strictly less than `BLS_MODULUS`).`
- **Code Location**: `VerifyProof`
- **Potential Impact**: Accepting non-canonical field elements can lead to ambiguity and potential consensus splits, as different client implementations might interpret the values differently. It can also introduce cryptographic vulnerabilities or malleability issues in the precompile's logic.
- **Suggestion**: Confirm that the backend implementations (`ckzgVerifyProof` and `gokzgVerifyProof`) validate that the `point` and `claim` inputs are canonical (less than `BLS_MODULUS`) and reject them if they are not. The function's documentation in `kzg4844.go` should also specify this behavior.

---

### 5. params/protocol_params.go

**Status**: PARTIAL_MATCH | **Confidence**: 95%

The provided code file, `params/protocol_params.go`, correctly implements a subset of the constants defined in the EIP-4844 specification. However, it omits several critical parameters that govern the blob gas market and block limits, which is a significant gap for a central protocol parameters file.

#### Issues Found

**1. 🟡 [MEDIUM] MISSING**

- **Description**: The implementation file `params/protocol_params.go` defines several constants related to EIP-4844, such as `BlobTxBlobGasPerBlob` and `BlobTxMinBlobGasprice`. However, it is missing three critical constants from the specification that are essential for the blob gas fee update mechanism and block validation: `MAX_BLOB_GAS_PER_BLOCK`, `TARGET_BLOB_GAS_PER_BLOCK`, and `BLOB_BASE_FEE_UPDATE_FRACTION`.
- **Spec Reference**: `| Constant | Value |
| - | - |
| `MAX_BLOB_GAS_PER_BLOCK` | `786432` |
| `TARGET_BLOB_GAS_PER_BLOCK` | `393216` |
| `BLOB_BASE_FEE_UPDATE_FRACTION` | `3338477` |`
- **Code Location**: `params/protocol_params.go`
- **Potential Impact**: These constants are fundamental to the EIP-4844 gas market. If they are not defined in this central parameters file, they may be hardcoded elsewhere in the codebase, creating a risk of inconsistency and making future updates more difficult. If different parts of the client inadvertently use different values, it could lead to incorrect fee calculations or invalid block production/validation, potentially causing a local fork or consensus failure.
- **Suggestion**: Add the missing constants to the `params/protocol_params.go` file alongside the other EIP-4844 parameters to ensure they are sourced from a single, authoritative location within the codebase. For example:

```go
const (
    // ... existing constants
    BlobTxTargetBlobGas   = 393216  // Corresponds to TARGET_BLOB_GAS_PER_BLOCK
    BlobTxMaxBlobGas      = 786432  // Corresponds to MAX_BLOB_GAS_PER_BLOCK
    BlobFeeUpdateFraction = 3338477 // Corresponds to BLOB_BASE_FEE_UPDATE_FRACTION
    // ... existing constants
)
```

---


## Methodology

This report was generated using PRSpec, an Ethereum specification compliance checker.
The analysis was performed using Gemini (gemini-2.5-pro) to compare the implementation
against the official EIP-4844 specification.

---

*Generated by PRSpec v1.3.0 | *
