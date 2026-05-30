#!/usr/bin/env python3
"""LiDAR에서 직접 건물 풋프린트+높이 추출 (OSM 불필요).
nDSM(지면위높이) 래스터 → 임계화 → 연결성분 → 면적/solidity/평탄도 필터(수목 배제)
→ 윤곽 단순화 → WGS84 폴리곤 + height. MapLibre fill-extrusion용 GeoJSON.
사용: extract_buildings_lidar.py <out.geojson> <epsg> <res_m> <las1> [las2 ...]
"""
import sys, json
import numpy as np
import laspy
from pyproj import Transformer
from scipy.ndimage import minimum_filter, maximum_filter, grey_opening
from skimage.measure import label, regionprops, find_contours, approximate_polygon


def main(out, epsg, res, las_files):
    Xs, Ys, Zs = [], [], []
    for p in las_files:
        las = laspy.read(p)
        Xs.append(np.asarray(las.x)); Ys.append(np.asarray(las.y)); Zs.append(np.asarray(las.z))
    X = np.concatenate(Xs); Y = np.concatenate(Ys); Z = np.concatenate(Zs)
    x0, x1, y0, y1 = X.min(), X.max(), Y.min(), Y.max()
    W = int(np.ceil((x1 - x0) / res)); H = int(np.ceil((y1 - y0) / res))
    print(f"grid {W}x{H} @ {res}m, {X.size:,} pts")

    col = np.clip(((X - x0) / res).astype(np.int32), 0, W - 1)
    row = np.clip(((Y - y0) / res).astype(np.int32), 0, H - 1)
    flat = row * W + col
    # 최대표면(DSM): 셀별 최대 Z
    dsm = np.full(H * W, -1e9)
    np.maximum.at(dsm, flat, Z)
    dsm = dsm.reshape(H, W)
    empty = dsm < -1e8
    dsm[empty] = np.nan
    # 빈셀 채우기(작은 갭)
    from scipy.ndimage import generic_filter  # noqa
    dsm_f = np.where(np.isnan(dsm), -1e9, dsm)
    dsm_fill = maximum_filter(dsm_f, size=3)
    dsm = np.where(np.isnan(dsm), np.where(dsm_fill < -1e8, np.nan, dsm_fill), dsm)
    valid = ~np.isnan(dsm)
    dsm0 = np.where(valid, dsm, np.nanmedian(dsm[valid]))

    # 지면(DTM) 근사: 큰 윈도 morphological opening(min then max)
    win = max(3, int(round(30 / res)))
    ground = grey_opening(dsm0, size=win)
    ndsm = dsm0 - ground
    ndsm[~valid] = 0

    mask = ndsm > 2.5
    lab = label(mask)
    cell_area = res * res
    t = Transformer.from_crs(epsg, 4326, always_xy=True)

    feats = []
    for r in regionprops(lab, intensity_image=ndsm):
        area = r.area * cell_area
        if area < 40 or area > 200000:
            continue
        if r.solidity < 0.55:               # 수목 클럼프 등 불규칙 배제
            continue
        vals = ndsm[r.coords[:, 0], r.coords[:, 1]]
        if vals.std() > 6:                  # 거친 수관 배제(평탄한 지붕만)
            continue
        h = float(np.median(vals))
        if h < 2.5 or h > 200:
            continue
        # 윤곽 추출 + 단순화
        minr, minc, maxr, maxc = r.bbox
        sub = np.zeros((maxr - minr + 2, maxc - minc + 2), np.uint8)
        sub[1:-1, 1:-1] = (lab[minr:maxr, minc:maxc] == r.label)
        cs = find_contours(sub, 0.5)
        if not cs:
            continue
        c = max(cs, key=len)
        c = approximate_polygon(c, tolerance=1.2)
        if len(c) < 4:
            continue
        ring = []
        for rr, cc in c:
            gx = x0 + (minc - 1 + cc) * res
            gy = y0 + (minr - 1 + rr) * res
            lon, lat = t.transform(gx, gy)
            ring.append([round(lon, 7), round(lat, 7)])
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"height": round(h, 1)}})

    json.dump({"type": "FeatureCollection", "features": feats}, open(out, "w"))
    hs = [f["properties"]["height"] for f in feats]
    print(f"wrote {out}: {len(feats)} buildings (LiDAR검출), height {min(hs):.0f}~{max(hs):.0f}m (median {np.median(hs):.0f})")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), sys.argv[4:])
