"""
종양 라벨 후처리 (Smoothing) 스크립트

종양(label 2) 라벨의 울퉁불퉁한 경계 사이를 채우고 다듬는 스크립트.

처리 파이프라인:
    [전처리 — 라벨 보정]
    0-pre. 저강도 라벨 삭제
           - 신장/종양 라벨 중 CT intensity ≤ 0 HU인 복셀을 배경(0)으로 삭제
           - 실제 조직이 아닌 공기/노이즈 영역 제거
           - CT 이미지 필요

    0a. 고립 신장 component → 종양 재라벨링
        - 신장 라벨의 connected component 분석
        - 상위 2개(좌우 신장 본체)를 제외한 나머지 고립 component 중
          종양과 인접한 것을 종양으로 재라벨링
        - 종양 돌기 끝부분이 신장으로 잘못 라벨링된 경우 보정

    [후처리 — Smoothing]
    1. 가장 큰 connected component만 유지 (고립 복셀 제거)
    2. Morphological closing (빈 구멍/파인 부분 메움)
    3. Morphological opening (작은 돌출부 제거)
    4. Gaussian smoothing + threshold (경계 부드럽게)
    5. Smoothed 종양이 신장+종양 영역 내로만 제한 (외부 확장 방지)
    6. 종양이 줄어든 영역은 신장으로 복구

사용법:
    python smooth_tumor.py S003/S003_Segmentation_A.nii.gz
    python smooth_tumor.py S004/S004_segmentation_*.nii.gz --sigma 1.0

    CT 이미지는 파일명에서 자동 매칭:
      S003_Segmentation_A.nii.gz → S003_image_A.nii.gz
      S004_segmentation_A.nii.gz → S004_image_A.nii.gz

옵션:
    --kidney-label  : 신장 라벨 번호 (기본: 1)
    --tumor-label   : 종양 라벨 번호 (기본: 2)
    --sigma         : Gaussian smoothing sigma in mm (기본: 1.0)
    --close-iter    : Morphological closing 반복 횟수 (기본: 3)
    --open-iter     : Morphological opening 반복 횟수 (기본: 2)
    --image         : CT 이미지 경로 (생략 시 자동 매칭)
    --no-backup     : 백업 생성 안 함
    --output-dir    : 출력 폴더 지정 (기본: 원본 파일 덮어쓰기)
"""

import os
import re
import glob
import shutil
import argparse
import nibabel as nib
import numpy as np
from scipy import ndimage


def find_ct_image(seg_path):
    """
    세그멘테이션 파일 경로에서 대응하는 CT 이미지 경로를 자동 매칭.
    S003_Segmentation_A.nii.gz → S003_image_A.nii.gz
    """
    seg_path_abs = os.path.abspath(seg_path)
    seg_dir = os.path.dirname(seg_path_abs)
    seg_name = os.path.basename(seg_path_abs)
    match = re.match(r"(S\d+)_[Ss]egmentation_([ADP])\.nii\.gz", seg_name)
    if not match:
        return None
    case, phase = match.group(1), match.group(2)
    img_path = os.path.join(seg_dir, f"{case}_image_{phase}.nii.gz")
    if os.path.exists(img_path):
        return img_path
    return None


def relabel_sandwiched_kidney(data, ct_data, kidney_label, tumor_label,
                              intensity_threshold=0, iterations=2):
    """
    종양과 낮은 intensity 영역 사이에 끼인 얇은 신장 복셀을 종양으로 재라벨링.

    로직:
      1. 종양에 인접한 신장 복셀을 찾음
      2. 그 중 intensity <= threshold인 영역에도 인접한 복셀 = 끼인 신장
      3. 이를 종양으로 재라벨링
      4. iterations회 반복 (1-2 복셀 두께 처리)

    Parameters
    ----------
    data : np.ndarray (uint16)
    ct_data : np.ndarray (float32)
    kidney_label : int
    tumor_label : int
    intensity_threshold : float
        배경으로 판단할 intensity 기준 (기본: 0 HU)
    iterations : int
        반복 횟수 (기본: 2)

    Returns
    -------
    result : np.ndarray (uint16)
    total_relabeled : int
    """
    struct = ndimage.generate_binary_structure(3, 1)
    result = data.copy()
    total_relabeled = 0

    for step in range(iterations):
        kidney_mask = (result == kidney_label)
        tumor_mask = (result == tumor_label)

        # 종양 인접 영역
        tumor_adjacent = ndimage.binary_dilation(tumor_mask, structure=struct).astype(bool)
        # 낮은 intensity 인접 영역
        low_intensity = (ct_data <= intensity_threshold)
        low_adjacent = ndimage.binary_dilation(low_intensity, structure=struct).astype(bool)

        # 종양과 인접 AND 낮은 intensity와 인접 → 끼인 신장
        sandwiched = kidney_mask & tumor_adjacent & low_adjacent

        relabeled = int(np.sum(sandwiched))
        if relabeled == 0:
            break

        result[sandwiched] = tumor_label
        total_relabeled += relabeled
        print(f"      Step {step + 1}: {relabeled:,} voxels 재라벨링")

    return result, total_relabeled


