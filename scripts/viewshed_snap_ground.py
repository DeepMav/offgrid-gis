#!/usr/bin/env python3
"""관측점이 건물/수목 위(DSM 표면이 지면보다 높음)에 떨어지면, 주변에서 가장 가까운
지면 셀(도로·개활지)로 스냅. addr_server /viewshed(광주 DSM)가 호출.
입력: lon lat   출력(stdout): "X_3857 Y_3857 corrected(0|1)"
"""
import sys, math
import numpy as np
from osgeo import gdal

DSM = "/home/asus-3080/gsplat-pilot/viewer/gwangju_dsm_3857.tif"
OS = 20037508.342789244
R = 40          # 스냅 탐색 반경(px ≈ m)
ON_STRUCT = 2.5  # 지면보다 이만큼 높으면 건물/수목 위로 판단

lon, lat = float(sys.argv[1]), float(sys.argv[2])
X = lon * OS / 180.0
Y = math.log(math.tan((90 + lat) * math.pi / 360.0)) * OS / math.pi

ds = gdal.Open(DSM); gt = ds.GetGeoTransform()
W, H = ds.RasterXSize, ds.RasterYSize
b = ds.GetRasterBand(1); nd = b.GetNoDataValue()
col = int((X - gt[0]) / gt[1]); row = int((Y - gt[3]) / gt[5])

c0 = max(0, col - R); r0 = max(0, row - R)
win = b.ReadAsArray(c0, r0, min(W - c0, 2*R+1), min(H - r0, 2*R+1))
corrected = 0
if win is not None:
    win = win.astype(float)
    valid = win[win != nd]
    if valid.size:
        ground = float(np.percentile(valid, 8))      # 주변 지면 추정(저분위)
        oc, orow = col - c0, row - r0
        obsz = win[orow, oc] if (0 <= orow < win.shape[0] and 0 <= oc < win.shape[1]) else ground
        if obsz - ground > ON_STRUCT:                # 건물/수목 위 → 지면 스냅
            mask = (win != nd) & (win <= ground + 1.5)
            ys, xs = np.where(mask)
            if xs.size:
                k = np.argmin((xs - oc)**2 + (ys - orow)**2)
                col, row = c0 + int(xs[k]), r0 + int(ys[k])
                X = gt[0] + (col + 0.5) * gt[1]
                Y = gt[3] + (row + 0.5) * gt[5]
                corrected = 1
print(f"{X} {Y} {corrected}")
