#!/usr/bin/env python3
"""gsplat simple_trainer 체크포인트(.pt) → INRIA 포맷 3DGS .ply 변환.
GaussianSplats3D(MIT) 등 표준 웹뷰어가 읽는 포맷.
사용: export_ply.py <ckpt.pt> <out.ply> [max_sh_degree] [max_splats]
  max_sh_degree: 0=DC만(경량/고속), 1~3=고차 밴드 포함(고화질, 기본 3)
  max_splats   : 불투명도 상위 N개만 유지(웹 고속용). 0=전체(기본)
"""
import sys
import numpy as np
import torch
from plyfile import PlyData, PlyElement


def main(ckpt_path: str, ply_path: str, max_sh_degree: int = 3, max_splats: int = 0):
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    splats = ckpt["splats"] if isinstance(ckpt, dict) and "splats" in ckpt else ckpt

    def arr(k):
        return splats[k].detach().cpu().float().numpy()

    means = arr("means")                       # [N,3]
    scales = arr("scales")                      # [N,3] (log-space, INRIA도 log 저장)
    quats = arr("quats")                        # [N,4] (scalar-first w,x,y,z)
    opacities = arr("opacities").reshape(-1, 1) # [N,1] (logit, INRIA도 pre-sigmoid 저장)
    sh0 = arr("sh0")                            # [N,1,3]
    shN = arr("shN")                            # [N,K-1,3]
    N = means.shape[0]

    # 웹 고속용: 불투명도(sigmoid) 상위 max_splats개만 유지
    if max_splats and max_splats < N:
        prob = 1.0 / (1.0 + np.exp(-opacities.reshape(-1)))   # sigmoid
        keep = np.argpartition(-prob, max_splats)[:max_splats]
        means, scales, quats = means[keep], scales[keep], quats[keep]
        opacities, sh0, shN = opacities[keep], sh0[keep], shN[keep]
        N = means.shape[0]

    f_dc = sh0.reshape(N, 3)                                  # [N,3]
    # SH degree 상한 적용: degree d → coeff (d+1)^2, f_rest = (coeff-1) per channel
    keep_coeffs = max(0, (max_sh_degree + 1) ** 2 - 1)        # DC 제외 보존할 고차 계수 수
    shN = shN[:, :keep_coeffs, :]
    f_rest = np.transpose(shN, (0, 2, 1)).reshape(N, -1)      # INRIA: 채널-major [N, 3*keep]
    normals = np.zeros((N, 3), dtype=np.float32)

    names = ["x", "y", "z", "nx", "ny", "nz"]
    names += [f"f_dc_{i}" for i in range(3)]
    names += [f"f_rest_{i}" for i in range(f_rest.shape[1])]
    names += ["opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]

    parts = [means, normals, f_dc] + ([f_rest] if f_rest.shape[1] else []) + [opacities, scales, quats]
    data = np.concatenate(parts, axis=1).astype(np.float32)

    elements = np.empty(N, dtype=[(n, "f4") for n in names])
    for i, n in enumerate(names):
        elements[n] = data[:, i]
    PlyData([PlyElement.describe(elements, "vertex")], text=False).write(ply_path)
    print(f"wrote {ply_path}: {N:,} gaussians, {len(names)} props (SH coeffs/ch={shN.shape[1]+1})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: export_ply.py <ckpt.pt> <out.ply> [max_sh_degree=3] [max_splats=0]")
        sys.exit(1)
    deg = int(sys.argv[3]) if len(sys.argv) >= 4 else 3
    cap = int(sys.argv[4]) if len(sys.argv) >= 5 else 0
    main(sys.argv[1], sys.argv[2], deg, cap)
