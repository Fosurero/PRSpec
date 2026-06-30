# GitHub Issue: Besu EIP-7702 Transaction allows empty authorization list

**Repository:** https://github.com/hyperledger/besu
**Labels:** bug, EIP-7702

---

## Title
EIP-7702: `Transaction.java` constructor does not reject empty `authorization_list`

---

## Body

### Summary

While using [PRSpec](https://github.com/safi842/PRSpec) to analyze Besu's EIP-7702 implementation, we found that the `Transaction` class constructor for `DELEGATE_CODE` (type 0x04) transactions validates that `codeDelegationList.isPresent()` but does **not** validate that the list is non-empty.

The [EIP-7702 specification](https://eips.ethereum.org/EIPS/eip-7702) explicitly states:

> A transaction with an empty `authorization_list` is considered **invalid**.

### Location

`ethereum/core/src/main/java/org/hyperledger/besu/ethereum/core/Transaction.java`

```java
// Constructor validation for DELEGATE_CODE transactions:
// checks isPresent() but NOT non-empty
if (type == TransactionType.DELEGATE_CODE) {
    checkArgument(maybeCodeDelegationList.isPresent(), ...);
    // ← Missing: checkArgument(!maybeCodeDelegationList.get().isEmpty(), ...)
}
```

Compare to the analogous blob transaction check:
```java
// Blob tx: correctly verifies non-empty
checkArgument(!versionedHashes.get().isEmpty(), "versioned hashes must not be empty");
```

### Impact

A `DELEGATE_CODE` transaction object with an empty `authorization_list` can be constructed in memory. `MainnetTransactionValidator` does separately check for non-empty lists at the validator layer, so this does not directly cause consensus issues on the current execution path.

However:
- The data model is more permissive than the spec allows
- Any code path that bypasses the validator (e.g., direct RPC simulation, testing frameworks, internal tooling) could silently construct invalid EIP-7702 transactions
- Creates inconsistency with the blob transaction pattern which correctly validates at construction time

### Suggested Fix

In the `Transaction` constructor, add:

```java
checkArgument(
    maybeCodeDelegationList.map(l -> !l.isEmpty()).orElse(false),
    "EIP-7702 set code transactions must have a non-empty authorization list"
);
```

### Discovery Method

Found via **PRSpec** ([github.com/safi842/PRSpec](https://github.com/safi842/PRSpec)), an automated LLM-based tool that compares Ethereum client implementations against EIP specifications. The finding was verified at confidence 100/100 by adversarial verification.

---
*PRSpec is an open-source tool that helps maintain cross-client EIP compliance.*