def relabel_isolated_kidney(data, kidney_label, tumor_label, min_kidney_ratio=0.01):
    """
    신장 라벨의 고립 component를 분석하여,
    신장 본체와 분리되어 있고 종양과 인접한 component는 종양으로 재라벨링.

    Parameters
    ----------
    data : np.ndarray (uint16)
    kidney_label : int
    tumor_label : int
    min_kidney_ratio : float
        신장 전체 대비 이 비율 이하인 component를 고립으로 판단 (기본: 1%)

    Returns
    -------
    result : np.ndarray (uint16)
    stats : dict
    """
    kidney_mask = (data == kidney_label)
    tumor_mask = (data == tumor_label)

    total_kidney = int(np.sum(kidney_mask))
    if total_kidney == 0:
        return data.copy(), {"relabeled_count": 0, "relabeled_voxels": 0}

    # 신장 connected component 분석
    labeled, n_comp = ndimage.label(kidney_mask)
    if n_comp <= 1:
        return data.copy(), {"relabeled_count": 0, "relabeled_voxels": 0}

    sizes = ndimage.sum(kidney_mask, labeled, range(1, n_comp + 1))

    # 상위 2개는 좌우 신장 본체로 간주
    sorted_indices = np.argsort(sizes)[::-1]
    main_labels = set()
    for idx in sorted_indices[:2]:
        if sizes[idx] / total_kidney >= min_kidney_ratio:
            main_labels.add(idx + 1)

    # 종양 마스크를 1 복셀 확장하여 인접 판단용 마스크 생성
    struct = ndimage.generate_binary_structure(3, 1)
    tumor_adjacent = ndimage.binary_dilation(tumor_mask, structure=struct).astype(bool)

    result = data.copy()
    relabeled_count = 0
    relabeled_voxels = 0

    for i in range(1, n_comp + 1):
        if i in main_labels:
            continue

        comp_mask = (labeled == i)
        comp_size = int(np.sum(comp_mask))

        # 이 component가 종양과 인접한지 확인
        touches_tumor = np.any(comp_mask & tumor_adjacent)

        if touches_tumor:
            result[comp_mask] = tumor_label
            relabeled_count += 1
            relabeled_voxels += comp_size

    stats = {
        "relabeled_count": relabeled_count,
        "relabeled_voxels": relabeled_voxels,
        "total_kidney_components": n_comp,
        "main_kidney_components": len(main_labels),
    }

    return result, stats


