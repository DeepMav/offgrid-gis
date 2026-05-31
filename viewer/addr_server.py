#!/usr/bin/env python3
"""주소/POI 검색 서버 — PostGIS pg_trgm 유사검색 + 정적파일 서빙.
COEP 없음(martin 타일 교차출처 로드 가능). /search?q=... → JSON.
사용: python3 addr_server.py [port=8082]
"""
import os, sys, json, math, subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import psycopg2

# 가시권 시범영역(서울 북부·북한산) DEM — scripts/build_terrain_dem.py로 생성
DEM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "terrain_dem.tif")
VS_AREA = (126.80, 37.52, 127.15, 37.80)  # 가시권 DEM 영역 lon0,lat0,lon1,lat1
RT_AREA = (126.65, 37.40, 127.25, 37.72)  # 경로탐색(서울권 도로망) 영역

# 접속정보는 GIS_DSN 환경변수로 재정의 가능. 비밀번호는 PGPASSWORD/~/.pgpass 사용 권장.
DSN = os.environ.get("GIS_DSN", "host=localhost port=5432 dbname=gis user=postgres")


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/building_pois":
            qs = parse_qs(u.query)
            bid = qs.get("id", [None])[0]
            lon = qs.get("lon", [None])[0]; lat = qs.get("lat", [None])[0]
            rows = []
            try:
                con = psycopg2.connect(DSN); cur = con.cursor()
                if bid is not None:
                    # 건물 풋프린트 안의 POI (공간 포함)
                    cur.execute(
                        """SELECT p.name, p.cat FROM poi p
                           JOIN gwangju_buildings b ON ST_Contains(b.geom, p.geom)
                           WHERE b.id = %s ORDER BY p.name LIMIT 60""", (bid,))
                elif lon is not None and lat is not None:
                    # 전국 건물(좌표 기반): 클릭점 25m 내 POI
                    cur.execute(
                        """SELECT name, cat FROM poi
                           WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_Point(%s,%s),4326)::geography, 25)
                           ORDER BY name LIMIT 60""", (float(lon), float(lat)))
                for name, cat in cur.fetchall():
                    rows.append({"name": name, "cat": cat})
                cur.close(); con.close()
            except Exception as e:
                self.send_response(500); self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode()); return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(rows, ensure_ascii=False).encode("utf-8"))
            return
        if u.path == "/viewshed":
            # 가시권 분석: 관측점에서 보이는 영역 → GeoJSON (gdal_viewshed)
            qs = parse_qs(u.query)
            try:
                lon = float(qs["lon"][0]); lat = float(qs["lat"][0])
            except Exception:
                self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"lon/lat"}'); return
            h = float(qs.get("h", ["10"])[0]); r = float(qs.get("r", ["12000"])[0])
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            if not (VS_AREA[0] <= lon <= VS_AREA[2] and VS_AREA[1] <= lat <= VS_AREA[3]):
                self.wfile.write(json.dumps({"error": "out_of_area", "msg": "가시권 시범영역(서울 북부·북한산) 밖입니다"}, ensure_ascii=False).encode()); return
            OS = 20037508.342789244
            X = lon * OS / 180.0
            Y = math.log(math.tan((90 + lat) * math.pi / 360.0)) * OS / math.pi
            tag = os.urandom(4).hex(); vt = f"/tmp/vs_{tag}.tif"; vp = f"/tmp/vs_{tag}.geojson"; vo = f"/tmp/vs_{tag}_4326.geojson"
            try:
                subprocess.run(["gdal_viewshed", "-md", str(r), "-oz", str(h), "-tz", "1.7", "-ox", str(X), "-oy", str(Y), DEM, vt],
                               check=True, capture_output=True, timeout=60)
                subprocess.run(["gdal_polygonize.py", vt, "-b", "1", "-f", "GeoJSON", vp, "vs", "DN"],
                               check=True, capture_output=True, timeout=60)
                subprocess.run(["ogr2ogr", "-f", "GeoJSON", "-where", "DN=255", "-t_srs", "EPSG:4326", vo, vp],
                               check=True, capture_output=True, timeout=60)
                gj = json.load(open(vo))
                self.wfile.write(json.dumps(gj, ensure_ascii=False).encode("utf-8"))
            except Exception as ex:
                self.wfile.write(json.dumps({"error": str(ex)}).encode())
            finally:
                for f in (vt, vp, vo):
                    try: os.remove(f)
                    except Exception: pass
            return
        if u.path == "/route":
            # 경로탐색: 출발/도착 좌표 → pgr_dijkstra 최단경로 GeoJSON + 거리/시간
            qs = parse_qs(u.query)
            try:
                fl, ft = map(float, qs["from"][0].split(",")); tl, tt = map(float, qs["to"][0].split(","))
            except Exception:
                self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"from/to"}'); return
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            for lon, lat in ((fl, ft), (tl, tt)):
                if not (RT_AREA[0] <= lon <= RT_AREA[2] and RT_AREA[1] <= lat <= RT_AREA[3]):
                    self.wfile.write(json.dumps({"error": "out_of_area", "msg": "경로 시범영역(서울권) 밖입니다"}, ensure_ascii=False).encode()); return
            try:
                con = psycopg2.connect(DSN); cur = con.cursor()
                cur.execute(
                    """WITH s AS (SELECT id FROM ways_vertices_pgr ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s,%s),4326) LIMIT 1),
                            e AS (SELECT id FROM ways_vertices_pgr ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s,%s),4326) LIMIT 1),
                            r AS (SELECT w.the_geom g, w.length_m, w.cost_s
                                  FROM pgr_dijkstra('SELECT gid AS id, source, target, cost, reverse_cost FROM ways',
                                     (SELECT id FROM s),(SELECT id FROM e)) d JOIN ways w ON d.edge=w.gid)
                       SELECT ST_AsGeoJSON(ST_Collect(g)), COALESCE(SUM(length_m),0), COALESCE(SUM(cost_s),0) FROM r""",
                    (fl, ft, tl, tt))
                geom, dist, tsec = cur.fetchone(); cur.close(); con.close()
            except Exception as ex:
                self.wfile.write(json.dumps({"error": str(ex)}).encode()); return
            if not geom or dist == 0:
                self.wfile.write(json.dumps({"error": "no_route", "msg": "경로를 찾지 못했습니다"}, ensure_ascii=False).encode()); return
            feat = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": json.loads(geom), "properties": {"dist_m": round(dist), "time_s": round(tsec)}}]}
            self.wfile.write(json.dumps(feat, ensure_ascii=False).encode("utf-8"))
            return
        if u.path == "/poi_bbox":
            # 뷰포트(bbox) 내 POI를 GeoJSON으로 반환 → 클라이언트 클러스터링용
            qs = parse_qs(u.query)
            try:
                w = float(qs["w"][0]); s = float(qs["s"][0]); e = float(qs["e"][0]); n = float(qs["n"][0])
            except Exception:
                self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"bbox required"}'); return
            lim = min(int(qs.get("limit", ["8000"])[0]), 12000)
            feats = []
            try:
                con = psycopg2.connect(DSN); cur = con.cursor()
                cur.execute(
                    """SELECT name, cat, ST_X(geom), ST_Y(geom) FROM poi
                       WHERE geom && ST_MakeEnvelope(%s,%s,%s,%s,4326) AND name IS NOT NULL
                       LIMIT %s""", (w, s, e, n, lim))
                for name, cat, lon, lat in cur.fetchall():
                    feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                                  "properties": {"name": name, "cat": cat}})
                cur.close(); con.close()
            except Exception as ex:
                self.send_response(500); self.end_headers()
                self.wfile.write(json.dumps({"error": str(ex)}).encode()); return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False).encode("utf-8"))
            return
        if u.path == "/search":
            q = (parse_qs(u.query).get("q", [""])[0]).strip()
            rows = []
            if q:
                try:
                    con = psycopg2.connect(DSN); cur = con.cursor()
                    like = "%" + q + "%"
                    # POI(장소명) + roadaddr(도로명주소) 동시 검색, pg_trgm 유사도 정렬(오타 허용)
                    cur.execute(
                        """SELECT name, lon, lat, score, kind FROM (
                             SELECT name, ST_X(geom) lon, ST_Y(geom) lat,
                                    GREATEST(similarity(name,%s), CASE WHEN name ILIKE %s THEN 1 ELSE 0 END) score, 'POI' kind
                             FROM poi WHERE name %% %s OR name ILIKE %s
                             UNION ALL
                             SELECT addr, ST_X(geom), ST_Y(geom),
                                    GREATEST(similarity(addr,%s), CASE WHEN addr ILIKE %s THEN 1 ELSE 0 END), '도로명주소'
                             FROM roadaddr WHERE addr %% %s OR addr ILIKE %s
                           ) s
                           ORDER BY score DESC, length(name) ASC LIMIT 12""",
                        (q, like, q, like, q, like, q, like))
                    for name, lon, lat, score, kind in cur.fetchall():
                        rows.append({"name": name, "lon": lon, "lat": lat, "score": round(score, 2), "kind": kind})
                    cur.close(); con.close()
                except Exception as e:
                    self.send_response(500); self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode()); return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(rows, ensure_ascii=False).encode("utf-8"))
            return
        return super().do_GET()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8082
    print(f"주소검색 서버: http://localhost:{port}/  (/search?q=)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
