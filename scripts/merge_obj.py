#!/usr/bin/env python3
"""여러 OBJ(같은 좌표계)를 하나로 병합. 정점 인덱스 오프셋 처리.
사용: merge_obj.py <out.obj> <in1.obj> [in2.obj ...]  또는  merge_obj.py <out.obj> <dir>
"""
import sys, os, glob


def main(out, inputs):
    files = []
    for p in inputs:
        if os.path.isdir(p):
            files += sorted(glob.glob(os.path.join(p, "*.obj")))
        else:
            files.append(p)
    voff = 0
    nv = nf = nb = 0
    with open(out, "w") as o:
        for f in files:
            local_v = 0
            for line in open(f):
                if line.startswith("v "):
                    o.write(line); local_v += 1; nv += 1
                elif line.startswith("f "):
                    parts = line.split()[1:]
                    idx = []
                    for p in parts:
                        i = int(p.split("/")[0])
                        idx.append(str(i + voff))
                    o.write("f " + " ".join(idx) + "\n"); nf += 1
            voff += local_v
            nb += 1
    print(f"merged {nb} files -> {out}: {nv} verts, {nf} faces")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
