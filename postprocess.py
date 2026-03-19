"""
신장+종양 세그멘테이션 통합 후처리 스크립트

처리 파이프라인:
    Step 1. 저강도 라벨 삭제
            - 신장(1)/종양(2) 라벨 중 CT intensity ≤ 0 HU인 복셀을 배경(0)으로 삭제
            - 공기/노이즈 영역 제거

    Step 2. 종양 smoothing
            - 가장 큰 connected component만 유지 (고립 복셀 제거)
            - Morphological closing (울퉁불퉁한 사이 채움)
            - Morphological opening (튀어나온 부분 제거)
            - Gaussian smoothing + threshold (경계면 부드럽게)
            - 종양이 신장+종양 영역 밖으로 확장되지 않도록 제한

    Step 3. 신장 외부 경계 smoothing
            - 종양 라벨은 그대로 유지
            - 신장+종양을 하나의 장기 마스크로 합침
            - 상위 2개 component 유지 (좌우 신장 보존)
            - 각 component별 closing → opening → Gaussian smoothing
            - Smoothed 장기 마스크에서 종양 영역 빼기 = 신장

사용법:
    python postprocess.py S003/S003_Segmentation_A.nii.gz
    python postprocess.py S004/S004_segmentation_*.nii.gz --sigma 1.0

    CT 이미지는 파일명에서 자동 매칭:
      S003_Segmentation_A.nii.gz → S003_image_A.nii.gz
      S004_segmentation_A.nii.gz → S004_image_A.nii.gz

옵션:
    --kidney-label      : 신장 라벨 번호 (기본: 1)
    --tumor-label       : 종양 라벨 번호 (기본: 2)
    --tumor-sigma       : 종양 Gaussian sigma in mm (기본: 1.0)
    --tumor-close-iter  : 종양 closing 반복 횟수 (기본: 3)
    --tumor-open-iter   : 종양 opening 반복 횟수 (기본: 2)
    --kidney-sigma      : 신장 Gaussian sigma in mm (기본: 1.0)
    --kidney-close-iter : 신장 closing 반복 횟수 (기본: 3)
    --kidney-open-iter  : 신장 opening 반복 횟수 (기본: 2)
    --keep-n            : 유지할 큰 component 수 (기본: 2, 좌우 신장)
    --image             : CT 이미지 경로 (생략 시 자동 매칭)
    --no-backup         : 백업 생성 안 함
    --output-dir        : 출력 폴더 지정 (기본: 원본 파일 덮어쓰기)
"""

import os
import re
import glob
import shutil
import argparse
import nibabel as nib
import numpy as np
from scipy import ndimage


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────

def find_ct_image(seg_path):
    """세그멘테이션 파일에서 CT 이미지 경로 자동 매칭."""
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


def surface_ratio(binary_mask):
    """표면 불규칙도 계산 (표면 voxel 비율 %)"""
    total = int(np.sum(binary_mask))
    if total == 0:
        return 0.0
    eroded = ndimage.binary_erosion(binary_mask)
    surface = total - int(np.sum(eroded))
    return surface / total * 100


# ──────────────────────────────────────────────
# Step 1: 저강도 라벨 삭제
# ──────────────────────────────────────────────

def step1_remove_low_intensity(data, ct_data, kidney_label, tumor_label, threshold=0):
    """신장/종양 라벨 중 intensity ≤ threshold인 복셀을 배경(0)으로 삭제."""
    low = (ct_data <= threshold)
    kidney_low = (data == kidney_label) & low
    tumor_low = (data == tumor_label) & low

    removed_kidney = int(np.sum(kidney_low))
    removed_tumor = int(np.sum(tumor_low))

    result = data.copy()
    result[kidney_low] = 0
    result[tumor_low] = 0
    return result, removed_kidney, removed_tumor


# ──────────────────────────────────────────────
# Step 2: 종양 smoothing
# ──────────────────────────────────────────────

