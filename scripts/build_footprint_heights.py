#!/usr/bin/env python3
"""OSM 풋프린트(4326) + LiDAR 높이 → MapLibre fill-extrusion용 GeoJSON.
타일 범위 내 건물만, 폴리곤은 WGS84 유지 + height(m) 속성 부여.
사용: build_footprint_heights.py <buildings_4326.json> <tile.las> <out.geojson>
"""
import sys, json
import numpy as np
import laspy
from pyproj import Transformer
from shapely.geometry import Polygon
from matplotlib.path import Path


def main(geojson, las_path, out):
    d = json.load(open(geojson))
    feats_in = d.get("features", [])

    t = Transformer.from_crs(4326, 5186, always_xy=True)
    las = laspy.read(las_path)
    X, Y, Z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
    tx0, tx1, ty0, ty1 = X.min(), X.max(), Y.min(), Y.max()
    ground = float(np.percentile(Z, 5))

    out_feats = []
    for f in feats_in:
        g = f.get("geometry")
        if not g:
            continue
        polys_ll = [g["coordinates"][0]] if g["type"] == "Polygon" else \
                   [p[0] for p in g["coordinates"]] if g["type"] == "MultiPolygon" else []
        for ll in polys_ll:
            ring5186 = [t.transform(lon, lat) for lon, lat in ll]
            if len(ring5186) < 4:
                continue
            poly = Polygon(ring5186)
            if not poly.is_valid or poly.area < 30:
                continue
            bx0, by0, bx1, by1 = poly.bounds
            if bx1 < tx0 or bx0 > tx1 or by1 < ty0 or by0 > ty1:
                continue
            m = (X >= bx0-1) & (X <= bx1+1) & (Y >= by0-1) & (Y <= by1+1)
            if m.sum() < 8:
                continue
            inside = Path(np.asarray(ring5186)).contains_points(np.column_stack([X[m], Y[m]]))
            zin = Z[m][inside]
            if zin.size < 8:
                continue
            h = float(np.percentile(zin, 90)) - ground
            if h < 2 or h > 200:
                continue
            out_feats.append({"type": "Feature",
                              "geometry": {"type": "Polygon", "coordinates": [ll]},
                              "properties": {"height": round(h, 1)}})

    fc = {"type": "FeatureCollection", "features": out_feats}
    json.dump(fc, open(out, "w"))
    hs = [ft["properties"]["height"] for ft in out_feats]
    print(f"wrote {out}: {len(out_feats)} buildings, height {min(hs):.0f}~{max(hs):.0f}m (median {np.median(hs):.0f})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
