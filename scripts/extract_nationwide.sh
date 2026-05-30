#!/usr/bin/env bash
# 전국 POI + 도로명주소(지역명 포함) PostGIS 적재 (south-korea OSM 전체)
set -uo pipefail
PBF=/home/asus-3080/gsplat-pilot/tools/planetiler/data/sources/south_korea.osm.pbf
# 비밀번호는 PGPASSWORD 환경변수 또는 ~/.pgpass 사용 (예: export PGPASSWORD=...)
PG="PG:host=localhost port=5432 dbname=gis user=postgres"
echo "시작: $(date '+%H:%M:%S')"

echo "[1/4] 시도/시군구 경계 추출"
ogr2ogr -f PostgreSQL "$PG" "$PBF" multipolygons \
  -where "boundary='administrative' AND admin_level IN ('4','6')" \
  -nln admin_raw -lco GEOMETRY_NAME=geom -nlt MULTIPOLYGON -a_srs EPSG:4326 -overwrite 2>&1 | tail -1

echo "[2/4] 전국 POI(named) 추출"
ogr2ogr -f PostgreSQL "$PG" "$PBF" points -where "name IS NOT NULL" \
  -nln poi -lco GEOMETRY_NAME=geom -lco FID=id -nlt POINT -a_srs EPSG:4326 -overwrite 2>&1 | tail -1

echo "[3/4] 전국 주소(addr:street) 추출"
ogr2ogr -f PostgreSQL "$PG" "$PBF" multipolygons -where "other_tags LIKE '%addr:street%'" \
  -nln addr_raw -lco GEOMETRY_NAME=geom -nlt MULTIPOLYGON -a_srs EPSG:4326 -overwrite 2>&1 | tail -1

echo "[4/4] roadaddr 구축(지역명 조인) + 인덱스"
sudo -u postgres psql -d gis 2>&1 <<'SQL' | tail -8
CREATE INDEX IF NOT EXISTS admin_raw_geom ON admin_raw USING gist(geom);
DROP TABLE IF EXISTS roadaddr;
CREATE TABLE roadaddr AS
SELECT (row_number() OVER())::int id, ST_Centroid(geom)::geometry(Point,4326) geom,
       (other_tags::hstore->'addr:street') street,
       (other_tags::hstore->'addr:housenumber') hnum
FROM addr_raw WHERE (other_tags::hstore) ? 'addr:street';
ALTER TABLE roadaddr ADD PRIMARY KEY (id);
CREATE INDEX roadaddr_geom ON roadaddr USING gist(geom);
ALTER TABLE roadaddr ADD COLUMN sido text, ADD COLUMN sigungu text, ADD COLUMN addr text;
UPDATE roadaddr r SET sido = a.name FROM admin_raw a WHERE a.admin_level='4' AND ST_Contains(a.geom, r.geom);
UPDATE roadaddr r SET sigungu = a.name FROM admin_raw a WHERE a.admin_level='6' AND ST_Contains(a.geom, r.geom);
UPDATE roadaddr SET addr = trim(concat_ws(' ', sido, sigungu, street, hnum));
CREATE INDEX roadaddr_addr_trgm ON roadaddr USING gin(addr gin_trgm_ops);
CREATE INDEX IF NOT EXISTS poi_name_trgm ON poi USING gin(name gin_trgm_ops);
ANALYZE roadaddr; ANALYZE poi;
SELECT '전국 도로명주소:' lbl, count(*) FROM roadaddr
UNION ALL SELECT '전국 POI:', count(*) FROM poi;
SQL
echo "종료: $(date '+%H:%M:%S')"
