#!/usr/bin/env bash
# run_train.sh — gsplat simple_trainer (MCMC 전략, cap_max=1M 기본 → 10GB 안전)
# 사용: run_train.sh <colmap_data_dir> <result_dir> [data_factor=4] [max_steps=30000]
set -euo pipefail
export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$PATH
export TORCH_CUDA_ARCH_LIST=8.6

DATA="${1:?usage: run_train.sh <colmap_data_dir> <result_dir> [factor] [steps]}"
RESULT="${2:?result_dir 필요}"
FACTOR="${3:-4}"
STEPS="${4:-30000}"
VENV=/home/asus-3080/venvs/gsplat

cd /home/asus-3080/tools/gsplat/examples
"$VENV/bin/python" simple_trainer.py mcmc \
  --data_dir "$DATA" \
  --data_factor "$FACTOR" \
  --result_dir "$RESULT" \
  --max_steps "$STEPS" \
  --disable_viewer