def relabel_kidney_by_neighbor_ratio(data, kidney_label, tumor_label,
                                     min_tumor_ratio=0.8, iterations=3):
    """
    종양 인접 신장 복셀 중, 이웃의 과반수가 종양이면 종양으로 재라벨링.
    신장 본체에 연결되어 있어도 경계의 찔끔한 신장을 정리.

    Parameters
    ----------
    data : np.ndarray (uint16)
    kidney_label : int
    tumor_label : int
    min_tumor_ratio : float
        6-connectivity 이웃 중 종양 비율이 이 값 이상이면 종양으로 변경 (기본: 0.5)
    iterations : int
        반복 횟수 (기본: 3)

    Returns
    -------
    result : np.ndarray (uint16)
    total_relabeled : int
    """
    struct = ndimage.generate_binary_structure(3, 1)
    result = data.copy()
    total_relabeled = 0

    for step in range(iterations):
        kidney_mask = (result == kidney_label)
        tumor_mask = (result == tumor_label)

        # 종양 인접 신장 복셀만 후보
        tumor_adj = ndimage.binary_dilation(tumor_mask, structure=struct)
        candidates = kidney_mask & tumor_adj

        candidate_coords = np.argwhere(candidates)
        if len(candidate_coords) == 0:
            break

        # 각 후보의 6-connectivity 이웃 중 종양 비율 계산
        # convolution으로 이웃의 종양 수를 한번에 계산
        tumor_count = ndimage.convolve(
            tumor_mask.astype(np.float32), struct.astype(np.float32), mode='constant', cval=0
        )
        # 이웃 총 수 (경계 보정)
        ones = np.ones_like(tumor_mask, dtype=np.float32)
        neighbor_count = ndimage.convolve(
            ones, struct.astype(np.float32), mode='constant', cval=0
        )
        # 자기 자신 제외
        tumor_count_neighbors = tumor_count - tumor_mask.astype(np.float32)
        neighbor_count_self_excluded = neighbor_count - 1

        ratio = np.zeros_like(tumor_count)
        valid = neighbor_count_self_excluded > 0
        ratio[valid] = tumor_count_neighbors[valid] / neighbor_count_self_excluded[valid]

        # 후보 중 비율 조건 충족하는 것만 재라벨링
        to_relabel = candidates & (ratio >= min_tumor_ratio)
        relabeled = int(np.sum(to_relabel))

        if relabeled == 0:
            break

        result[to_relabel] = tumor_label
        total_relabeled += relabeled
        print(f"      Step {step + 1}: {relabeled:,} voxels 재라벨링")

    return result, total_relabeled


def remove_low_intensity_labels(data, ct_data, kidney_label, tumor_label, threshold=0):
    """
    신장/종양 라벨 중 intensity <= threshold인 복셀을 배경(0)으로 삭제.

    Returns
    -------
    result : np.ndarray (uint16)
    removed_kidney : int
    removed_tumor : int
    """
    low_intensity = (ct_data <= threshold)
    kidney_low = (data == kidney_label) & low_intensity
    tumor_low = (data == tumor_label) & low_intensity

    removed_kidney = int(np.sum(kidney_low))
    removed_tumor = int(np.sum(tumor_low))

    result = data.copy()
    result[kidney_low] = 0
    result[tumor_low] = 0
    return result, removed_kidney, removed_tumor


def expand_tumor_by_intensity(data, ct_data, tumor_label, kidney_label,
                              sigma_range=2.0, iterations=2):
    """
    종양 경계 주변 신장 복셀 중 intensity가 종양과 비슷한 것을 종양으로 재라벨링.

    종양 intensity 분포(mean ± sigma_range * std)를 계산하고,
    경계 인접 신장 복셀이 그 범위 안이면 종양으로 변경.

    Parameters
    ----------
    data : np.ndarray (uint16)
    ct_data : np.ndarray (float32)
    tumor_label : int
    kidney_label : int
    sigma_range : float
        평균 ± sigma_range * 표준편차 범위 (기본: 2.0)
    iterations : int
        반복 횟수 (기본: 2)

    Returns
    -------
    result : np.ndarray (uint16)
    total_relabeled : int
    """
    struct = ndimage.generate_binary_structure(3, 1)
    result = data.copy()
    total_relabeled = 0

    for step in range(iterations):
        tumor_mask = (result == tumor_label)
        kidney_mask = (result == kidney_label)

        tumor_voxels = ct_data[tumor_mask]
        if len(tumor_voxels) == 0:
            break

        t_mean = float(np.mean(tumor_voxels))
        t_std = float(np.std(tumor_voxels))
        low = t_mean - sigma_range * t_std
        high = t_mean + sigma_range * t_std

        if step == 0:
            print(f"      종양 intensity: {t_mean:.1f} ± {t_std:.1f} HU, 범위: [{low:.0f} ~ {high:.0f}]")

        # 종양 인접 신장 복셀
        tumor_adj = ndimage.binary_dilation(tumor_mask, structure=struct)
        candidates = kidney_mask & tumor_adj

        # intensity가 종양 범위 내인 것만
        in_range = (ct_data >= low) & (ct_data <= high)
        to_relabel = candidates & in_range

        relabeled = int(np.sum(to_relabel))
        if relabeled == 0:
            break

        result[to_relabel] = tumor_label
        total_relabeled += relabeled
        print(f"      Step {step + 1}: {relabeled:,} voxels 재라벨링")

    return result, total_relabeled


