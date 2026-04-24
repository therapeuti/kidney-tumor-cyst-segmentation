"""
관 구조 제거 스크립트 (혈관, ureter 등)

방식:
    신장 라벨의 안쪽(medial) 방향에서 뻗어나온 가느다란 관 구조를 제거.
    - 좌우 신장의 중심을 구해 안쪽 방향(hilum) 식별
    - 안쪽 영역에서만 erosion 기반 관 구조 필터링 적용
    - 바깥쪽 신장 경계는 보존

사용법:
    python remove_tubular.py S003/S003_Segmentation_A.nii.gz
    python remove_tubular.py S003/S003_Segmentation_*.nii.gz --erosion-iter 5

옵션:
    --kidney-label  : 신장 라벨 번호 (기본: 1)
    --tumor-label   : 종양 라벨 번호 (기본: 2)
    --erosion-iter  : erosion 반복 횟수 (기본: 5, 클수록 굵은 관까지 제거)
    --medial-margin : hilum 쪽 마진 (복셀 단위, 기본: 30)
    --no-backup     : 백업 생성 안 함
    --output-dir    : 출력 폴더 지정 (기본: 원본 파일 덮어쓰기)
"""

import os
import glob
import shutil
import argparse
import nibabel as nib
import numpy as np
from scipy import ndimage


def find_kidney_components(organ_mask, keep_n=2):
    """
    장기 마스크에서 상위 keep_n개 component를 찾고 정보 반환.

    Returns
    -------
    components : list of dict
        각 component의 id, mask, size, centroid
    labeled : np.ndarray
    """
    labeled, n_comp = ndimage.label(organ_mask)
    if n_comp == 0:
        return [], labeled

    sizes = ndimage.sum(organ_mask, labeled, range(1, n_comp + 1))
    top_indices = np.argsort(sizes)[::-1][:keep_n]

    components = []
    for idx in top_indices:
        comp_id = idx + 1
        comp_mask = (labeled == comp_id)
        coords = np.argwhere(comp_mask)
        components.append({
            "id": comp_id,
            "mask": comp_mask,
            "size": int(sizes[idx]),
            "centroid": coords.mean(axis=0),
            "bbox_min": coords.min(axis=0),
            "bbox_max": coords.max(axis=0),
        })

    return components, labeled


