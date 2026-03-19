"""
세그멘테이션 라벨 후처리 (Smoothing) 스크립트

사용법:
    python smooth_segmentation.py <nii.gz 파일 경로> [옵션]
    python smooth_segmentation.py S003/S003_Segmentation_A.nii.gz
    python smooth_segmentation.py S003/*.nii.gz --target-label 2 --sigma 1.0

옵션:
    --target-label  : 후처리할 라벨 번호 (기본: 2)
    --sigma         : Gaussian smoothing sigma in mm (기본: 1.0)
    --close-iter    : Morphological closing 반복 횟수 (기본: 3)
    --open-iter     : Morphological opening 반복 횟수 (기본: 2)
    --no-backup     : 백업 생성 안 함
    --output-dir    : 출력 폴더 지정 (기본: 원본 파일 덮어쓰기)

처리 파이프라인:
    1. 가장 큰 connected component만 유지 (고립 voxel 제거)
    2. Morphological closing (작은 구멍/파인 부분 메움)
    3. Morphological opening (작은 돌출부 제거)
    4. Gaussian smoothing + threshold (경계 부드럽게, 비등방성 voxel 보정)
"""

import sys
import os
import glob
import shutil
import argparse
import nibabel as nib
import numpy as np
from scipy import ndimage


def smooth_label(data, target_label, zooms, sigma_mm=1.0, close_iter=3, open_iter=2):
    """
    특정 라벨에 대해 smoothing 후처리를 수행한다.

    Parameters
    ----------
    data : np.ndarray (uint16)
        전체 세그멘테이션 볼륨
    target_label : int
        후처리할 라벨 번호
    zooms : tuple
        voxel spacing (mm)
    sigma_mm : float
        Gaussian smoothing sigma (mm 단위, 각 축에 비등방성 보정 적용)
    close_iter : int
        Morphological closing 반복 횟수
    open_iter : int
        Morphological opening 반복 횟수

    Returns
    -------
    result : np.ndarray (uint16)
        후처리된 세그멘테이션 볼륨
    stats : dict
        처리 전후 통계
    """
    mask = (data == target_label).astype(np.float64)
    before_count = int(np.sum(mask))

    if before_count == 0:
        return data.copy(), {"before": 0, "after": 0, "removed_components": 0}

    # Step 1: 가장 큰 connected component만 유지
    labeled, n_comp = ndimage.label(mask)
    removed_voxels = 0
    if n_comp > 1:
        sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
        largest = np.argmax(sizes) + 1
        mask = (labeled == largest).astype(np.float64)
        removed_voxels = before_count - int(np.sum(mask))

    # Step 2: Morphological closing (구멍 메우기)
    struct = ndimage.generate_binary_structure(3, 1)
    if close_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=close_iter).astype(np.float64)

    # Step 3: Morphological opening (돌출부 제거)
    if open_iter > 0:
        mask = ndimage.binary_opening(mask, structure=struct, iterations=open_iter).astype(np.float64)

    # Step 4: Gaussian smoothing (비등방성 보정)
    sigma_voxels = [sigma_mm / float(z) for z in zooms]
    smoothed = ndimage.gaussian_filter(mask, sigma=sigma_voxels)
    mask_final = (smoothed >= 0.5).astype(np.uint16)

    # 결과 조합
    result = data.copy()
    result[data == target_label] = 0
    result[mask_final == 1] = target_label

    after_count = int(np.sum(result == target_label))

    # 표면 불규칙도 계산
    def surface_ratio(binary_mask):
        if np.sum(binary_mask) == 0:
            return 0.0
        eroded = ndimage.binary_erosion(binary_mask)
        surface = int(np.sum(binary_mask)) - int(np.sum(eroded))
        return surface / int(np.sum(binary_mask)) * 100

    before_surface = surface_ratio((data == target_label).astype(np.uint8))
    after_surface = surface_ratio((result == target_label).astype(np.uint8))

    stats = {
        "before": before_count,
        "after": after_count,
        "volume_change_pct": (after_count - before_count) / max(before_count, 1) * 100,
        "removed_components": n_comp - 1,
        "removed_voxels": removed_voxels,
        "surface_before_pct": before_surface,
        "surface_after_pct": after_surface,
    }

    return result, stats


def process_file(path, target_label, sigma_mm, close_iter, open_iter, backup, output_dir):
    """단일 파일 후처리"""
    fname = os.path.basename(path)

    # 로드
    img = nib.load(path)
    data = np.round(np.asanyarray(img.dataobj)).astype(np.uint16)
    zooms = img.header.get_zooms()

    # 후처리
    result, stats = smooth_label(data, target_label, zooms, sigma_mm, close_iter, open_iter)

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
        print(f"    Label {target_label} not found, skipped.")
        return

    print(f"    Voxels:  {stats['before']:>10,} -> {stats['after']:>10,} ({stats['volume_change_pct']:+.1f}%)")
    print(f"    Surface: {stats['surface_before_pct']:>9.1f}% -> {stats['surface_after_pct']:>9.1f}%")
    if stats["removed_components"] > 0:
        print(f"    Removed: {stats['removed_components']} isolated component(s), {stats['removed_voxels']} voxels")
    print(f"    Saved:   {out_path}")


def main():
    parser = argparse.ArgumentParser(description="세그멘테이션 라벨 후처리 (Smoothing)")
    parser.add_argument("files", nargs="+", help="NIfTI 파일 경로 (glob 패턴 지원)")
    parser.add_argument("--target-label", type=int, default=2, help="후처리할 라벨 번호 (기본: 2)")
    parser.add_argument("--sigma", type=float, default=1.0, help="Gaussian sigma in mm (기본: 1.0)")
    parser.add_argument("--close-iter", type=int, default=3, help="Closing 반복 횟수 (기본: 3)")
    parser.add_argument("--open-iter", type=int, default=2, help="Opening 반복 횟수 (기본: 2)")
    parser.add_argument("--no-backup", action="store_true", help="백업 생성 안 함")
    parser.add_argument("--output-dir", type=str, default=None, help="출력 폴더 (기본: 원본 덮어쓰기)")
    args = parser.parse_args()

    # glob 패턴 확장
    paths = []
    for pattern in args.files:
        expanded = glob.glob(pattern)
        if expanded:
            paths.extend(expanded)
        else:
            paths.append(pattern)

    print(f"Processing {len(paths)} file(s), target label={args.target_label}, "
          f"sigma={args.sigma}mm, closing={args.close_iter}, opening={args.open_iter}")
    print()

    for path in sorted(paths):
        process_file(
            path,
            target_label=args.target_label,
            sigma_mm=args.sigma,
            close_iter=args.close_iter,
            open_iter=args.open_iter,
            backup=not args.no_backup,
            output_dir=args.output_dir,
        )
    print()
    print("Done.")


if __name__ == "__main__":
    main()
