#!/usr/bin/env python3
"""여러 LiDAR 타일 + OSM 풋프린트 → MapLibre fill-extrusion GeoJSON (넓은 영역).
건물별 지역 지면(내부점 10퍼센타일)으로 타일간 표고차 대응. height = pct90-pct10.
사용: build_footprint_heights_multi.py <buildings_4326.json> <out.geojson> <epsg> <sub> <las1> [las2 ...]
  epsg: LiDAR 좌표계 (전주=5186, 광주=5181). sub: 점 다운샘플 간격(1=전체, 3=1/3)
"""
import sys, json
import numpy as np
import laspy
from pyproj import Transformer
from shapely.geometry import Polygon
from matplotlib.path import Path


def main(geojson, out, las_files, epsg=5186, sub=1, min_area=30.0, min_pts=8):
    d = json.load(open(geojson))
    t = Transformer.from_crs(4326, epsg, always_xy=True)

    Xs, Ys, Zs, boxes = [], [], [], []
    for p in las_files:
        las = laspy.read(p)
        x, y, z = np.asarray(las.x)[::sub], np.asarray(las.y)[::sub], np.asarray(las.z)[::sub]
        Xs.append(x); Ys.append(y); Zs.append(z)
        boxes.append((x.min(), x.max(), y.min(), y.max()))
    X = np.concatenate(Xs); Y = np.concatenate(Ys); Z = np.concatenate(Zs)
    print(f"tiles {len(las_files)}, points {X.size:,}")

    def in_any_tile(bx0, by0, bx1, by1):
        for tx0, tx1, ty0, ty1 in boxes:
            if not (bx1 < tx0 or bx0 > tx1 or by1 < ty0 or by0 > ty1):
                return True
        return False

    out_feats = []
    for f in d.get("features", []):
        g = f.get("geometry")
        if not g:
            continue
        polys = [g["coordinates"][0]] if g["type"] == "Polygon" else \
                [p[0] for p in g["coordinates"]] if g["type"] == "MultiPolygon" else []
        for ll in polys:
            ring = [t.transform(lon, lat) for lon, lat in ll]
            if len(ring) < 4:
                continue
            poly = Polygon(ring)
            if not poly.is_valid or poly.area < min_area:
                continue
            bx0, by0, bx1, by1 = poly.bounds
            if not in_any_tile(bx0, by0, bx1, by1):
                continue
            m = (X >= bx0-1) & (X <= bx1+1) & (Y >= by0-1) & (Y <= by1+1)
            if m.sum() < min_pts:
                continue
            inside = Path(np.asarray(ring)).contains_points(np.column_stack([X[m], Y[m]]))
            zin = Z[m][inside]
            if zin.size < min_pts:
                continue
            h = float(np.percentile(zin, 90) - np.percentile(zin, 10))  # 건물별 지역 높이
            if h < 2 or h > 200:
                continue
            out_feats.append({"type": "Feature",
                              "geometry": {"type": "Polygon", "coordinates": [ll]},
                              "properties": {"height": round(h, 1)}})

    json.dump({"type": "FeatureCollection", "features": out_feats}, open(out, "w"))
    hs = [ft["properties"]["height"] for ft in out_feats]
    print(f"wrote {out}: {len(out_feats)} buildings, height {min(hs):.0f}~{max(hs):.0f}m (median {np.median(hs):.0f})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[7:], int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6]))