def remove_tubular_medial(organ_mask, components, erosion_iter=5, medial_margin=30):
    """
    각 신장의 안쪽(medial, hilum) 방향에서만 관 구조를 제거.

    원리:
      1. 좌우 신장의 centroid로 안쪽 방향 결정
      2. 각 신장의 안쪽 영역 마스크 생성
      3. 안쪽 영역에서만 erosion → 본체 유지 → dilation → 교집합
      4. 바깥쪽은 그대로 보존

    Returns
    -------
    filtered_mask : np.ndarray (uint8)
    stats : dict
    """
    result = organ_mask.copy()
    before_total = int(np.sum(organ_mask))
    total_removed = 0

    if len(components) < 2:
        print(f"    신장이 {len(components)}개뿐 — medial 방향 판별 불가, 전체 영역에 적용")
        # fallback: 전체에 erosion 기반 필터링
        result, removed = _erosion_filter(organ_mask, organ_mask, erosion_iter, keep_n=len(components))
        return result, {"total_removed": removed, "method": "global"}

    # x축 centroid 기준으로 좌/우 정렬
    components.sort(key=lambda c: c["centroid"][0])
    # components[0] = x가 작은 쪽, components[1] = x가 큰 쪽
    # 안쪽 = 서로를 향하는 방향

    midpoint_x = (components[0]["centroid"][0] + components[1]["centroid"][0]) / 2

    for i, comp in enumerate(components):
        cx = comp["centroid"][0]
        bbox_min = comp["bbox_min"]
        bbox_max = comp["bbox_max"]

        # 안쪽 영역 결정
        if cx < midpoint_x:
            # 이 신장은 x가 작은 쪽 → 안쪽은 x가 큰 방향
            medial_start = int(bbox_max[0]) - medial_margin
            medial_end = int(bbox_max[0]) + medial_margin
            side = "x-small side"
        else:
            # 이 신장은 x가 큰 쪽 → 안쪽은 x가 작은 방향
            medial_start = int(bbox_min[0]) - medial_margin
            medial_end = int(bbox_min[0]) + medial_margin
            side = "x-large side"

        # 범위 클리핑
        medial_start = max(0, medial_start)
        medial_end = min(organ_mask.shape[0], medial_end)

        print(f"    Component {comp['id']} ({side}): medial x=[{medial_start}-{medial_end}]")

        # 이 component의 안쪽 영역 마스크
        medial_zone = np.zeros_like(organ_mask, dtype=bool)
        medial_zone[medial_start:medial_end, :, :] = True

        # 이 component에서 안쪽에 해당하는 부분만 추출
        comp_medial = comp["mask"] & medial_zone
        comp_lateral = comp["mask"] & ~medial_zone

        # 안쪽 부분에 erosion 기반 필터링
        if int(np.sum(comp_medial)) > 0:
            comp_all = comp["mask"].astype(np.uint8)
            filtered_medial, removed = _erosion_filter(
                comp_medial.astype(np.uint8), comp_all, erosion_iter, keep_n=1
            )
            total_removed += removed
            print(f"      제거: {removed:,} voxels")

            # 결과 조합: 바깥쪽(원본) + 안쪽(필터링됨)
            # 이 component 영역을 갱신
            comp_result = comp_lateral.astype(np.uint8) | filtered_medial
            result[comp["mask"]] = 0
            result[comp_result > 0] = 1

    return result, {"total_removed": total_removed, "method": "medial"}


def _erosion_filter(target_mask, context_mask, erosion_iter, keep_n=1):
    """
    target_mask 내에서 erosion 기반 관 구조 필터링.
    context_mask는 erosion/dilation 시 참조하는 전체 영역.

    Returns
    -------
    filtered : np.ndarray (uint8)
    removed : int
    """
    struct = ndimage.generate_binary_structure(3, 1)
    before = int(np.sum(target_mask))

    if before == 0:
        return target_mask, 0

    # context_mask 전체에서 erosion → target 영역에서 살아남은 부분 확인
    eroded = ndimage.binary_erosion(
        context_mask, structure=struct, iterations=erosion_iter
    ).astype(np.uint8)

    # eroded에서 가장 큰 component만 유지
    labeled_eroded, n_comp = ndimage.label(eroded)
    if n_comp == 0:
        print(f"      경고: erosion {erosion_iter}회로 모든 영역 사라짐 — 필터링 건너뜀")
        return target_mask, 0

    sizes = ndimage.sum(eroded, labeled_eroded, range(1, n_comp + 1))
    top_indices = np.argsort(sizes)[::-1][:keep_n]

    core_mask = np.zeros_like(eroded)
    for idx in top_indices:
        core_mask[labeled_eroded == (idx + 1)] = 1

    # dilation으로 복원
    dilated_core = ndimage.binary_dilation(
        core_mask, structure=struct, iterations=erosion_iter
    ).astype(np.uint8)

    # target 영역과 교집합
    filtered = (target_mask & dilated_core).astype(np.uint8)
    removed = before - int(np.sum(filtered))

    return filtered, removed