def surface_ratio(binary_mask):
    """표면 불규칙도 계산 (표면 voxel 비율 %)"""
    total = int(np.sum(binary_mask))
    if total == 0:
        return 0.0
    eroded = ndimage.binary_erosion(binary_mask)
    surface = total - int(np.sum(eroded))
    return surface / total * 100


def smooth_tumor(data, kidney_label, tumor_label, zooms,
                 ct_data=None, sigma_mm=1.0, close_iter=3, open_iter=2):
    """
    종양 라벨 smoothing.
    종양 확장은 신장+종양 영역 내로만 제한.
    """
    # Step 0-pre: 신장/종양 중 intensity ≤ 0 삭제
    low_removed_kidney = 0
    low_removed_tumor = 0
    if ct_data is not None:
        data, low_removed_kidney, low_removed_tumor = remove_low_intensity_labels(
            data, ct_data, kidney_label, tumor_label, threshold=0
        )
        if low_removed_kidney > 0 or low_removed_tumor > 0:
            print(f"    [전처리] intensity ≤ 0 삭제: 신장 -{low_removed_kidney:,}, 종양 -{low_removed_tumor:,} voxels")

    # Step 0a: 고립 신장 component → 종양 재라벨링
    data, relabel_stats = relabel_isolated_kidney(data, kidney_label, tumor_label)
    if relabel_stats["relabeled_voxels"] > 0:
        print(f"    [전처리] 고립 신장 {relabel_stats['relabeled_count']}개 → 종양으로 재라벨링 (+{relabel_stats['relabeled_voxels']:,} voxels)")

    kidney_mask = (data == kidney_label)
    tumor_mask = (data == tumor_label)
    organ_mask = kidney_mask | tumor_mask

    before_tumor = int(np.sum(tumor_mask))

    if before_tumor == 0:
        return data.copy(), {"before": 0, "after": 0, "relabeled_voxels": 0,
                             "low_removed_kidney": 0, "low_removed_tumor": 0,
                             "volume_change_pct": 0, "surface_before_pct": 0,
                             "surface_after_pct": 0, "removed_components": 0,
                             "removed_voxels": 0}

    mask = tumor_mask.astype(np.float64)

    # Step 1: 가장 큰 connected component만 유지
    labeled, n_comp = ndimage.label(mask)
    removed_components = 0
    removed_voxels = 0
    if n_comp > 1:
        sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
        largest = np.argmax(sizes) + 1
        mask = (labeled == largest).astype(np.float64)
        removed_voxels = before_tumor - int(np.sum(mask))
        removed_components = n_comp - 1

    # Step 2: Morphological closing (빈 구멍 메움)
    struct = ndimage.generate_binary_structure(3, 1)
    if close_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=close_iter).astype(np.float64)

    # Step 3: Morphological opening (돌출부 제거)
    if open_iter > 0:
        mask = ndimage.binary_opening(mask, structure=struct, iterations=open_iter).astype(np.float64)

    # Step 4: Gaussian smoothing
    sigma_voxels = [sigma_mm / float(z) for z in zooms]
    smoothed = ndimage.gaussian_filter(mask, sigma=sigma_voxels)
    mask_final = (smoothed >= 0.5).astype(np.uint8)

    # Step 5: 신장+종양 영역 내로 제한
    mask_final = mask_final & organ_mask.astype(np.uint8)

    # 결과 조합
    result = data.copy()
    # 기존 종양 영역 → 신장으로 초기화
    result[tumor_mask] = kidney_label
    # smoothed 종양 영역 적용
    result[mask_final == 1] = tumor_label

    after_tumor = int(np.sum(result == tumor_label))
    after_kidney = int(np.sum(result == kidney_label))

    before_surface = surface_ratio(tumor_mask.astype(np.uint8))
    after_surface = surface_ratio((result == tumor_label).astype(np.uint8))

    stats = {
        "before": before_tumor,
        "after": after_tumor,
        "volume_change_pct": (after_tumor - before_tumor) / max(before_tumor, 1) * 100,
        "surface_before_pct": before_surface,
        "surface_after_pct": after_surface,
        "removed_components": removed_components,
        "removed_voxels": removed_voxels,
        "relabeled_voxels": relabel_stats["relabeled_voxels"],
        "low_removed_kidney": low_removed_kidney,
        "low_removed_tumor": low_removed_tumor,
    }

    return result, stats


