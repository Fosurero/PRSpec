# GitHub Issue: Besu EIP-1559 7-Wei Minimum Floor (Not in Spec)

**Repository:** https://github.com/hyperledger/besu
**Labels:** question, EIP-1559

---

## Title
EIP-1559: `LondonFeeMarket` enforces a 7 Wei minimum baseFee floor not specified in the spec

---

## Body

### Summary

While using [PRSpec](https://github.com/safi842/PRSpec) — an automated EIP compliance checker — to audit Besu's EIP-1559 implementation, we found that `LondonFeeMarket` enforces a minimum 7 Wei floor on transaction admission that is not present in the EIP-1559 specification.

### Location

`ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/feemarket/LondonFeeMarket.java`

```java
// Line 35
private static final Wei DEFAULT_BASEFEE_FLOOR = Wei.of(7L);

// Line 53
this.baseFeeFloor = baseFeeInitialValue.isZero() ? Wei.ZERO : DEFAULT_BASEFEE_FLOOR;

// Lines 77–84
@Override
public boolean satisfiesFloorTxFee(final Transaction txn) {
    // ensure effective baseFee is at least above floor
    return txn.getGasPrice()
        .map(Optional::of)
        .orElse(txn.getMaxFeePerGas())
        .filter(fee -> fee.greaterOrEqualThan(baseFeeFloor))
        .isPresent();
}
```

### EIP-1559 Spec

The [EIP-1559 specification](https://eips.ethereum.org/EIPS/eip-1559) defines transaction validity as:

```
assert transaction.max_fee_per_gas >= block.base_fee_per_gas
```

There is **no minimum floor** below which valid EIP-1559 transactions with sufficient `max_fee_per_gas` should be rejected. The spec only requires `max_fee_per_gas ≥ base_fee_per_gas`.

### Observed Behavior

When the network `baseFee` drops below 7 Wei (which can happen on testnets, private networks, or L2s with very low activity), Besu's `satisfiesFloorTxFee()` will reject transactions with `gasPrice < 7 Wei` even if they satisfy `max_fee_per_gas ≥ base_fee_per_gas`. Other clients (go-ethereum, Nethermind) do not enforce this floor and would accept such transactions.

This creates a **cross-client mempool divergence**: a transaction valid per spec and accepted by geth/Nethermind would be rejected by Besu's transaction pool.

### Questions

1. Is this 7 Wei floor intentional (e.g., spam protection)?
2. If so, is it documented as a Besu-specific extension to EIP-1559?
3. Are there plans to align with the spec, or should this be explicitly noted as a known divergence?

### Discovery Method

Found via **PRSpec** ([github.com/safi842/PRSpec](https://github.com/safi842/PRSpec)), an automated LLM-based tool that compares Ethereum client implementations against EIP specifications and flags behavioral deviations. The finding was independently verified by reading the source directly.

---
*PRSpec is an open-source tool built for the Ethereum Foundation grant program to help maintain cross-client EIP compliance.*