def step2_smooth_tumor(data, kidney_label, tumor_label, zooms,
                       sigma_mm=1.0, close_iter=3, open_iter=2):
    """종양 라벨 smoothing. 신장+종양 영역 내로 제한."""
    kidney_mask = (data == kidney_label)
    tumor_mask = (data == tumor_label)
    organ_mask = kidney_mask | tumor_mask

    before_tumor = int(np.sum(tumor_mask))
    if before_tumor == 0:
        return data.copy(), {}

    mask = tumor_mask.astype(np.float64)

    # 가장 큰 connected component만 유지
    labeled, n_comp = ndimage.label(mask)
    removed_components = 0
    removed_voxels = 0
    if n_comp > 1:
        sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
        largest = np.argmax(sizes) + 1
        mask = (labeled == largest).astype(np.float64)
        removed_voxels = before_tumor - int(np.sum(mask))
        removed_components = n_comp - 1

    # Morphological closing
    struct = ndimage.generate_binary_structure(3, 1)
    if close_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=close_iter).astype(np.float64)

    # Morphological opening
    if open_iter > 0:
        mask = ndimage.binary_opening(mask, structure=struct, iterations=open_iter).astype(np.float64)

    # Gaussian smoothing
    sigma_voxels = [sigma_mm / float(z) for z in zooms]
    smoothed = ndimage.gaussian_filter(mask, sigma=sigma_voxels)
    mask_final = (smoothed >= 0.5).astype(np.uint8)

    # 신장+종양 영역 내로 제한
    mask_final = mask_final & organ_mask.astype(np.uint8)

    # 결과 조합
    result = data.copy()
    result[tumor_mask] = kidney_label  # 기존 종양 → 신장으로 초기화
    result[mask_final == 1] = tumor_label  # smoothed 종양 적용

    after_tumor = int(np.sum(result == tumor_label))
    before_surface = surface_ratio(tumor_mask.astype(np.uint8))
    after_surface = surface_ratio((result == tumor_label).astype(np.uint8))

    stats = {
        "before": before_tumor,
        "after": after_tumor,
        "change_pct": (after_tumor - before_tumor) / max(before_tumor, 1) * 100,
        "surface_before": before_surface,
        "surface_after": after_surface,
        "removed_components": removed_components,
        "removed_voxels": removed_voxels,
    }
    return result, stats


# ──────────────────────────────────────────────
# Step 3: 신장 외부 경계 smoothing
# ──────────────────────────────────────────────

def step3_smooth_kidney(data, kidney_label, tumor_label, zooms,
                        sigma_mm=1.0, close_iter=3, open_iter=2, keep_n=2):
    """
    종양은 그대로 두고 신장+종양 장기 외곽을 smooth한 뒤,
    종양 영역을 빼서 신장 라벨을 재구성.
    """
    kidney_mask = (data == kidney_label)
    tumor_mask = (data == tumor_label)

    before_kidney = int(np.sum(kidney_mask))
    if before_kidney == 0:
        return data.copy(), {}

    # 신장 + 종양 → 장기 마스크
    organ_mask = (kidney_mask | tumor_mask).astype(np.uint8)
    organ_total = int(np.sum(organ_mask))

    # 상위 keep_n개 component 유지
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

    # 각 component별 개별 smoothing
    struct = ndimage.generate_binary_structure(3, 1)
    smoothed_organ = np.zeros_like(organ_mask, dtype=np.uint8)

    for i in range(1, n_comp + 1):
        comp_mask = (labeled == i).astype(np.float64)

        if close_iter > 0:
            comp_mask = ndimage.binary_closing(comp_mask, structure=struct, iterations=close_iter).astype(np.float64)
        if open_iter > 0:
            comp_mask = ndimage.binary_opening(comp_mask, structure=struct, iterations=open_iter).astype(np.float64)

        sigma_voxels = [sigma_mm / float(z) for z in zooms]
        comp_smoothed = ndimage.gaussian_filter(comp_mask, sigma=sigma_voxels)
        comp_final = (comp_smoothed >= 0.5).astype(np.uint8)
        smoothed_organ = np.maximum(smoothed_organ, comp_final)

    # 종양 원위치 유지, 나머지 = 신장
    result = data.copy()
    result[kidney_mask] = 0  # 기존 신장 제거
    result[tumor_mask] = 0   # 기존 종양 제거

    final_tumor = tumor_mask & (smoothed_organ == 1)
    final_kidney = (smoothed_organ == 1) & ~final_tumor

    result[final_kidney] = kidney_label
    result[final_tumor] = tumor_label

    after_kidney = int(np.sum(result == kidney_label))

    before_organ_surface = surface_ratio((kidney_mask | tumor_mask).astype(np.uint8))
    after_organ_surface = surface_ratio((smoothed_organ == 1).astype(np.uint8))

    stats = {
        "before": before_kidney,
        "after": after_kidney,
        "change_pct": (after_kidney - before_kidney) / max(before_kidney, 1) * 100,
        "organ_surface_before": before_organ_surface,
        "organ_surface_after": after_organ_surface,
        "removed_components": removed_components,
        "removed_voxels": removed_voxels,
    }
    return result, stats


# ──────────────────────────────────────────────
# 메인 처리
# ──────────────────────────────────────────────

