#!/usr/bin/env python3
"""건물 OBJ + 정사영상 → 평면 UV 텍스처 GLB (지붕 사진화).
UV = 정사영상 extent 기준 XY 평면투영. 결과 GLB는 deck.gl ScenegraphLayer/three.js로 로드.
사용: texture_buildings_glb.py <buildings.obj> <ortho.png> <ortho_meta.json> <out.glb>
"""
import sys, json
import numpy as np
import trimesh
from PIL import Image


def main(obj_path, ortho_png, meta_json, out_glb):
    meta = json.load(open(meta_json))
    x0, x1, y0, y1 = meta["extent_centered"]
    mesh = trimesh.load(obj_path, process=False)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    V = mesh.vertices  # (n,3) tile-centered (x east, y north, z up)
    # 평면 UV: U=동서, V=남북(이미지 위=북) → V_tex = (y1 - y)/(y1-y0)
    u = (V[:, 0] - x0) / (x1 - x0)
    v = (y1 - V[:, 1]) / (y1 - y0)
    uv = np.clip(np.column_stack([u, v]), 0, 1)

    img = Image.open(ortho_png).convert("RGB")
    mat = trimesh.visual.texture.SimpleMaterial(image=img)
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, image=img, material=mat)
    mesh.export(out_glb)
    print(f"wrote {out_glb}: {len(V)} verts, {len(mesh.faces)} faces, textured")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
