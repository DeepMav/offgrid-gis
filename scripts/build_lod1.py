#!/usr/bin/env python3
"""LOD1 건물: OSM 풋프린트(WGS84) + LiDAR 높이 → 벽+평지붕 압출 OBJ.
풋프린트를 EPSG:5186으로 재투영해 LiDAR와 정합, 폴리곤 내부 점의 높이로 압출.
좌표는 LiDAR 타일 센터(mean XY, min Z) 기준으로 정렬(점군 뷰어와 동일 프레임).
사용: build_lod1.py <buildings.json> <tile.las> <out.obj>
"""
import sys, json
import numpy as np
import laspy
from pyproj import Transformer
from shapely.geometry import Polygon
from matplotlib.path import Path
import mapbox_earcut as earcut


def _rings_from_geojson(data):
    """GeoJSON FeatureCollection → 외곽 링 리스트 [[(lon,lat),...], ...]"""
    rings = []
    for f in data.get("features", []):
        g = f.get("geometry")
        if not g:
            continue
        if g["type"] == "Polygon":
            rings.append(g["coordinates"][0])
        elif g["type"] == "MultiPolygon":
            for poly in g["coordinates"]:
                rings.append(poly[0])
    return rings


def main(geojson, las_path, out_obj):
    data = json.load(open(geojson))
    rings_ll = _rings_from_geojson(data)
    print(f"footprints: {len(rings_ll)}")

    t = Transformer.from_crs(4326, 5186, always_xy=True)
    las = laspy.read(las_path)
    X, Y, Z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
    cx, cy, cz = X.mean(), Y.mean(), Z.min()        # 점군 뷰어와 동일 센터
    ground = float(np.percentile(Z, 5))             # 지면 기준 높이

    verts = []   # (x,y,z) centered
    faces = []   # 1-based indices
    nb = 0
    for ll in rings_ll:
        ring = [t.transform(lon, lat) for lon, lat in ll]   # → 5186
        if len(ring) < 4:
            continue
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        poly = Polygon(ring)
        if not poly.is_valid or poly.area < 4:       # 4m² 미만 제외
            continue
        xmin, ymin, xmax, ymax = poly.bounds
        m = (X >= xmin) & (X <= xmax) & (Y >= ymin) & (Y <= ymax)
        if m.sum() < 8:
            continue
        pts = np.column_stack([X[m], Y[m]])
        inside = Path(np.asarray(ring)).contains_points(pts)
        zin = Z[m][inside]
        if zin.size < 8:
            continue
        roof = float(np.percentile(zin, 90))
        h = roof - ground
        if h < 2 or h > 200:
            continue

        ext = list(poly.exterior.coords)[:-1]        # 닫힘 중복 제거
        n = len(ext)
        base = len(verts)
        # 바닥(ground) 0..n-1, 지붕(roof) n..2n-1
        for (px, py) in ext:
            verts.append((px - cx, py - cy, ground - cz))
        for (px, py) in ext:
            verts.append((px - cx, py - cy, roof - cz))
        # 벽 (각 변마다 2삼각형)
        for i in range(n):
            j = (i + 1) % n
            b0, b1 = base + i + 1, base + j + 1
            t0, t1 = base + n + i + 1, base + n + j + 1
            faces.append((b0, b1, t1)); faces.append((b0, t1, t0))
        # 지붕 캡 (earcut 삼각분할)
        ring2d = np.array(ext, dtype=np.float64)
        tris = earcut.triangulate_float64(ring2d, np.array([n]))
        for k in range(0, len(tris), 3):
            a, b, c = tris[k] + base + n + 1, tris[k+1] + base + n + 1, tris[k+2] + base + n + 1
            faces.append((a, b, c))   # CCW = +Z(위) 방향
        nb += 1

    with open(out_obj, "w") as f:
        f.write(f"# LOD1 buildings: {nb}\n")
        for (x, y, z) in verts:
            f.write(f"v {x:.3f} {y:.3f} {z:.3f}\n")
        for (a, b, c) in faces:
            f.write(f"f {a} {b} {c}\n")
    print(f"wrote {out_obj}: {nb} buildings, {len(verts)} verts, {len(faces)} faces (center {cx:.1f},{cy:.1f})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
