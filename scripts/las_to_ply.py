#!/usr/bin/env python3
"""항공 LiDAR .las → 컬러 바이너리 PLY (웹 점군 뷰어용).
좌표 센터링(UTM 큰 값 → three.js float 정밀도 보호), RGB 16→8bit.
사용: las_to_ply.py <in.las> <out.ply> [max_points=0(전체)]
"""
import sys
import numpy as np
import laspy
from plyfile import PlyData, PlyElement


def main(las_path, ply_path, max_points=0):
    f = laspy.read(las_path)
    n = f.header.point_count
    xyz = np.vstack([f.x, f.y, f.z]).T.astype(np.float64)

    # RGB (16-bit → 8-bit). 색이 없으면 높이 컬러맵.
    names = f.point_format.dimension_names
    if all(c in names for c in ("red", "green", "blue")):
        rgb = np.vstack([f.red, f.green, f.blue]).T.astype(np.float32)
        if rgb.max() > 255:
            rgb = rgb / 256.0
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    else:
        z = xyz[:, 2]
        t = (z - z.min()) / (z.ptp() + 1e-9)
        rgb = (np.stack([t, np.clip(1 - abs(t - 0.5) * 2, 0, 1), 1 - t], 1) * 255).astype(np.uint8)

    if max_points and n > max_points:
        idx = np.random.default_rng(0).choice(n, max_points, replace=False)
        xyz, rgb = xyz[idx], rgb[idx]

    # 센터링: XY는 중앙, Z는 최소(지면 0). Z-up → three.js Y-up 변환은 뷰어에서 처리.
    center = np.array([xyz[:, 0].mean(), xyz[:, 1].mean(), xyz[:, 2].min()])
    xyz = (xyz - center).astype(np.float32)

    m = xyz.shape[0]
    el = np.empty(m, dtype=[("x", "f4"), ("y", "f4"), ("z", "f4"),
                            ("red", "u1"), ("green", "u1"), ("blue", "u1")])
    el["x"], el["y"], el["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    el["red"], el["green"], el["blue"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    PlyData([PlyElement.describe(el, "vertex")], text=False).write(ply_path)
    print(f"wrote {ply_path}: {m:,} points (center XY subtracted), "
          f"extent {xyz[:,0].ptp():.0f}x{xyz[:,1].ptp():.0f}m, height {xyz[:,2].ptp():.0f}m")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: las_to_ply.py <in.las> <out.ply> [max_points=0]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
