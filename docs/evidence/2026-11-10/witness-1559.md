# PRSpec witness matrix: EIP-1559

- Spec: `ethereum/EIPs@542e62eb129517130b7facc52bbb9a1f333c711e` (`EIPS/eip-1559.md`, sha256 `4460ad966a22d850…`)
- besu: `8f01c7a3200780b00163ab76d544e0ef6646da41`
- go-ethereum: `c863eecbddb2c9db2cd2f07bb1db80740d75a5b3`
- nethermind: `8ba0b6d05ea0b036524658f5ba1b6d14afd8f20e`

Deterministic check (no LLM): spec constant vs. the value found at the client anchor. ✅ match · ❌ mismatch · ⚠️ could not check (fail-closed) · ⚪ no anchor yet.

| Rule | Spec constant | Spec value | besu | go-ethereum | nethermind |
| --- | --- | --- | --- | --- | --- |
| `EIP1559-ELASTICITY` | `ELASTICITY_MULTIPLIER` | `2` | ✅ | ✅ | ✅ |
| `EIP1559-DENOMINATOR` | `BASE_FEE_MAX_CHANGE_DENOMINATOR` | `8` | ✅ | ✅ | ✅ |
| `EIP1559-INITIAL-BASE-FEE` | `INITIAL_BASE_FEE` | `1000000000` | ✅ | ✅ | ✅ |

## Evidence

All mapped rules match.

Limits: constants and simple derived values only; a ✅ is not a proof of behavioural compliance. Anchors are reviewed against the commits listed in the rulebook; a moved constant shows as ⚠️, never as ✅.
