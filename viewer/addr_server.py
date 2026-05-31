#!/usr/bin/env python3
"""주소/POI 검색 서버 — PostGIS pg_trgm 유사검색 + 정적파일 서빙.
COEP 없음(martin 타일 교차출처 로드 가능). /search?q=... → JSON.
사용: python3 addr_server.py [port=8082]
"""
import os, sys, json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import psycopg2

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
