"""
신장+종양 통합 후처리: Intensity 확장 + Smoothing

방식:
    1. 신장(1) + 종양(2)을 하나의 장기 마스크로 합침
    2. 상위 N개 connected component 유지 (좌우 신장 보존, 고립 복셀 제거)
    3. CT intensity 기반 경계 확장 (덜 칠해진 부분 채움)
    4. Morphological closing/opening + Gaussian smoothing (경계 부드럽게)
    5. 종양 원위치 유지, 나머지 = 신장

사용법:
    python smooth_kidney_tumor.py S003/S003_Segmentation_A.nii.gz
    python smooth_kidney_tumor.py S003/S003_Segmentation_*.nii.gz --sigma 1.0

    CT 이미지는 파일명에서 자동 매칭:
      S003_Segmentation_A.nii.gz → S003_image_A.nii.gz

옵션:
    --kidney-label      : 신장 라벨 번호 (기본: 1)
    --tumor-label       : 종양 라벨 번호 (기본: 2)
    --sigma             : Gaussian smoothing sigma in mm (기본: 1.0)
    --close-iter        : Morphological closing 반복 횟수 (기본: 3)
    --open-iter         : Morphological opening 반복 횟수 (기본: 2)
    --keep-n            : 유지할 큰 component 수 (기본: 2, 좌우 신장)
    --expand-steps      : Intensity 기반 경계 확장 횟수 (기본: 5)
    --expand-threshold  : 확장 시 최소 intensity HU (기본: 120)
    --image             : CT 이미지 경로 (생략 시 자동 매칭)
    --no-backup         : 백업 생성 안 함
    --output-dir        : 출력 폴더 지정 (기본: 원본 파일 덮어쓰기)
"""

import os
import glob
import re
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


def expand_by_intensity(organ_mask, ct_data, threshold=120, steps=5):
    """
    Intensity 기반 경계 확장.
    현재 라벨 경계의 인접 빈 복셀 중 CT intensity >= threshold인 복셀을 채움.
    이를 steps회 반복.
    """
    struct = ndimage.generate_binary_structure(3, 1)
    mask = organ_mask.copy()
    total_added = 0

    for step in range(steps):
        dilated = ndimage.binary_dilation(mask, structure=struct).astype(np.uint8)
        candidates = (dilated == 1) & (mask == 0)
        accepted = candidates & (ct_data >= threshold)
        added = int(np.sum(accepted))
        total_added += added

        if added == 0:
            break

        mask[accepted] = 1
        print(f"      Step {step + 1}: +{added:,} voxels")

    return mask, total_added


def smooth_organ_mask(mask, zooms, sigma_mm, close_iter, open_iter):
    """단일 binary mask에 closing → opening → gaussian smoothing 적용."""
    struct = ndimage.generate_binary_structure(3, 1)

    if close_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=close_iter).astype(np.float64)

    if open_iter > 0:
        mask = ndimage.binary_opening(mask, structure=struct, iterations=open_iter).astype(np.float64)

    sigma_voxels = [sigma_mm / float(z) for z in zooms]
    smoothed = ndimage.gaussian_filter(mask.astype(np.float64), sigma=sigma_voxels)
    return (smoothed >= 0.5).astype(np.uint8)


def surface_ratio(binary_mask):
    """표면 불규칙도 계산 (표면 voxel 비율 %)"""
    total = int(np.sum(binary_mask))
    if total == 0:
        return 0.0
    eroded = ndimage.binary_erosion(binary_mask)
    surface = total - int(np.sum(eroded))
    return surface / total * 100


