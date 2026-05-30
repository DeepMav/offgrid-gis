#!/usr/bin/env bash
# run_sfm.sh — 우리가 빌드한 COLMAP(특징추출/매칭, GPU SIFT) + GLOMAP(전역 매퍼)로
# 이미지 폴더에서 COLMAP 포맷 sparse 모델 생성. 3DGS 학습 입력으로 사용.
# 사용: run_sfm.sh <images_dir> <out_dir> [matcher: exhaustive|sequential]
set -euo pipefail
export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$PATH

IMAGES="${1:?usage: run_sfm.sh <images_dir> <out_dir> [exhaustive|sequential]}"
OUT="${2:?out_dir 필요}"
MATCHER="${3:-exhaustive}"
DB="$OUT/database.db"

mkdir -p "$OUT/sparse"
echo "[1/3] COLMAP feature_extractor (GPU SIFT) — images: $IMAGES ($(ls "$IMAGES" | wc -l)장)"
colmap feature_extractor \
  --database_path "$DB" --image_path "$IMAGES" \
  --ImageReader.single_camera 1 \
  --ImageReader.camera_model OPENCV \
  --SiftExtraction.use_gpu 1

echo "[2/3] COLMAP ${MATCHER}_matcher (GPU)"
colmap "${MATCHER}_matcher" --database_path "$DB" --SiftMatching.use_gpu 1

echo "[3/3] GLOMAP mapper (전역 SfM)"
glomap mapper --database_path "$DB" --image_path "$IMAGES" --output_path "$OUT/sparse"

echo "완료. sparse 모델:"
ls -R "$OUT/sparse" | head -20
