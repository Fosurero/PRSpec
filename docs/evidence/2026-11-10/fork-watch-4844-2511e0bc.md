# Fork Watch impact card: EIP-4844

Spec revisions: `2511e0bc^` → `2511e0bc` (ethereum/EIPs)

| Change | Constant | Old | New | Witness rules | Client files to review |
| --- | --- | --- | --- | --- | --- |
| changed | `MAX_DATA_GAS_PER_BLOCK` | `2**19` | `786432` | EIP4844-MAX-BLOB-GAS | besu: `config/src/main/java/org/hyperledger/besu/config/BlobSchedule.java`<br>go-ethereum: `params/config.go`<br>nethermind: `src/Nethermind/Nethermind.Specs/Forks/17_Cancun.cs` |
| changed | `TARGET_DATA_GAS_PER_BLOCK` | `2**18` | `393216` | EIP4844-TARGET-BLOB-GAS | besu: `config/src/main/java/org/hyperledger/besu/config/BlobSchedule.java`<br>go-ethereum: `params/config.go`<br>nethermind: `src/Nethermind/Nethermind.Specs/Forks/17_Cancun.cs` |
| changed | `DATA_GASPRICE_UPDATE_FRACTION` | `2225652` | `3338477` | EIP4844-UPDATE-FRACTION | besu: `config/src/main/java/org/hyperledger/besu/config/BlobSchedule.java`<br>go-ethereum: `params/config.go`<br>nethermind: `src/Nethermind/Nethermind.Specs/Forks/17_Cancun.cs` |

Parameter-level only: prose/algorithm changes in the EIP are not detected here; they are what the LLM analysis and human review are for.
