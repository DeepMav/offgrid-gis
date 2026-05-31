#!/usr/bin/env python3
"""LiDAR LAS → 고해상 DSM(표면모델, 건물·수목 포함) GeoTIFF. 건물 단위 가시권용.
laspy로 점 읽어 1m 격자 최대Z(surface)로 래스터화. 광주 LiDAR.
주의: 이 LAS는 좌표축이 (북향X, 동향Y)로 swap → easting=las.y, northing=las.x.
사용: /usr/bin/python3 build_lidar_dsm.py
산출: viewer/gwangju_dsm.tif (EPSG:5181, 1m)
"""
import glob, numpy as np, laspy
from osgeo import gdal, osr

LAS = sorted(glob.glob("/home/asus-3080/gsplat-pilot/data/gwangju/*.las"))
OUT = "/home/asus-3080/gsplat-pilot/viewer/gwangju_dsm.tif"
EPSG = 5181; RES = 1.0

# 헤더로 union 범위 (LAS x=easting, y=northing — 5181 표준)
emin=nmin=1e18; emax=nmax=-1e18
for p in LAS:
    h=laspy.open(p).header
    emin=min(emin,h.mins[0]); emax=max(emax,h.maxs[0])
    nmin=min(nmin,h.mins[1]); nmax=max(nmax,h.maxs[1])
W=int((emax-emin)/RES); H=int((nmax-nmin)/RES)
print(f"DSM {W}x{H} (EPSG:{EPSG}) E {emin:.0f}~{emax:.0f} N {nmin:.0f}~{nmax:.0f}")

dsm=np.full((H,W),-9999.0,np.float32); d=dsm.ravel()
for p in LAS:
    las=laspy.read(p)
    e=np.asarray(las.x); n=np.asarray(las.y); z=np.asarray(las.z)
    col=np.clip(((e-emin)/RES).astype(np.int32),0,W-1)
    row=np.clip(((nmax-n)/RES).astype(np.int32),0,H-1)
    fl=row*W+col; o=np.argsort(z)
    np.maximum.at(d,fl[o],z[o])
    print(f"  {p.split('/')[-1]}: {len(z):,} pts")

# 축 중립 proj4 CRS (E,N) — EPSG 권위축 모호성 회피
s=osr.SpatialReference(); s.ImportFromProj4(
    "+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000 +y_0=500000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")
out=gdal.GetDriverByName("GTiff").Create(OUT,W,H,1,gdal.GDT_Float32,["COMPRESS=DEFLATE"])
out.SetGeoTransform((emin,RES,0,nmax,0,-RES)); out.SetProjection(s.ExportToWkt())
b=out.GetRasterBand(1); b.WriteArray(dsm); b.SetNoDataValue(-9999); out=None
v=dsm>-9999
print(f"유효셀 {v.mean()*100:.1f}%, 표고 {dsm[v].min():.1f}~{dsm[v].max():.1f}m")

# 빈 셀 채우기 + EPSG:3857 변환 (가시권 엔드포인트가 사용하는 최종본)
import subprocess
F3857 = OUT.replace(".tif", "_3857.tif")
subprocess.run(["cp", OUT, "/tmp/_dsm0.tif"], check=True)
subprocess.run(["gdal_fillnodata.py", "-md", "25", "/tmp/_dsm0.tif", OUT], check=True)
subprocess.run(["gdalwarp", "-t_srs", "EPSG:3857", "-tr", "1", "1", "-r", "near",
                "-dstnodata", "-9999", "-overwrite", "-co", "COMPRESS=DEFLATE", OUT, F3857], check=True)
print("완료:", OUT, "+", F3857)
