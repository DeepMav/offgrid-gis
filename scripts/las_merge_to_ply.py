#!/usr/bin/env python3
"""여러 항공 LiDAR .las를 공통 좌표계로 병합 → 컬러 PLY (웹 점군 뷰어용).
타일 정렬 유지를 위해 전역 좌표로 합친 뒤 '한 번만' 센터링. 선택적 다운샘플.
사용: las_merge_to_ply.py <out.ply> <max_points> <in1.las> [in2.las ...]
  max_points: 0=전체, >0이면 그 개수로 균일 다운샘플
"""
import sys
import numpy as np
import laspy
from plyfile import PlyData, PlyElement


def main(out_ply, max_points, las_files):
    xs, ys, zs, rs, gs, bs = [], [], [], [], [], []
    for p in las_files:
        f = laspy.read(p)
        xs.append(np.asarray(f.x)); ys.append(np.asarray(f.y)); zs.append(np.asarray(f.z))
        names = f.point_format.dimension_names
        if all(c in names for c in ("red", "green", "blue")):
            r, g, b = np.asarray(f.red), np.asarray(f.green), np.asarray(f.blue)
            if max(r.max(), g.max(), b.max()) > 255:
                r, g, b = r / 256.0, g / 256.0, b / 256.0
        else:
            z = np.asarray(f.z); t = (z - z.min()) / (np.ptp(z) + 1e-9)
            r, g, b = t * 255, np.clip(1 - abs(t - .5) * 2, 0, 1) * 255, (1 - t) * 255
        rs.append(r); gs.append(g); bs.append(b)
        print(f"  + {p.split('/')[-1]}: {len(f.x):,} pts")

    x = np.concatenate(xs).astype(np.float64)
    y = np.concatenate(ys).astype(np.float64)
    z = np.concatenate(zs).astype(np.float64)
    rgb = np.clip(np.stack([np.concatenate(rs), np.concatenate(gs), np.concatenate(bs)], 1), 0, 255).astype(np.uint8)
    n = x.shape[0]
    print(f"병합 총 {n:,} pts, 범위 X{np.ptp(x):.0f}m Y{np.ptp(y):.0f}m")

    if max_points and n > max_points:
        idx = np.random.default_rng(0).choice(n, max_points, replace=False)
        x, y, z, rgb = x[idx], y[idx], z[idx], rgb[idx]
        print(f"다운샘플 → {max_points:,} pts")

    # 공통 센터: XY 중앙, Z 최소
    cx, cy, cz = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2, z.min()
    x, y, z = (x - cx).astype(np.float32), (y - cy).astype(np.float32), (z - cz).astype(np.float32)

    m = x.shape[0]
    el = np.empty(m, dtype=[("x", "f4"), ("y", "f4"), ("z", "f4"),
                            ("red", "u1"), ("green", "u1"), ("blue", "u1")])
    el["x"], el["y"], el["z"] = x, y, z
    el["red"], el["green"], el["blue"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    PlyData([PlyElement.describe(el, "vertex")], text=False).write(out_ply)
    print(f"wrote {out_ply}: {m:,} pts, extent {np.ptp(x):.0f}x{np.ptp(y):.0f}m height {np.ptp(z):.0f}m")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: las_merge_to_ply.py <out.ply> <max_points> <in1.las> [in2.las ...]")
        sys.exit(1)
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3:])
