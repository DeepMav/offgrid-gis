#!/usr/bin/env python3
"""점군 PLY → 표면 메시 (screened Poisson). 컬러 보존 + 저밀도 풍선 제거 + 감결.
사용: meshify.py <in_points.ply> <out_mesh.ply> [poisson_depth=11] [target_faces=1500000]
"""
import sys
import numpy as np
import pymeshlab as ml


def main(inp, outp, depth=11, target_faces=1_500_000):
    ms = ml.MeshSet()
    ms.load_new_mesh(inp)                       # mesh 0 = 점군(컬러 보유)
    print("loaded points:", ms.current_mesh().vertex_number())

    ms.compute_normal_for_point_clouds(k=10, smoothiter=2)
    print("normals done")

    ms.generate_surface_reconstruction_screened_poisson(depth=depth, samplespernode=2.0)
    print("poisson mesh:", ms.current_mesh().vertex_number(), "verts,",
          ms.current_mesh().face_number(), "faces")

    # 저밀도(외삽 풍선) 제거: poisson quality(밀도) 하위 백분위 삭제
    q = ms.current_mesh().vertex_scalar_array()
    thr = float(np.percentile(q, 35))
    ms.compute_selection_by_condition_per_vertex(condselect=f"q<{thr}")
    ms.meshing_remove_selected_vertices()
    print("trimmed -> faces", ms.current_mesh().face_number())

    # 점군(mesh 0) → poisson(mesh 1) 컬러 전송 (최근접점)
    try:
        ms.transfer_attributes_per_vertex(sourcemesh=0, targetmesh=ms.current_mesh_id(),
                                          colortransfer=True, upperbound=ml.PercentageValue(2))
        print("color transferred")
    except Exception as e:
        print("color transfer skipped:", e)

    if ms.current_mesh().face_number() > target_faces:
        ms.meshing_decimation_quadric_edge_collapse(targetfacenum=target_faces,
                                                    preservenormal=True, preserveboundary=True)
        print("decimated -> faces", ms.current_mesh().face_number())

    ms.save_current_mesh(outp, save_vertex_color=True, save_vertex_normal=True)
    print("saved", outp, "| faces", ms.current_mesh().face_number())


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: meshify.py <in.ply> <out.ply> [depth=11] [faces=1500000]")
        sys.exit(1)
    d = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    f = int(sys.argv[4]) if len(sys.argv) > 4 else 1_500_000
    main(sys.argv[1], sys.argv[2], d, f)
