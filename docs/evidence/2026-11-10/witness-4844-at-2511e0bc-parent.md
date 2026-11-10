# PRSpec witness matrix: EIP-4844

- Spec: `ethereum/EIPs@2511e0bc^` (`EIPS/eip-4844.md`, sha256 `c295779bb19c7ff7…`)
- besu: `8f01c7a3200780b00163ab76d544e0ef6646da41`
- go-ethereum: `c863eecbddb2c9db2cd2f07bb1db80740d75a5b3`
- nethermind: `8ba0b6d05ea0b036524658f5ba1b6d14afd8f20e`

Deterministic check (no LLM): spec constant vs. the value found at the client anchor. ✅ match · ❌ mismatch · ⚠️ could not check (fail-closed) · ⚪ no anchor yet.

| Rule | Spec constant | Spec value | besu | go-ethereum | nethermind |
| --- | --- | --- | --- | --- | --- |
| `EIP4844-GAS-PER-BLOB` | `GAS_PER_BLOB` | `2**17` | ✅ | ✅ | ✅ |
| `EIP4844-MIN-BLOB-BASE-FEE` | `MIN_BASE_FEE_PER_BLOB_GAS` | `1` | ✅ | ✅ | ✅ |
| `EIP4844-UPDATE-FRACTION` | `BLOB_BASE_FEE_UPDATE_FRACTION` | `2225652` | ❌ `3338477` | ❌ `3338477` | ❌ `3338477` |
| `EIP4844-TARGET-BLOB-GAS` | `TARGET_BLOB_GAS_PER_BLOCK` | `2**18` | ❌ `393216` | ❌ `393216` | ❌ `393216` |
| `EIP4844-MAX-BLOB-GAS` | `MAX_BLOB_GAS_PER_BLOCK` | `2**19` | ❌ `786432` | ❌ `786432` | ❌ `786432` |
| `EIP4844-TX-TYPE` | `BLOB_TX_TYPE` | `Bytes1(0x03)` | ✅ | ✅ | ✅ |
| `EIP4844-POINT-EVAL-GAS` | `POINT_EVALUATION_PRECOMPILE_GAS` | `50000` | ✅ | ✅ | ✅ |
| `EIP4844-BLOBHASH-OPCODE` | `HASH_OPCODE_BYTE` | `Bytes1(0x49)` | ✅ | ✅ | ✅ |
| `EIP4844-FIELD-ELEMENTS` | `FIELD_ELEMENTS_PER_BLOB` | `4096` | ⚪ | ✅ | ⚪ |

## Evidence

- **besu · EIP4844-UPDATE-FRACTION · FAIL**: spec line 51 `BLOB_BASE_FEE_UPDATE_FRACTION = 2225652` (= 2225652); code `config/src/main/java/org/hyperledger/besu/config/BlobSchedule.java:24` → `public static final BlobSchedule CANCUN_DEFAULT = BlobSchedule.create(3, 6, 3338477);` (= 3338477). spec uses historical name DATA_GASPRICE_UPDATE_FRACTION; 
- **besu · EIP4844-TARGET-BLOB-GAS · FAIL**: spec line 49 `TARGET_BLOB_GAS_PER_BLOCK = 2**18` (= 262144); code `config/src/main/java/org/hyperledger/besu/config/BlobSchedule.java:24` → `public static final BlobSchedule CANCUN_DEFAULT = BlobSchedule.create(3, 6, 3338477);` (= 393216). spec uses historical name TARGET_DATA_GAS_PER_BLOCK; code value = 3 x GAS_PER_BLOB (131072)
- **besu · EIP4844-MAX-BLOB-GAS · FAIL**: spec line 48 `MAX_BLOB_GAS_PER_BLOCK = 2**19` (= 524288); code `config/src/main/java/org/hyperledger/besu/config/BlobSchedule.java:24` → `public static final BlobSchedule CANCUN_DEFAULT = BlobSchedule.create(3, 6, 3338477);` (= 786432). spec uses historical name MAX_DATA_GAS_PER_BLOCK; code value = 6 x GAS_PER_BLOB (131072)
- **go-ethereum · EIP4844-UPDATE-FRACTION · FAIL**: spec line 51 `BLOB_BASE_FEE_UPDATE_FRACTION = 2225652` (= 2225652); code `params/config.go:243` → `UpdateFraction: 3338477,` (= 3338477). spec uses historical name DATA_GASPRICE_UPDATE_FRACTION; 
- **go-ethereum · EIP4844-TARGET-BLOB-GAS · FAIL**: spec line 49 `TARGET_BLOB_GAS_PER_BLOCK = 2**18` (= 262144); code `params/config.go:241` → `Target:         3,` (= 393216). spec uses historical name TARGET_DATA_GAS_PER_BLOCK; code value = 3 x GAS_PER_BLOB (131072)
- **go-ethereum · EIP4844-MAX-BLOB-GAS · FAIL**: spec line 48 `MAX_BLOB_GAS_PER_BLOCK = 2**19` (= 524288); code `params/config.go:242` → `Max:            6,` (= 786432). spec uses historical name MAX_DATA_GAS_PER_BLOCK; code value = 6 x GAS_PER_BLOB (131072)
- **nethermind · EIP4844-UPDATE-FRACTION · FAIL**: spec line 51 `BLOB_BASE_FEE_UPDATE_FRACTION = 2225652` (= 2225652); code `src/Nethermind/Nethermind.Specs/Forks/17_Cancun.cs:22` → `spec.BlobBaseFeeUpdateFraction = 3338477;` (= 3338477). spec uses historical name DATA_GASPRICE_UPDATE_FRACTION; 
- **nethermind · EIP4844-TARGET-BLOB-GAS · FAIL**: spec line 49 `TARGET_BLOB_GAS_PER_BLOCK = 2**18` (= 262144); code `src/Nethermind/Nethermind.Specs/Forks/17_Cancun.cs:21` → `spec.TargetBlobCount = 3;` (= 393216). spec uses historical name TARGET_DATA_GAS_PER_BLOCK; code value = 3 x GAS_PER_BLOB (131072)
- **nethermind · EIP4844-MAX-BLOB-GAS · FAIL**: spec line 48 `MAX_BLOB_GAS_PER_BLOCK = 2**19` (= 524288); code `src/Nethermind/Nethermind.Specs/Forks/17_Cancun.cs:20` → `spec.MaxBlobCount = 6;` (= 786432). spec uses historical name MAX_DATA_GAS_PER_BLOCK; code value = 6 x GAS_PER_BLOB (131072)

Limits: constants and simple derived values only; a ✅ is not a proof of behavioural compliance. Anchors are reviewed against the commits listed in the rulebook; a moved constant shows as ⚠️, never as ✅.
