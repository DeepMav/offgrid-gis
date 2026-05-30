
---
## 6. 로컬(오프라인) 지도 서버 — 추가 라이선스 (2026-05-30)
**도구(🟢 전부 퍼미시브)**: planetiler(Apache-2.0), tilemaker(FTWPL/보통), tileserver-gl(BSD-3), osm2pgsql(GPL-서버용).
**데이터**:
- OSM/Geofabrik 남한 .pbf = **ODbL 1.0** 🟡 (상용OK + 출처표기 "© OpenStreetMap contributors" + 파생DB share-alike). 렌더 PMTiles=Produced Work라 독점제품 동봉 가능(표기 필수).
- planetiler 부가: Natural Earth(PD 🟢), water_polygons/lake_centerlines(ODbL 🟡).
- **국가공간정보 GIS건물통합정보 = CC BY-NC-ND 🔴 (비영리·변경금지 → 상용/군납 불가)**. 정확한 한국건물이지만 못 씀.
- VWorld 🔴, AI Hub LiDAR=모델만🟡.
**결론**: 상용/군납 로컬 지도 = **planetiler+OSM(ODbL, 표기) 베이스 + 자체취득(드론/측량) 데이터**. 정부 정밀데이터는 대부분 비영리 한정이라 배제. 완전 오프라인 자체호스팅이라 군납 외부의존 요건 충족.
