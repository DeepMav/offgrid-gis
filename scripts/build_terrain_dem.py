#!/usr/bin/env python3
"""terrarium DEM 타일(AWS, 공개) → 시범영역 DEM/terrain-RGB GeoTIFF (EPSG:3857).
오프라인 지형 3D + 가시권 분석용. 1회 빌드 후 결과만 로컬에서 사용.
사용: /usr/bin/python3 build_terrain_dem.py
산출: viewer/terrain_dem.tif (Float32 표고), viewer/terrain_rgb.tif (terrain-RGB)
"""
import math, os, sys, urllib.request
import numpy as np
from osgeo import gdal, osr

# 시범영역: 서울 북부 + 북한산 (표고 기복 큼)
LON0, LAT0, LON1, LAT1 = 126.80, 37.52, 127.15, 37.80
Z = 13
OUT = "/home/asus-3080/gsplat-pilot/viewer"
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
OS = 20037508.342789244  # web mercator 반경

def lon2x(lon, z): return int((lon + 180.0) / 360.0 * (1 << z))
def lat2y(lat, z):
    r = math.radians(lat)
    return int((1.0 - math.log(math.tan(r) + 1.0/math.cos(r)) / math.pi) / 2.0 * (1 << z))

x0, x1 = lon2x(LON0, Z), lon2x(LON1, Z)
y0, y1 = lat2y(LAT1, Z), lat2y(LAT0, Z)   # y0=북(작은값)
nx, ny = (x1 - x0 + 1), (y1 - y0 + 1)
print(f"zoom {Z}: x {x0}..{x1} ({nx}), y {y0}..{y1} ({ny}) = {nx*ny} tiles")

W, H = nx*256, ny*256
R = np.full((H, W), 128, np.uint8); G = np.zeros((H, W), np.uint8); B = np.zeros((H, W), np.uint8)
tmp = "/tmp/_terr.png"
ok = miss = 0
for j, ty in enumerate(range(y0, y1+1)):
    for i, tx in enumerate(range(x0, x1+1)):
        u = URL.format(z=Z, x=tx, y=ty)
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "offgrid-gis-dem/1.0"})
            data = urllib.request.urlopen(req, timeout=20).read()
            open(tmp, "wb").write(data)
            ds = gdal.Open(tmp); a = ds.ReadAsArray(); ds = None  # (3,256,256)
            R[j*256:(j+1)*256, i*256:(i+1)*256] = a[0]
            G[j*256:(j+1)*256, i*256:(i+1)*256] = a[1]
            B[j*256:(j+1)*256, i*256:(i+1)*256] = a[2]
            ok += 1
        except Exception:
            miss += 1  # 해수면(0m): R=128,G=0,B=0 그대로
    sys.stdout.write(f"\r  rows {j+1}/{ny}  ok={ok} miss={miss}"); sys.stdout.flush()
print()

# geotransform (EPSG:3857)
tile_m = 2*OS / (1 << Z)
top_x = -OS + x0 * tile_m
top_y = OS - y0 * tile_m
pix = tile_m / 256.0
gt = (top_x, pix, 0, top_y, 0, -pix)
srs = osr.SpatialReference(); srs.ImportFromEPSG(3857); wkt = srs.ExportToWkt()

# terrain-RGB GeoTIFF (지형타일용)
drv = gdal.GetDriverByName("GTiff")
rgb = drv.Create(OUT+"/terrain_rgb.tif", W, H, 3, gdal.GDT_Byte, ["COMPRESS=DEFLATE"])
rgb.SetGeoTransform(gt); rgb.SetProjection(wkt)
for k, arr in enumerate([R, G, B]): rgb.GetRasterBand(k+1).WriteArray(arr)
rgb = None

# 표고 디코드 → DEM GeoTIFF (가시권용)
elev = (R.astype(np.float32)*256 + G.astype(np.float32) + B.astype(np.float32)/256.0) - 32768.0
dem = drv.Create(OUT+"/terrain_dem.tif", W, H, 1, gdal.GDT_Float32, ["COMPRESS=DEFLATE"])
dem.SetGeoTransform(gt); dem.SetProjection(wkt)
dem.GetRasterBand(1).WriteArray(elev); dem.GetRasterBand(1).SetNoDataValue(-9999); dem = None
print(f"표고 범위: {elev.min():.0f} ~ {elev.max():.0f} m")
print("완료:", OUT+"/terrain_rgb.tif,", OUT+"/terrain_dem.tif")
