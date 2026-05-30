#!/usr/bin/env bash
# 웹뷰어 정적 서버. 브라우저에서 http://localhost:8080/ 접속.
# .ply는 viewer/scene.ply (또는 ?ply=경로 쿼리)로 로드.
set -euo pipefail
PORT="${1:-8080}"
cd /home/asus-3080/gsplat-pilot/viewer
echo "뷰어: http://localhost:${PORT}/  (Ctrl+C로 종료)"
exec python3 -m http.server "$PORT"
