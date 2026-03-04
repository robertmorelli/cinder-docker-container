#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The command to run inside the container
inner_cmd=(
  PYTHONPATH=/cinder/Tools/benchmarks:/root
  /cinder/python
  /root/tests/regression_check/regression_run.py
)

if [[ "$#" -gt 0 ]]; then
  inner_cmd+=("$@")
fi

printf -v inner_cmd_quoted '%q ' "${inner_cmd[@]}"

# Run inside the container using start.sh from the current directory
START_SKIP_BUILD="${START_SKIP_BUILD:-1}" \
  bash "$SCRIPT_DIR/start.sh" /bin/bash -lc "$inner_cmd_quoted"