def smooth_kidney_tumor(data, kidney_label, tumor_label, zooms,
                        ct_data=None, sigma_mm=1.0, close_iter=3, open_iter=2,
                        keep_n=2, expand_steps=5, expand_threshold=120):
    """신장+종양 통합 smoothing."""
    kidney_mask = (data == kidney_label)
    tumor_mask = (data == tumor_label)

    before_kidney = int(np.sum(kidney_mask))
    before_tumor = int(np.sum(tumor_mask))

    # Step 1: 신장 + 종양 → 하나의 장기 마스크
    organ_mask = (kidney_mask | tumor_mask).astype(np.uint8)
    organ_total = int(np.sum(organ_mask))

    if organ_total == 0:
        return data.copy(), {"before_kidney": 0, "before_tumor": 0,
                             "after_kidney": 0, "after_tumor": 0,
                             "expand_added": 0, "components_found": 0,
                             "components_removed": 0, "removed_voxels": 0}

    # Step 2: 상위 keep_n개 component 유지
    labeled, n_comp = ndimage.label(organ_mask)
    removed_components = 0
    removed_voxels = 0

    if n_comp > keep_n:
        sizes = ndimage.sum(organ_mask, labeled, range(1, n_comp + 1))
        top_indices = np.argsort(sizes)[::-1][:keep_n]
        top_labels = set(top_indices + 1)
        new_mask = np.zeros_like(organ_mask)
        for lbl in top_labels:
            new_mask[labeled == lbl] = 1
        removed_voxels = organ_total - int(np.sum(new_mask))
        removed_components = n_comp - keep_n
        organ_mask = new_mask.astype(np.uint8)
        labeled, n_comp = ndimage.label(organ_mask)

    # Step 3: Intensity 기반 경계 확장
    expand_added = 0
    if ct_data is not None and expand_steps > 0:
        print(f"    [Intensity 확장] threshold={expand_threshold} HU, steps={expand_steps}")
        organ_mask, expand_added = expand_by_intensity(
            organ_mask, ct_data, threshold=expand_threshold, steps=expand_steps
        )
        print(f"      총 추가: {expand_added:,} voxels")
        labeled, n_comp = ndimage.label(organ_mask)
    elif ct_data is None:
        print(f"    [Intensity 확장] CT 이미지 없음 — 건너뜀")

    # Step 4: 각 component별 개별 smoothing
    smoothed_organ = np.zeros_like(organ_mask, dtype=np.uint8)
    for i in range(1, n_comp + 1):
        comp_mask = (labeled == i).astype(np.float64)
        comp_smoothed = smooth_organ_mask(comp_mask, zooms, sigma_mm, close_iter, open_iter)
        smoothed_organ = np.maximum(smoothed_organ, comp_smoothed)

    # Step 5: 종양 원위치 유지, 나머지 = 신장
    result = data.copy()
    result[kidney_mask] = 0
    result[tumor_mask] = 0

    final_tumor = tumor_mask & (smoothed_organ == 1)
    final_kidney = (smoothed_organ == 1) & ~final_tumor

    result[final_kidney] = kidney_label
    result[final_tumor] = tumor_label

    after_kidney = int(np.sum(result == kidney_label))
    after_tumor = int(np.sum(result == tumor_label))

    before_organ_surface = surface_ratio((kidney_mask | tumor_mask).astype(np.uint8))
    after_organ_surface = surface_ratio((smoothed_organ == 1).astype(np.uint8))
    before_kidney_surface = surface_ratio(kidney_mask.astype(np.uint8))
    after_kidney_surface = surface_ratio(final_kidney.astype(np.uint8))

    stats = {
        "before_kidney": before_kidney,
        "before_tumor": before_tumor,
        "after_kidney": after_kidney,
        "after_tumor": after_tumor,
        "kidney_change_pct": (after_kidney - before_kidney) / max(before_kidney, 1) * 100,
        "tumor_change_pct": (after_tumor - before_tumor) / max(before_tumor, 1) * 100,
        "organ_surface_before_pct": before_organ_surface,
        "organ_surface_after_pct": after_organ_surface,
        "kidney_surface_before_pct": before_kidney_surface,
        "kidney_surface_after_pct": after_kidney_surface,
        "components_found": n_comp + removed_components,
        "components_removed": removed_components,
        "removed_voxels": removed_voxels,
        "expand_added": expand_added,
    }

    return result, stats


