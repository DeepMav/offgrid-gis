#!/usr/bin/env bash
# pgRouting 도로망 적재 — south_korea PBF → 서울권 도로 토폴로지(ways/ways_vertices_pgr).
# addr_server의 /route 가 pgr_dijkstra로 최단경로 계산.
# 의존: postgresql-16-pgrouting, osm2pgrouting, osmium-tool
# 사용: build_routing.sh [bbox=left,bottom,right,top]  (기본=서울권)
set -uo pipefail
PBF="${PBF:-/home/asus-3080/gsplat-pilot/tools/planetiler/data/sources/south_korea.osm.pbf}"
BBOX="${1:-126.65,37.40,127.25,37.72}"   # 서울권 (RT_AREA와 일치시킬 것)
PGPW="${PGPASSWORD:-gis}"

echo "[1/4] pgrouting 확장"
sudo -u postgres psql -d gis -tAc "CREATE EXTENSION IF NOT EXISTS pgrouting CASCADE;"

echo "[2/4] 도로(highway)만 필터 (전국→경량)"
osmium tags-filter "$PBF" w/highway -o /tmp/roads.osm.pbf --overwrite

echo "[3/4] 영역 추출 → XML ($BBOX)"
osmium extract -b "$BBOX" /tmp/roads.osm.pbf -o /tmp/region_roads.osm --overwrite

echo "[4/4] osm2pgrouting 토폴로지 적재 (ways / ways_vertices_pgr)"
osm2pgrouting -f /tmp/region_roads.osm -c /usr/share/osm2pgrouting/mapconfig.xml \
  -d gis -U postgres -W "$PGPW" -h localhost --clean

sudo -u postgres psql -d gis -tAc "SELECT 'ways', count(*) FROM ways UNION ALL SELECT 'vertices', count(*) FROM ways_vertices_pgr;"
echo "완료. /route?from=lon,lat&to=lon,lat 로 경로탐색."
