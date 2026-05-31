#!/usr/bin/env python3
"""가시권용 '건물 차폐' 표면 = 지면(DTM, 최소Z) + 건물 footprint 높이.
LAS가 미분류라 max-Z DSM은 나무·노이즈가 시야를 헛막음 → 지면 위에 건물만 세워
나무/노이즈를 배제. 사람 눈높이 도심 가시권에 적합.
사용: /usr/bin/python3 build_viewshed_surface.py
산출: viewer/gwangju_dsm_3857.tif (지면+건물, EPSG:3857, 1m)  ← /viewshed가 사용
"""
import glob, subprocess, numpy as np, laspy
from osgeo import gdal, osr
gdal.UseExceptions()

LAS = sorted(glob.glob("/home/asus-3080/gsplat-pilot/data/gwangju/*.las"))
VIEWER = "/home/asus-3080/gsplat-pilot/viewer"
DTM = "/tmp/gw_dtm.tif"; OUT = VIEWER + "/gwangju_dsm_3857.tif"
RES = 1.0
P4 = "+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000 +y_0=500000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"

# union 범위 (LAS x=easting, y=northing)
emin=nmin=1e18; emax=nmax=-1e18
for p in LAS:
    h=laspy.open(p).header
    emin=min(emin,h.mins[0]); emax=max(emax,h.maxs[0])
    nmin=min(nmin,h.mins[1]); nmax=max(nmax,h.maxs[1])
W=int((emax-emin)/RES); H=int((nmax-nmin)/RES)
print(f"DTM {W}x{H}")

# 지면 = 셀별 최소Z (나무 밑 지면 통과점 활용). 노이즈 방지 위해 5%분위 근사로 min 사용
dtm=np.full((H,W), 1e9, np.float32); d=dtm.ravel()
for p in LAS:
    las=laspy.read(p)
    e=np.asarray(las.x); n=np.asarray(las.y); z=np.asarray(las.z)
    col=np.clip(((e-emin)/RES).astype(np.int32),0,W-1)
    row=np.clip(((nmax-n)/RES).astype(np.int32),0,H-1)
    fl=row*W+col; o=np.argsort(z)[::-1]   # 내림차순 → 마지막(최소)이 남음
    np.minimum.at(d,fl[o],z[o])
    print(f"  {p.split('/')[-1]}: {len(z):,}")
dtm[dtm>1e8]=-9999.0

s=osr.SpatialReference(); s.ImportFromProj4(P4)
ds=gdal.GetDriverByName("GTiff").Create(DTM,W,H,1,gdal.GDT_Float32,["COMPRESS=DEFLATE"])
ds.SetGeoTransform((emin,RES,0,nmax,0,-RES)); ds.SetProjection(s.ExportToWkt())
ds.GetRasterBand(1).WriteArray(dtm); ds.GetRasterBand(1).SetNoDataValue(-9999); ds=None
subprocess.run(["cp",DTM,"/tmp/_d0.tif"],check=True)
subprocess.run(["gdal_fillnodata.py","-md","25","/tmp/_d0.tif",DTM],check=True)
# 3857 변환
DTM3857="/tmp/gw_dtm_3857.tif"
subprocess.run(["gdalwarp","-t_srs","EPSG:3857","-tr","1","1","-r","near","-dstnodata","-9999",
                "-overwrite","-co","COMPRESS=DEFLATE",DTM,DTM3857],check=True)

# 지면 평활화(6m 평균→bilinear 업샘플): 1m 요철·노이즈 제거 → 눈높이 시선이 매끈히 통과
g=gdal.Open(DTM3857); gt=g.GetGeoTransform(); Wd,Hd=g.RasterXSize,g.RasterYSize
te=[str(gt[0]), str(gt[3]+Hd*gt[5]), str(gt[0]+Wd*gt[1]), str(gt[3])]; g=None
subprocess.run(["gdalwarp","-tr","6","6","-r","average","-dstnodata","-9999","-overwrite",
                DTM3857,"/tmp/gw_coarse.tif"],check=True)
subprocess.run(["gdalwarp","-te",*te,"-ts",str(Wd),str(Hd),"-r","bilinear","-dstnodata","-9999",
                "-overwrite","/tmp/gw_coarse.tif",OUT],check=True)

# 건물 footprint(PostGIS, 높이) → 3857 GeoJSON, 매끈 지면에 가산 → 지면+건물 표면
PG="PG:host=localhost port=5432 dbname=gis user=postgres password=gis"
subprocess.run(["ogr2ogr","-f","GeoJSON","-t_srs","EPSG:3857","/tmp/gw_blds.geojson",
                PG,"-sql","SELECT geom, height FROM gwangju_buildings"],check=True)
subprocess.run(["gdal_rasterize","-a","height","-add","/tmp/gw_blds.geojson",OUT],check=True)
a=gdal.Open(OUT).ReadAsArray(); v=a[a>-9999]
print(f"완료: {OUT}  표고 {v.min():.0f}~{v.max():.0f}m (매끈 지면+건물, 나무·노이즈 제외)")
