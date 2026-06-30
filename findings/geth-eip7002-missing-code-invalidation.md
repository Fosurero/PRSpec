# GitHub Issue: go-ethereum EIP-7002/7251 — missing predeploy is silently skipped instead of invalidating the block

**Repository:** https://github.com/ethereum/go-ethereum
**Labels:** question, consensus

---

## Title
EIP-7002/7251: `processRequestsSystemCall` does not invalidate the block when the request predeploy has no code

---

## Body

### Summary

While auditing go-ethereum's execution-layer requests handling with [PRSpec](https://github.com/Fosurero/PRSpec), we noticed that `processRequestsSystemCall` does **not** invalidate the block when there is **no code** at a request predeploy address (`WITHDRAWAL_REQUEST_PREDEPLOY_ADDRESS` for EIP-7002, `CONSOLIDATION_REQUEST_PREDEPLOY_ADDRESS` for EIP-7251).

The canonical execution-specs reference treats a missing system contract as a block-invalidating condition. go-ethereum instead treats the empty return value the same as an empty queue and silently continues.

### Location

`core/state_processor.go` — `processRequestsSystemCall`

```go
ret, _, err := evm.Call(msg.From, *msg.To, msg.Data, gasBudget, common.U2560)
...
if err != nil {
    return fmt.Errorf("system call failed to execute: %v", err)
}
blockAccessList.Merge(bal)

if len(ret) == 0 {
    return nil // skip empty output   <-- no distinction between "empty queue" and "no code"
}
```

Calling an account with no code via `evm.Call` returns `(nil, gas, nil)` — success, empty return data, **no error**. So a missing predeploy reaches `len(ret) == 0` and the function returns `nil`, and the block is accepted.

### Reference behavior (execution-specs)

[`ethereum/execution-specs`](https://github.com/ethereum/execution-specs) (`forks/prague/fork.py`) routes both withdrawals and consolidations through `process_checked_system_transaction`, which raises `InvalidBlock` on empty code:

```python
system_contract_code = get_code(
    untracked_state,
    get_account(untracked_state, target_address).code_hash,
)

if len(system_contract_code) == 0:
    raise InvalidBlock(
        f"System contract address {target_address.hex()} does not contain code"
    )
```

The reference comment explicitly calls out EIP-7002 and EIP-7251 for this case.

### Cross-client comparison

PRSpec ran the same analysis against Nethermind, which **does** distinguish the two cases. Its `ExecutionRequestsProcessor` checks for empty code and invalidates the block, matching the reference. So today:

| Client | Missing predeploy → |
|--------|---------------------|
| execution-specs (reference) | block **invalid** |
| Nethermind | block **invalid** |
| **go-ethereum** | block **accepted** (request type silently omitted) |

### Impact

On correctly-configured networks the predeploys are deployed at the fork transition, so this path is not exercised on mainnet today, and there is **no live consensus split**.

However:
- On a chain where a predeploy is absent or mis-deployed (custom networks, devnets, a botched fork activation), go-ethereum would produce/accept a block that a reference-conformant client rejects — a latent cross-client divergence on exactly the withdrawal/consolidation path that staking protocols rely on.
- The code conflates "deployed contract, empty queue" with "no contract at all," weakening the spec's `no code ⇒ invalid block` guarantee.

### Question

1. Is the missing-code check intentionally omitted because the predeploys are assumed to always be present after the fork transition?
2. If so, would it be worth adding an explicit empty-code assertion (matching the execution-specs reference) to make the invariant robust against mis-configured genesis/fork setups?

### Discovery Method

Found via **PRSpec** ([github.com/Fosurero/PRSpec](https://github.com/Fosurero/PRSpec)), an automated LLM-based EIP compliance checker. The finding was graded **CONFIRMED at 100/100 confidence** by adversarial verification and then re-checked by hand against both the go-ethereum source and the execution-specs `forks/prague/fork.py` reference.

---
*PRSpec is an open-source tool that helps maintain cross-client EIP compliance.*