def process_file(path, kidney_label, tumor_label, sigma_mm, close_iter, open_iter,
                 image_path, backup, output_dir):
    """단일 파일 후처리"""
    fname = os.path.basename(path)

    img = nib.load(path)
    data = np.round(np.asanyarray(img.dataobj)).astype(np.uint16)
    zooms = img.header.get_zooms()

    # CT 이미지 로드
    ct_path = image_path or find_ct_image(path)
    ct_data = None
    if ct_path and os.path.exists(ct_path):
        print(f"  CT image: {os.path.basename(ct_path)}")
        ct_img = nib.load(ct_path)
        ct_data = np.asanyarray(ct_img.dataobj).astype(np.float32)
    else:
        print(f"  CT image: not found")

    result, stats = smooth_tumor(
        data, kidney_label, tumor_label, zooms, ct_data,
        sigma_mm, close_iter, open_iter
    )

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
            print(f"  Backup: {backup_path}")

    # 저장
    new_header = img.header.copy()
    new_header.set_data_dtype(np.uint16)
    new_header["scl_slope"] = 1
    new_header["scl_inter"] = 0
    new_img = nib.Nifti1Image(result, img.affine, new_header)
    nib.save(new_img, out_path)

    # 결과 출력
    print(f"  {fname}:")
    if stats["before"] == 0:
        print(f"    Tumor label not found, skipped.")
        return

    if stats["low_removed_kidney"] > 0 or stats["low_removed_tumor"] > 0:
        print(f"    Low intensity: 신장 -{stats['low_removed_kidney']:,}, 종양 -{stats['low_removed_tumor']:,} voxels 삭제")
    if stats["relabeled_voxels"] > 0:
        print(f"    Relabeled: +{stats['relabeled_voxels']:,} voxels (고립 신장 → 종양)")
    print(f"    Voxels:  {stats['before']:>10,} -> {stats['after']:>10,} ({stats['volume_change_pct']:+.1f}%)")
    print(f"    Surface: {stats['surface_before_pct']:>9.1f}% -> {stats['surface_after_pct']:>9.1f}%")
    if stats["removed_components"] > 0:
        print(f"    Removed: {stats['removed_components']} isolated component(s), {stats['removed_voxels']:,} voxels")
    print(f"    Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="종양 라벨 후처리 (Smoothing)")
    parser.add_argument("files", nargs="+", help="NIfTI 파일 경로 (glob 패턴 지원)")
    parser.add_argument("--kidney-label", type=int, default=1, help="신장 라벨 번호 (기본: 1)")
    parser.add_argument("--tumor-label", type=int, default=2, help="종양 라벨 번호 (기본: 2)")
    parser.add_argument("--sigma", type=float, default=1.0, help="Gaussian sigma in mm (기본: 1.0)")
    parser.add_argument("--close-iter", type=int, default=3, help="Closing 반복 횟수 (기본: 3)")
    parser.add_argument("--open-iter", type=int, default=2, help="Opening 반복 횟수 (기본: 2)")
    parser.add_argument("--image", type=str, default=None, help="CT 이미지 경로 (생략 시 자동 매칭)")
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
    print(f"  tumor={args.tumor_label}, kidney={args.kidney_label}")
    print(f"  sigma={args.sigma}mm, closing={args.close_iter}, opening={args.open_iter}")
    print()

    for path in sorted(paths):
        process_file(
            path,
            kidney_label=args.kidney_label,
            tumor_label=args.tumor_label,
            sigma_mm=args.sigma,
            close_iter=args.close_iter,
            open_iter=args.open_iter,
            image_path=args.image,
            backup=not args.no_backup,
            output_dir=args.output_dir,
        )
    print()
    print("Done.")


if __name__ == "__main__":
    main()
