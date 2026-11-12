#!/usr/bin/env bash
# Runs inside the recorded terminal. Every command shown on screen is executed
# for real on this GitHub Actions runner; the model requests happen during the
# recording. Output passes through scrubtty.py (secret redaction + transcript).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
T="$WORK/evidence/terminal-transcript.txt"
FILES=(
  ethereum/blockcreation/src/main/java/org/hyperledger/besu/ethereum/blockcreation/AbstractBlockCreator.java
  ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/feemarket/ExcessBlobGasCalculator.java
  evm/src/main/java/org/hyperledger/besu/evm/gascalculator/CancunGasCalculator.java
)

show() {
  local where="${PWD/#$WORK/\~/demo}"
  printf '\n\033[1;32mrunner@github-actions\033[0m:\033[1;34m%s\033[0m$ %s\n' "$where" "$*"
  printf '\n%s$ %s\n' "$where" "$*" >> "$T"
  sleep 1
}
run() { show "$*"; python3 "$HERE/scrubtty.py" "$T" -- "$@"; }

analyze() {  # side commit: first model that completes wins, every attempt is shown
  local side=$1 sha=$2 candidate provider model var f
  mkdir -p "$WORK/out/$side" && cd "$WORK/out/$side" || return 1
  for candidate in $PRSPEC_MODELS; do
    provider=${candidate%%:*}; model=${candidate#*:}
    case $provider in
      gemini) var=GEMINI_MODEL; [ -n "${GEMINI_API_KEY:-}" ] || continue ;;
      meta)   var=META_MODEL;   [ -n "${MODEL_API_KEY:-}" ] || continue ;;
      *) continue ;;
    esac
    local args=(prspec analyze --eip 4844 --client besu --config ../../demo-config.yaml
                --provider "$provider" --source-dir "../../besu-$side" --ref "$sha"
                --spec-file ../../eips/EIPS/eip-4844.md --multi-file)
    for f in "${FILES[@]}"; do args+=(--file "$f"); done
    args+=(--no-verify --output json,markdown,html --fail-on incomplete)
    show "$var=$model ${args[*]}"
    if env "$var=$model" python3 "$HERE/scrubtty.py" "$T" -- "${args[@]}"; then
      echo "$candidate" > model-used
      cd "$WORK"; return 0
    fi
    mkdir -p failed
    for f in output/*; do if [ -f "$f" ]; then mv "$f" "failed/${model}-${f##*/}"; fi; done
  done
  cd "$WORK"; return 1
}

cd "$WORK" || exit 1
clear
run echo "Live PRSpec run on GitHub Actions: $RUN_URL"
run prspec --version
run git -C besu-before log -1 --date=short --format='%H %ad %s'
run git -C besu-after log -1 --date=short --format='%H %ad %s'
run git -C eips log -1 --date=short --format='%H %ad %s'
analyze before "$BEFORE_SHA"
analyze after "$AFTER_SHA"
run python3 "$HERE/compare.py" out/before out/after
sleep 6
