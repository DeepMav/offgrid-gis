#!/usr/bin/env python3
"""컬러 LiDAR → top-down 정사영상 PNG (건물 텍스처 + 지면용).
타일 센터 기준 좌표로 정렬(건물 메시와 동일 프레임). extent를 JSON으로 기록.
사용: make_ortho.py <tile.las> <out.png> [res_m=0.25]
"""
import sys, json
import numpy as np
import laspy
from PIL import Image


def main(las_path, out_png, res=0.25):
    f = laspy.read(las_path)
    X, Y, Z = np.asarray(f.x), np.asarray(f.y), np.asarray(f.z)
    r, g, b = np.asarray(f.red), np.asarray(f.green), np.asarray(f.blue)
    if max(r.max(), g.max(), b.max()) > 255:
        r, g, b = r / 256.0, g / 256.0, b / 256.0
    cx, cy, cz = X.mean(), Y.mean(), Z.min()
    x = X - cx; y = Y - cy
    x0, x1, y0, y1 = x.min(), x.max(), y.min(), y.max()
    W = int(np.ceil((x1 - x0) / res)); H = int(np.ceil((y1 - y0) / res))
    print(f"ortho {W}x{H} px @ {res}m, extent x[{x0:.1f},{x1:.1f}] y[{y0:.1f},{y1:.1f}]")

    # 픽셀 인덱스 (이미지 위=북쪽: row = H-1 - (y-y0)/res)
    col = np.clip(((x - x0) / res).astype(np.int32), 0, W - 1)
    row = np.clip((H - 1 - (y - y0) / res).astype(np.int32), 0, H - 1)
    flat = row * W + col
    img = np.zeros((H * W, 3), np.float64)
    cnt = np.zeros(H * W, np.int64)
    for ch, arr in enumerate((r, g, b)):
        np.add.at(img[:, ch], flat, arr)
    np.add.at(cnt, flat, 1)
    nz = cnt > 0
    img[nz] /= cnt[nz][:, None]
    rgb = img.reshape(H, W, 3).astype(np.uint8)
    mask = nz.reshape(H, W)

    # 빈 픽셀 간단 채우기(최근접 다운/업): 작은 갭은 좌우/상하 평균
    from scipy.ndimage import grey_dilation, binary_dilation
    for _ in range(3):
        empty = ~mask
        if not empty.any():
            break
        dil = np.stack([grey_dilation(rgb[:, :, c], size=3) for c in range(3)], -1)
        rgb[empty] = dil[empty]
        mask = binary_dilation(mask)

    Image.fromarray(rgb, "RGB").save(out_png)
    meta = {"center": [cx, cy, cz], "extent_centered": [x0, x1, y0, y1],
            "size": [W, H], "res": res}
    json.dump(meta, open(out_png.rsplit(".", 1)[0] + "_meta.json", "w"))
    print(f"wrote {out_png} + meta")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.25)