def process_file(path, kidney_label, tumor_label, erosion_iter, medial_margin,
                 backup, output_dir):
    """단일 파일 후처리"""
    fname = os.path.basename(path)
    print(f"\n  {fname}:")

    img = nib.load(path)
    data = np.round(np.asanyarray(img.dataobj)).astype(np.uint16)

    kidney_mask = (data == kidney_label)
    tumor_mask = (data == tumor_label)
    before_kidney = int(np.sum(kidney_mask))
    before_tumor = int(np.sum(tumor_mask))

    # 신장 + 종양 → 장기 마스크
    organ_mask = (kidney_mask | tumor_mask).astype(np.uint8)
    organ_total = int(np.sum(organ_mask))

    if organ_total == 0:
        print(f"    Kidney/tumor labels not found, skipped.")
        return

    # 신장 component 찾기
    components, labeled = find_kidney_components(organ_mask, keep_n=2)
    print(f"    Components: {len(components)}개")
    for c in components:
        print(f"      Component {c['id']}: {c['size']:,} voxels, centroid x={c['centroid'][0]:.0f}")

    # 관 구조 제거
    filtered_organ, stats = remove_tubular_medial(
        organ_mask, components, erosion_iter=erosion_iter, medial_margin=medial_margin
    )

    # 결과 조합: 종양 원위치 유지, 나머지 = 신장
    result = data.copy()
    result[kidney_mask] = 0
    result[tumor_mask] = 0

    final_tumor = tumor_mask & (filtered_organ == 1)
    final_kidney = (filtered_organ == 1) & ~final_tumor

    result[final_kidney] = kidney_label
    result[final_tumor] = tumor_label

    after_kidney = int(np.sum(result == kidney_label))
    after_tumor = int(np.sum(result == tumor_label))

    # 출력 경로
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, fname)
    else:
        out_path = path

    # 백업
    if backup and out_path == path:
        backup_dir = os.path.join(os.path.dirname(path), "backup_original")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, fname)
        if not os.path.exists(backup_path):
            shutil.copy2(path, backup_path)
            print(f"    Backup: {backup_path}")

    # 저장
    new_header = img.header.copy()
    new_header.set_data_dtype(np.uint16)
    new_header["scl_slope"] = 1
    new_header["scl_inter"] = 0
    new_img = nib.Nifti1Image(result, img.affine, new_header)
    nib.save(new_img, out_path)

    # 결과 출력
    print(f"    [신장 label {kidney_label}]")
    print(f"      Voxels: {before_kidney:>10,} -> {after_kidney:>10,} ({(after_kidney - before_kidney) / max(before_kidney, 1) * 100:+.1f}%)")
    print(f"    [종양 label {tumor_label}]")
    print(f"      Voxels: {before_tumor:>10,} -> {after_tumor:>10,} ({(after_tumor - before_tumor) / max(before_tumor, 1) * 100:+.1f}%)")
    print(f"    [관 구조 제거] -{stats['total_removed']:,} voxels ({stats['method']})")
    print(f"    Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="관 구조 제거 (혈관, ureter)")
    parser.add_argument("files", nargs="+", help="NIfTI 파일 경로 (glob 패턴 지원)")
    parser.add_argument("--kidney-label", type=int, default=1, help="신장 라벨 번호 (기본: 1)")
    parser.add_argument("--tumor-label", type=int, default=2, help="종양 라벨 번호 (기본: 2)")
    parser.add_argument("--erosion-iter", type=int, default=5, help="erosion 반복 횟수 (기본: 5)")
    parser.add_argument("--medial-margin", type=int, default=30, help="hilum 쪽 마진 복셀 (기본: 30)")
    parser.add_argument("--no-backup", action="store_true", help="백업 생성 안 함")
    parser.add_argument("--output-dir", type=str, default=None, help="출력 폴더 (기본: 원본 덮어쓰기)")
    args = parser.parse_args()

    paths = []
    for pattern in args.files:
        expanded = glob.glob(pattern)
        if expanded:
            paths.extend(expanded)
        else:
            paths.append(pattern)

    print(f"Processing {len(paths)} file(s)")
    print(f"  kidney={args.kidney_label}, tumor={args.tumor_label}")
    print(f"  erosion_iter={args.erosion_iter}, medial_margin={args.medial_margin}")

    for path in sorted(paths):
        process_file(
            path,
            kidney_label=args.kidney_label,
            tumor_label=args.tumor_label,
            erosion_iter=args.erosion_iter,
            medial_margin=args.medial_margin,
            backup=not args.no_backup,
            output_dir=args.output_dir,
        )
    print()
    print("Done.")


if __name__ == "__main__":
    main()