def process_file(path, kidney_label, tumor_label,
                 tumor_sigma, tumor_close, tumor_open,
                 kidney_sigma, kidney_close, kidney_open,
                 keep_n, image_path, backup, output_dir):
    """단일 파일 후처리"""
    fname = os.path.basename(path)
    print(f"\n{'='*60}")
    print(f"  {fname}")
    print(f"{'='*60}")

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

    # ── Step 1: 저강도 라벨 삭제 ──
    print(f"\n  [Step 1] 저강도 라벨 삭제 (intensity ≤ 0 HU)")
    if ct_data is not None:
        data, rm_kidney, rm_tumor = step1_remove_low_intensity(
            data, ct_data, kidney_label, tumor_label
        )
        print(f"    신장: -{rm_kidney:,} voxels")
        print(f"    종양: -{rm_tumor:,} voxels")
    else:
        print(f"    CT 이미지 없음 — 건너뜀")

    # ── Step 2: 종양 smoothing ──
    print(f"\n  [Step 2] 종양 smoothing (sigma={tumor_sigma}, close={tumor_close}, open={tumor_open})")
    data, t_stats = step2_smooth_tumor(
        data, kidney_label, tumor_label, zooms,
        sigma_mm=tumor_sigma, close_iter=tumor_close, open_iter=tumor_open
    )
    if t_stats:
        print(f"    Voxels:  {t_stats['before']:>10,} -> {t_stats['after']:>10,} ({t_stats['change_pct']:+.1f}%)")
        print(f"    Surface: {t_stats['surface_before']:.1f}% -> {t_stats['surface_after']:.1f}%")
        if t_stats["removed_components"] > 0:
            print(f"    고립 제거: {t_stats['removed_components']}개, {t_stats['removed_voxels']:,} voxels")
    else:
        print(f"    종양 라벨 없음 — 건너뜀")

    # ── Step 3: 신장 외부 경계 smoothing ──
    print(f"\n  [Step 3] 신장 외곽 smoothing (sigma={kidney_sigma}, close={kidney_close}, open={kidney_open})")
    data, k_stats = step3_smooth_kidney(
        data, kidney_label, tumor_label, zooms,
        sigma_mm=kidney_sigma, close_iter=kidney_close, open_iter=kidney_open, keep_n=keep_n
    )
    if k_stats:
        print(f"    Voxels:  {k_stats['before']:>10,} -> {k_stats['after']:>10,} ({k_stats['change_pct']:+.1f}%)")
        print(f"    장기 외곽 Surface: {k_stats['organ_surface_before']:.1f}% -> {k_stats['organ_surface_after']:.1f}%")
        if k_stats["removed_components"] > 0:
            print(f"    고립 제거: {k_stats['removed_components']}개, {k_stats['removed_voxels']:,} voxels")
    else:
        print(f"    신장 라벨 없음 — 건너뜀")

    # ── 저장 ──
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, fname)
    else:
        out_path = path

    if backup and out_path == path:
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "backup_original")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, fname)
        if not os.path.exists(backup_path):
            shutil.copy2(path, backup_path)
            print(f"\n  Backup: {backup_path}")

    new_header = img.header.copy()
    new_header.set_data_dtype(np.uint16)
    new_header["scl_slope"] = 1
    new_header["scl_inter"] = 0
    new_img = nib.Nifti1Image(data, img.affine, new_header)
    nib.save(new_img, out_path)
    print(f"\n  Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="신장+종양 세그멘테이션 통합 후처리")
    parser.add_argument("files", nargs="+", help="NIfTI 파일 경로 (glob 패턴 지원)")
    parser.add_argument("--kidney-label", type=int, default=1, help="신장 라벨 번호 (기본: 1)")
    parser.add_argument("--tumor-label", type=int, default=2, help="종양 라벨 번호 (기본: 2)")
    parser.add_argument("--tumor-sigma", type=float, default=1.0, help="종양 Gaussian sigma mm (기본: 1.0)")
    parser.add_argument("--tumor-close-iter", type=int, default=3, help="종양 closing 반복 (기본: 3)")
    parser.add_argument("--tumor-open-iter", type=int, default=2, help="종양 opening 반복 (기본: 2)")
    parser.add_argument("--kidney-sigma", type=float, default=1.0, help="신장 Gaussian sigma mm (기본: 1.0)")
    parser.add_argument("--kidney-close-iter", type=int, default=3, help="신장 closing 반복 (기본: 3)")
    parser.add_argument("--kidney-open-iter", type=int, default=2, help="신장 opening 반복 (기본: 2)")
    parser.add_argument("--keep-n", type=int, default=2, help="유지할 큰 component 수 (기본: 2)")
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
    print(f"  종양: sigma={args.tumor_sigma}, close={args.tumor_close_iter}, open={args.tumor_open_iter}")
    print(f"  신장: sigma={args.kidney_sigma}, close={args.kidney_close_iter}, open={args.kidney_open_iter}")

    for path in sorted(paths):
        process_file(
            path,
            kidney_label=args.kidney_label,
            tumor_label=args.tumor_label,
            tumor_sigma=args.tumor_sigma,
            tumor_close=args.tumor_close_iter,
            tumor_open=args.tumor_open_iter,
            kidney_sigma=args.kidney_sigma,
            kidney_close=args.kidney_close_iter,
            kidney_open=args.kidney_open_iter,
            keep_n=args.keep_n,
            image_path=args.image,
            backup=not args.no_backup,
            output_dir=args.output_dir,
        )

    print(f"\n{'='*60}")
    print("Done.")


if __name__ == "__main__":
    main()
