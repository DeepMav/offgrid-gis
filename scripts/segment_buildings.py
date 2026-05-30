#!/usr/bin/env python3
"""타일 LiDAR를 OSM 풋프린트로 건물별 점군 PLY(법선 포함)로 분할 → City3D 입력.
면적 상위 N동만(데모). 좌표는 타일 센터 기준으로 정렬(병합 일관성).
사용: segment_buildings.py <buildings.json(4326)> <tile.las> <outdir> [max_buildings=40] [min_area=80]
"""
import sys, os, json
import numpy as np
import laspy
from pyproj import Transformer
from shapely.geometry import Polygon
from matplotlib.path import Path
import pymeshlab as ml


def main(geojson, las_path, outdir, maxb=40, min_area=80.0):
    os.makedirs(outdir, exist_ok=True)
    d = json.load(open(geojson))
    rings = []
    for f in d.get("features", []):
        g = f.get("geometry")
        if not g: continue
        if g["type"] == "Polygon": rings.append(g["coordinates"][0])
        elif g["type"] == "MultiPolygon":
            for poly in g["coordinates"]: rings.append(poly[0])

    t = Transformer.from_crs(4326, 5186, always_xy=True)
    las = laspy.read(las_path)
    X, Y, Z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
    cx, cy, cz = X.mean(), Y.mean(), Z.min()

    # 타일 LiDAR 범위 내 풋프린트만 (전주 전역 → 0024 타일로 한정)
    tx0, tx1, ty0, ty1 = X.min(), X.max(), Y.min(), Y.max()
    cand = []
    for ll in rings:
        ring = [t.transform(lon, lat) for lon, lat in ll]
        if len(ring) < 4: continue
        poly = Polygon(ring)
        if not (poly.is_valid and poly.area >= min_area): continue
        bx0, by0, bx1, by1 = poly.bounds
        if bx1 < tx0 or bx0 > tx1 or by1 < ty0 or by0 > ty1: continue   # 타일 밖 제외
        cand.append((poly.area, ring, poly))
    cand.sort(key=lambda r: -r[0])
    print(f"타일 내 footprints≥{min_area}m²: {len(cand)}, 상위 {maxb}동 처리")

    saved = 0
    for area, ring, poly in cand[:maxb]:
        xmin, ymin, xmax, ymax = poly.bounds
        m = (X >= xmin-1) & (X <= xmax+1) & (Y >= ymin-1) & (Y <= ymax+1)
        if m.sum() < 30: continue
        pts = np.column_stack([X[m], Y[m]])
        inside = Path(np.asarray(ring)).contains_points(pts)
        if inside.sum() < 30: continue
        bx = (X[m][inside] - cx).astype(np.float64)
        by = (Y[m][inside] - cy).astype(np.float64)
        bz = (Z[m][inside] - cz).astype(np.float64)
        # 법선 추정(pymeshlab)
        ms = ml.MeshSet()
        ms.add_mesh(ml.Mesh(vertex_matrix=np.column_stack([bx, by, bz])))
        ms.compute_normal_for_point_clouds(k=16)
        out = os.path.join(outdir, f"bld_{saved:03d}.ply")
        ms.save_current_mesh(out, save_vertex_normal=True, binary=True)
        saved += 1
    print(f"saved {saved} building clouds -> {outdir} (center {cx:.1f},{cy:.1f},{cz:.1f})")
    # 센터 기록(병합 시 좌표 참조)
    json.dump({"center": [cx, cy, cz]}, open(os.path.join(outdir, "_center.json"), "w"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3],
         int(sys.argv[4]) if len(sys.argv) > 4 else 40,
         float(sys.argv[5]) if len(sys.argv) > 5 else 80.0)
