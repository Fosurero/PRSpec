# PRSpec witness matrix: EIP-4844

- Spec: `ethereum/EIPs@542e62eb129517130b7facc52bbb9a1f333c711e` (`EIPS/eip-4844.md`, sha256 `2772bdb675d90d89…`)
- besu: `8f01c7a3200780b00163ab76d544e0ef6646da41`
- go-ethereum: `c863eecbddb2c9db2cd2f07bb1db80740d75a5b3`
- nethermind: `8ba0b6d05ea0b036524658f5ba1b6d14afd8f20e`

Deterministic check (no LLM): spec constant vs. the value found at the client anchor. ✅ match · ❌ mismatch · ⚠️ could not check (fail-closed) · ⚪ no anchor yet.

| Rule | Spec constant | Spec value | besu | go-ethereum | nethermind |
| --- | --- | --- | --- | --- | --- |
| `EIP4844-GAS-PER-BLOB` | `GAS_PER_BLOB` | `2**17` | ✅ | ✅ | ✅ |
| `EIP4844-MIN-BLOB-BASE-FEE` | `MIN_BASE_FEE_PER_BLOB_GAS` | `1` | ✅ | ✅ | ✅ |
| `EIP4844-UPDATE-FRACTION` | `BLOB_BASE_FEE_UPDATE_FRACTION` | `3338477` | ✅ | ✅ | ✅ |
| `EIP4844-TARGET-BLOB-GAS` | `TARGET_BLOB_GAS_PER_BLOCK` | `393216` | ✅ | ✅ | ✅ |
| `EIP4844-MAX-BLOB-GAS` | `MAX_BLOB_GAS_PER_BLOCK` | `786432` | ✅ | ✅ | ✅ |
| `EIP4844-TX-TYPE` | `BLOB_TX_TYPE` | `Bytes1(0x03)` | ✅ | ✅ | ✅ |
| `EIP4844-POINT-EVAL-GAS` | `POINT_EVALUATION_PRECOMPILE_GAS` | `50000` | ✅ | ✅ | ✅ |
| `EIP4844-BLOBHASH-OPCODE` | `HASH_OPCODE_BYTE` | `Bytes1(0x49)` | ✅ | ✅ | ✅ |
| `EIP4844-FIELD-ELEMENTS` | `FIELD_ELEMENTS_PER_BLOB` | `4096` | ⚪ | ✅ | ⚪ |

## Evidence

All mapped rules match.

Limits: constants and simple derived values only; a ✅ is not a proof of behavioural compliance. Anchors are reviewed against the commits listed in the rulebook; a moved constant shows as ⚠️, never as ✅.