def process_file(path, kidney_label, tumor_label, sigma_mm, close_iter, open_iter,
                 keep_n, expand_steps, expand_threshold, image_path, backup, output_dir):
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
        print(f"  CT image: not found (intensity expansion disabled)")

    result, stats = smooth_kidney_tumor(
        data, kidney_label, tumor_label, zooms, ct_data,
        sigma_mm, close_iter, open_iter, keep_n, expand_steps, expand_threshold
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
    if stats["before_kidney"] == 0 and stats["before_tumor"] == 0:
        print(f"    Kidney/tumor labels not found, skipped.")
        return

    print(f"    [장기 외곽]")
    print(f"      Surface: {stats['organ_surface_before_pct']:.1f}% -> {stats['organ_surface_after_pct']:.1f}%")
    print(f"    [신장 label {kidney_label}]")
    print(f"      Voxels:  {stats['before_kidney']:>10,} -> {stats['after_kidney']:>10,} ({stats['kidney_change_pct']:+.1f}%)")
    print(f"      Surface: {stats['kidney_surface_before_pct']:.1f}% -> {stats['kidney_surface_after_pct']:.1f}%")
    print(f"    [종양 label {tumor_label}]")
    print(f"      Voxels:  {stats['before_tumor']:>10,} -> {stats['after_tumor']:>10,} ({stats['tumor_change_pct']:+.1f}%)")
    if stats["expand_added"] > 0:
        print(f"    [Intensity 확장] +{stats['expand_added']:,} voxels 추가됨")
    if stats["components_removed"] > 0:
        print(f"    Removed: {stats['components_removed']} isolated component(s), {stats['removed_voxels']:,} voxels")
    print(f"    Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="신장+종양 통합 후처리: Intensity 확장 + Smoothing")
    parser.add_argument("files", nargs="+", help="NIfTI 파일 경로 (glob 패턴 지원)")
    parser.add_argument("--kidney-label", type=int, default=1, help="신장 라벨 번호 (기본: 1)")
    parser.add_argument("--tumor-label", type=int, default=2, help="종양 라벨 번호 (기본: 2)")
    parser.add_argument("--sigma", type=float, default=1.0, help="Gaussian sigma in mm (기본: 1.0)")
    parser.add_argument("--close-iter", type=int, default=3, help="Closing 반복 횟수 (기본: 3)")
    parser.add_argument("--open-iter", type=int, default=2, help="Opening 반복 횟수 (기본: 2)")
    parser.add_argument("--keep-n", type=int, default=2, help="유지할 큰 component 수 (기본: 2, 좌우 신장)")
    parser.add_argument("--expand-steps", type=int, default=5, help="Intensity 경계 확장 횟수 (기본: 5)")
    parser.add_argument("--expand-threshold", type=float, default=120, help="확장 시 최소 intensity HU (기본: 120)")
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
    print(f"  kidney={args.kidney_label}, tumor={args.tumor_label}, keep_n={args.keep_n}")
    print(f"  sigma={args.sigma}mm, closing={args.close_iter}, opening={args.open_iter}")
    print(f"  expand: {args.expand_steps} steps, threshold={args.expand_threshold} HU")
    print()

    for path in sorted(paths):
        process_file(
            path,
            kidney_label=args.kidney_label,
            tumor_label=args.tumor_label,
            sigma_mm=args.sigma,
            close_iter=args.close_iter,
            open_iter=args.open_iter,
            keep_n=args.keep_n,
            expand_steps=args.expand_steps,
            expand_threshold=args.expand_threshold,
            image_path=args.image,
            backup=not args.no_backup,
            output_dir=args.output_dir,
        )
    print()
    print("Done.")


if __name__ == "__main__":
    main()
