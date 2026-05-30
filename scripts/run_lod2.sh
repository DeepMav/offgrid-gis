#!/usr/bin/env bash
# 건물별 City3D LOD2 재구성 (건물당 타임아웃으로 느린 건물 스킵) → 결과 수집
set -uo pipefail
ROOT=/home/asus-3080/gsplat-pilot
CITY=$ROOT/tools/City3D
BIN=$CITY/build/bin/CLI_Example_2
INST=$CITY/data/building_instances
IN=/tmp/city3d_in
OUT=/tmp/city3d_out
PERB=${1:-90}     # 건물당 타임아웃(초)

mkdir -p "$OUT"; rm -f "$OUT"/*.obj
ok=0; skip=0
for ply in "$IN"/*.ply; do
  name=$(basename "$ply" .ply)
  rm -f "$INST"/*
  cp "$ply" "$INST/"
  ( cd "$(dirname "$BIN")" && timeout "$PERB" ./CLI_Example_2 >/dev/null 2>&1 )
  if [ -f "$INST/${name}_ReconstructedModel.obj" ]; then
    cp "$INST/${name}_ReconstructedModel.obj" "$OUT/"
    f=$(grep -c '^f ' "$INST/${name}_ReconstructedModel.obj")
    echo "OK   $name (faces $f)"; ok=$((ok+1))
  else
    echo "SKIP $name (timeout ${PERB}s / fail)"; skip=$((skip+1))
  fi
done
echo "=== 완료: OK $ok, SKIP $skip ==="
