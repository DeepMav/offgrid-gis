#!/usr/bin/env bash
# 공식 도로명주소 DB(위치정보요약DB SHP 또는 텍스트) → PostGIS roadaddr 교체 적재.
# juso 데이터는 보통 EUC-KR(CP949) 인코딩 + EPSG:5179(UTM-K) 또는 5186. 자동 처리.
# 사용:
#   SHP:   load_official_juso.sh shp  <폴더_또는_SHP경로>  <소스EPSG(예 5179)>
#   텍스트: load_official_juso.sh txt  <텍스트파일>  (구분자/컬럼은 juso 레이아웃에 맞춰 SQL 수정)
set -uo pipefail
# 비밀번호는 PGPASSWORD 환경변수 또는 ~/.pgpass 사용 (예: export PGPASSWORD=...)
PG="PG:host=localhost port=5432 dbname=gis user=postgres"
MODE="${1:?shp|txt}"; SRC="${2:?경로}"; SRCEPSG="${3:-5179}"

if [ "$MODE" = "shp" ]; then
  # 한글 인코딩 + 좌표계 지정 → roadaddr_off 테이블로 적재 (WGS84 변환)
  # juso 건물 SHP의 도로명주소 컬럼명은 데이터셋마다 상이(예: RDNMADR, BULD_NM, ...).
  # 적재 후 실제 컬럼을 확인해 addr 컬럼 매핑(아래 SQL)을 맞추세요.
  SHGCONFIG_OPTS="--config SHAPE_ENCODING CP949"
  ogr2ogr $SHGCONFIG_OPTS -f PostgreSQL "$PG" "$SRC" \
    -s_srs EPSG:$SRCEPSG -t_srs EPSG:4326 \
    -nln roadaddr_off -lco GEOMETRY_NAME=geom -nlt PROMOTE_TO_MULTI -overwrite 2>&1 | tail -2
  echo "=== 적재된 컬럼(도로명주소 필드 확인용) ==="
  sudo -u postgres psql -d gis -tAc "SELECT string_agg(column_name,', ') FROM information_schema.columns WHERE table_name='roadaddr_off';"
  echo "=== 다음 단계: 실제 도로명주소 컬럼을 addr로 매핑 (예시) ==="
  cat <<'NOTE'
  -- 예) 도로명주소 컬럼이 RDNMADR 라면:
  -- ALTER TABLE roadaddr_off ADD COLUMN addr text;
  -- UPDATE roadaddr_off SET addr = "RDNMADR";   -- 실제 컬럼명으로
  -- ALTER TABLE roadaddr_off ALTER COLUMN geom TYPE geometry(Point,4326) USING ST_Centroid(geom);
  -- CREATE INDEX ON roadaddr_off USING gist(geom);
  -- CREATE INDEX ON roadaddr_off USING gin(addr gin_trgm_ops);
  -- 그런 다음 검색서버 DSN의 roadaddr → roadaddr_off로 바꾸거나 테이블 교체.
NOTE
elif [ "$MODE" = "txt" ]; then
  echo "텍스트(위치정보요약DB)는 |구분 EUC-KR. 레이아웃 문서에 맞춰 COPY 후 좌표컬럼으로 geom 생성 필요."
  echo "파일 인코딩 변환: iconv -f CP949 -t UTF-8 \"$SRC\" > /tmp/juso_utf8.txt"
fi
