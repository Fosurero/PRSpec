#!/usr/bin/env bash
# Sparse, blob-less clones of the client sources the witness rulebooks and the
# Besu pilot read. Usage: scripts/fetch_clients.sh DEST [besu_ref geth_ref nethermind_ref eips_ref]
# Without refs, the default branches are used; pass SHAs for a reproducible run.
set -euo pipefail
DEST=${1:?usage: fetch_clients.sh DEST [refs...]}
BESU_REF=${2:-} ; GETH_REF=${3:-} ; NM_REF=${4:-} ; EIPS_REF=${5:-}
mkdir -p "$DEST"
clone() { # name url ref paths...
  local name=$1 url=$2 ref=$3; shift 3
  if [ ! -d "$DEST/$name/.git" ]; then
    git clone -q --filter=blob:none --no-checkout "$url" "$DEST/$name"
  fi
  git -C "$DEST/$name" sparse-checkout set --no-cone "$@"
  if [ -n "$ref" ]; then git -C "$DEST/$name" checkout -q "$ref"; else git -C "$DEST/$name" checkout -q; fi
  echo "$name $(git -C "$DEST/$name" rev-parse HEAD)"
}
clone besu https://github.com/besu-eth/besu.git "$BESU_REF" \
  'ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/**' \
  'evm/src/main/java/**' 'datatypes/src/main/java/**' 'config/src/main/java/**'
clone go-ethereum https://github.com/ethereum/go-ethereum.git "$GETH_REF" \
  'params/*.go' 'consensus/misc/eip1559/*.go' 'consensus/misc/eip4844/*.go' \
  'core/types/*.go' 'core/vm/*.go' 'crypto/kzg4844/*.go'
clone nethermind https://github.com/NethermindEth/nethermind.git "$NM_REF" \
  'src/Nethermind/Nethermind.Core/**/*.cs' 'src/Nethermind/Nethermind.Evm/**/*.cs' \
  'src/Nethermind/Nethermind.Specs/**/*.cs' 'src/Nethermind/Nethermind.Evm.Precompiles/**/*.cs'
clone EIPs https://github.com/ethereum/EIPs.git "$EIPS_REF" \
  'EIPS/eip-1559.md' 'EIPS/eip-4844.md' 'EIPS/eip-7691.md'
