"""
세그멘테이션 후처리 대화형 도구

사용법:
    python segtools.py S004

    케이스 폴더를 지정하면 phase 선택 → 기능 선택 → 실행 → 반복
"""

import os
import sys
import re
import glob
import shutil
import nibabel as nib
import numpy as np
from scipy import ndimage


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────

def surface_ratio(binary_mask):
    total = int(np.sum(binary_mask))
    if total == 0:
        return 0.0
    eroded = ndimage.binary_erosion(binary_mask)
    surface = total - int(np.sum(eroded))
    return surface / total * 100


def load_case(case_dir):
    """케이스 폴더에서 phase별 파일 경로 매칭."""
    case_name = os.path.basename(case_dir)
    phases = {}
    for phase in ["A", "D", "P"]:
        # 대소문자 둘 다 시도
        for fmt in [f"{case_name}_Segmentation_{phase}.nii.gz",
                    f"{case_name}_segmentation_{phase}.nii.gz"]:
            seg_path = os.path.join(case_dir, fmt)
            if os.path.exists(seg_path):
                img_path = os.path.join(case_dir, f"{case_name}_image_{phase}.nii.gz")
                phases[phase] = {
                    "seg": seg_path,
                    "img": img_path if os.path.exists(img_path) else None,
                }
                break
    return phases


def backup_file(path):
    """백업 생성."""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "backup_original")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, os.path.basename(path))
    if not os.path.exists(backup_path):
        shutil.copy2(path, backup_path)
        print(f"  Backup: {backup_path}")


def save_result(path, data, img):
    """결과 저장."""
    new_header = img.header.copy()
    new_header.set_data_dtype(np.uint16)
    new_header["scl_slope"] = 1
    new_header["scl_inter"] = 0
    new_img = nib.Nifti1Image(data, img.affine, new_header)
    nib.save(new_img, path)
    print(f"  저장 완료: {path}")


# phase별 롤백 히스토리 {phase: [(data, description), ...]}
rollback_history = {}


def print_label_info(data, ct_data=None):
    """현재 라벨 상태 출력."""
    labels = np.unique(data)
    print(f"\n  현재 라벨 상태:")
    for label in labels:
        count = int(np.sum(data == label))
        name = {0: "배경", 1: "신장", 2: "종양"}.get(int(label), f"라벨{label}")
        info = f"    {name}(label {int(label)}): {count:>12,} voxels"
        if ct_data is not None and label > 0:
            vals = ct_data[data == label]
            info += f"  | intensity: {np.mean(vals):.0f} ± {np.std(vals):.0f} HU"
        print(info)
    print()


# ──────────────────────────────────────────────
# 기능 1: 고립 복셀 제거
# ──────────────────────────────────────────────

def func_remove_isolated(data, **kwargs):
    """고립 복셀 제거 (신장/종양 선택)"""
    target = input_choice("  대상 선택", ["1: 신장(label 1)", "2: 종양(label 2)", "3: 둘 다"])
    keep_n_map = {"1": (1, 2), "2": (2, 1), "3": None}

    if target == "3":
        # 신장 먼저
        data = _remove_isolated_label(data, label=1, keep_n=2)
        data = _remove_isolated_label(data, label=2, keep_n=1)
    elif target == "1":
        data = _remove_isolated_label(data, label=1, keep_n=2)
    elif target == "2":
        data = _remove_isolated_label(data, label=2, keep_n=1)

    return data


def _remove_isolated_label(data, label, keep_n):
    """특정 라벨의 상위 N개 component만 유지."""
    name = {1: "신장", 2: "종양"}.get(label, f"label{label}")
    mask = (data == label)
    total = int(np.sum(mask))
    if total == 0:
        print(f"  {name}: 라벨 없음")
        return data

    labeled, n_comp = ndimage.label(mask)
    if n_comp <= keep_n:
        print(f"  {name}: {n_comp}개 component — 제거 대상 없음")
        return data

    sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
    top_indices = np.argsort(sizes)[::-1][:keep_n]
    top_labels = set(top_indices + 1)

    result = data.copy()
    removed = 0
    for i in range(1, n_comp + 1):
        if i not in top_labels:
            comp_mask = (labeled == i)
            removed += int(np.sum(comp_mask))
            result[comp_mask] = 0

    print(f"  {name}: {n_comp}개 중 상위 {keep_n}개 유지, {n_comp - keep_n}개 제거 ({removed:,} voxels)")
    return result


# ──────────────────────────────────────────────
# 기능 2: 저강도 제거 (intensity ≤ 0)
# ──────────────────────────────────────────────

def func_remove_low_intensity(data, ct_data=None, **kwargs):
    """intensity ≤ 0인 신장/종양 복셀 삭제."""
    if ct_data is None:
        print("  CT 이미지 없음 — 실행 불가")
        return data

    low = (ct_data <= 0)
    result = data.copy()

    for label, name in [(1, "신장"), (2, "종양")]:
        mask = (data == label) & low
        removed = int(np.sum(mask))
        result[mask] = 0
        if removed > 0:
            print(f"  {name}: -{removed:,} voxels (intensity ≤ 0)")
        else:
            print(f"  {name}: 해당 없음")

    return result


# ──────────────────────────────────────────────
# 기능 3: 고강도 제거 (intensity ≥ 400)
# ──────────────────────────────────────────────

def func_remove_high_intensity(data, ct_data=None, **kwargs):
    """intensity ≥ 400인 신장/종양 복셀 삭제."""
    if ct_data is None:
        print("  CT 이미지 없음 — 실행 불가")
        return data

    threshold = input_int("  Threshold (기본 400)", default=400)
    high = (ct_data >= threshold)
    result = data.copy()

    for label, name in [(1, "신장"), (2, "종양")]:
        mask = (data == label) & high
        removed = int(np.sum(mask))
        result[mask] = 0
        if removed > 0:
            print(f"  {name}: -{removed:,} voxels (intensity ≥ {threshold})")
        else:
            print(f"  {name}: 해당 없음")

    return result


# ──────────────────────────────────────────────
# 기능 4: 종양 smoothing
# ──────────────────────────────────────────────

def func_smooth_tumor(data, zooms=None, **kwargs):
    """종양 라벨 smoothing."""
    kidney_mask = (data == 1)
    tumor_mask = (data == 2)
    organ_mask = kidney_mask | tumor_mask
    before = int(np.sum(tumor_mask))

    if before == 0:
        print("  종양 라벨 없음")
        return data

    sigma = input_float("  Gaussian sigma mm (기본 1.0)", default=1.0)
    close_iter = input_int("  Closing 반복 (기본 3)", default=3)
    open_iter = input_int("  Opening 반복 (기본 2)", default=2)

    mask = tumor_mask.astype(np.float64)

    # 가장 큰 component만 유지
    labeled, n_comp = ndimage.label(mask)
    if n_comp > 1:
        sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
        largest = np.argmax(sizes) + 1
        mask = (labeled == largest).astype(np.float64)
        print(f"  고립 제거: {n_comp - 1}개 component 삭제")

    struct = ndimage.generate_binary_structure(3, 1)
    if close_iter > 0:
        mask = ndimage.binary_closing(mask, structure=struct, iterations=close_iter).astype(np.float64)
    if open_iter > 0:
        mask = ndimage.binary_opening(mask, structure=struct, iterations=open_iter).astype(np.float64)

    sigma_voxels = [sigma / float(z) for z in zooms]
    smoothed = ndimage.gaussian_filter(mask, sigma=sigma_voxels)
    mask_final = (smoothed >= 0.5).astype(np.uint8)
    mask_final = mask_final & organ_mask.astype(np.uint8)

    result = data.copy()
    result[tumor_mask] = 1  # 기존 종양 → 신장
    result[mask_final == 1] = 2  # smoothed 종양

    after = int(np.sum(result == 2))
    before_s = surface_ratio(tumor_mask.astype(np.uint8))
    after_s = surface_ratio((result == 2).astype(np.uint8))
    print(f"  Voxels: {before:,} -> {after:,} ({(after-before)/max(before,1)*100:+.1f}%)")
    print(f"  Surface: {before_s:.1f}% -> {after_s:.1f}%")

    return result


# ──────────────────────────────────────────────
# 기능 5: 신장+종양 장기 외곽 smoothing
# ──────────────────────────────────────────────

def func_smooth_kidney(data, zooms=None, **kwargs):
    """종양 유지, 신장+종양 장기 외곽 smoothing."""
    kidney_mask = (data == 1)
    tumor_mask = (data == 2)
    before_kidney = int(np.sum(kidney_mask))

    if before_kidney == 0:
        print("  신장 라벨 없음")
        return data

    sigma = input_float("  Gaussian sigma mm (기본 1.0)", default=1.0)
    close_iter = input_int("  Closing 반복 (기본 3)", default=3)
    open_iter = input_int("  Opening 반복 (기본 2)", default=2)
    keep_n = input_int("  유지할 component 수 (기본 2)", default=2)

    organ_mask = (kidney_mask | tumor_mask).astype(np.uint8)

    # 상위 keep_n개 component 유지
    labeled, n_comp = ndimage.label(organ_mask)
    if n_comp > keep_n:
        sizes = ndimage.sum(organ_mask, labeled, range(1, n_comp + 1))
        top_indices = np.argsort(sizes)[::-1][:keep_n]
        top_labels = set(top_indices + 1)
        new_mask = np.zeros_like(organ_mask)
        for lbl in top_labels:
            new_mask[labeled == lbl] = 1
        removed = int(np.sum(organ_mask)) - int(np.sum(new_mask))
        organ_mask = new_mask.astype(np.uint8)
        labeled, n_comp = ndimage.label(organ_mask)
        print(f"  고립 제거: {removed:,} voxels")

    # 각 component별 smoothing
    struct = ndimage.generate_binary_structure(3, 1)
    smoothed_organ = np.zeros_like(organ_mask, dtype=np.uint8)

    for i in range(1, n_comp + 1):
        comp = (labeled == i).astype(np.float64)
        if close_iter > 0:
            comp = ndimage.binary_closing(comp, structure=struct, iterations=close_iter).astype(np.float64)
        if open_iter > 0:
            comp = ndimage.binary_opening(comp, structure=struct, iterations=open_iter).astype(np.float64)
        sigma_voxels = [sigma / float(z) for z in zooms]
        comp = ndimage.gaussian_filter(comp, sigma=sigma_voxels)
        smoothed_organ = np.maximum(smoothed_organ, (comp >= 0.5).astype(np.uint8))

    result = data.copy()
    result[kidney_mask] = 0
    result[tumor_mask] = 0
    final_tumor = tumor_mask & (smoothed_organ == 1)
    final_kidney = (smoothed_organ == 1) & ~final_tumor
    result[final_kidney] = 1
    result[final_tumor] = 2

    after_kidney = int(np.sum(result == 1))
    before_s = surface_ratio((kidney_mask | tumor_mask).astype(np.uint8))
    after_s = surface_ratio((smoothed_organ == 1).astype(np.uint8))
    print(f"  신장 Voxels: {before_kidney:,} -> {after_kidney:,} ({(after_kidney-before_kidney)/max(before_kidney,1)*100:+.1f}%)")
    print(f"  장기 외곽 Surface: {before_s:.1f}% -> {after_s:.1f}%")

    return result


# ──────────────────────────────────────────────
# 기능 6: Intensity 기반 경계 확장
# ──────────────────────────────────────────────

def func_expand_boundary(data, ct_data=None, **kwargs):
    """특정 intensity 기준으로 경계 확장."""
    if ct_data is None:
        print("  CT 이미지 없음 — 실행 불가")
        return data

    target = input_choice("  확장 대상", ["1: 신장(label 1)", "2: 종양(label 2)"])
    label = int(target)
    name = {1: "신장", 2: "종양"}[label]

    threshold = input_float("  최소 intensity HU (기본 120)", default=120.0)
    steps = input_int("  확장 횟수 (기본 5)", default=5)

    mask = (data == label).astype(np.uint8)
    struct = ndimage.generate_binary_structure(3, 1)
    total_added = 0

    for step in range(steps):
        dilated = ndimage.binary_dilation(mask, structure=struct).astype(np.uint8)
        candidates = (dilated == 1) & (mask == 0) & (data == 0)  # 배경만 확장
        accepted = candidates & (ct_data >= threshold)
        added = int(np.sum(accepted))
        total_added += added

        if added == 0:
            break

        mask[accepted] = 1
        print(f"    Step {step + 1}: +{added:,} voxels")

    result = data.copy()
    new_voxels = (mask == 1) & (data != label)
    result[new_voxels] = label
    print(f"  {name} 확장 완료: +{total_added:,} voxels")

    return result


# ──────────────────────────────────────────────
# 기능 7: 라벨 상태 분석
# ──────────────────────────────────────────────

def func_analyze(data, ct_data=None, **kwargs):
    """현재 라벨 상태 상세 분석."""
    print_label_info(data, ct_data)

    for label, name in [(1, "신장"), (2, "종양")]:
        mask = (data == label)
        total = int(np.sum(mask))
        if total == 0:
            continue
        labeled, n_comp = ndimage.label(mask)
        sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
        sorted_idx = np.argsort(sizes)[::-1]
        sr = surface_ratio(mask.astype(np.uint8))
        print(f"  {name}: {n_comp}개 component, surface={sr:.1f}%")
        for rank, idx in enumerate(sorted_idx[:5]):
            print(f"    #{rank+1}: {int(sizes[idx]):>10,} voxels")
        if n_comp > 5:
            small_total = sum(int(sizes[idx]) for idx in sorted_idx[5:])
            print(f"    ... 외 {n_comp-5}개 ({small_total:,} voxels)")
        print()

    return data  # 변경 없음


# ──────────────────────────────────────────────
# 입력 헬퍼
# ──────────────────────────────────────────────

def input_choice(prompt, options):
    """선택지 입력."""
    for opt in options:
        print(f"    {opt}")
    while True:
        val = input(f"  {prompt}: ").strip()
        valid = [opt.split(":")[0].strip() for opt in options]
        if val in valid:
            return val
        print(f"    → {', '.join(valid)} 중 하나를 입력하세요")


def input_int(prompt, default):
    val = input(f"  {prompt}: ").strip()
    if val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


def input_float(prompt, default):
    val = input(f"  {prompt}: ").strip()
    if val == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


# ──────────────────────────────────────────────
# 기능 8: 내부 구멍 채우기
# ──────────────────────────────────────────────

def func_fill_holes(data, **kwargs):
    """라벨 내부 구멍을 채우기 (외곽 형태 유지)."""
    target = input_choice("  대상 선택", ["1: 신장(label 1)", "2: 종양(label 2)", "3: 신장+종양 장기 전체"])

    if target == "3":
        # 신장+종양 합쳐서 fill → 채워진 부분은 신장으로
        kidney_mask = (data == 1)
        tumor_mask = (data == 2)
        organ_mask = (kidney_mask | tumor_mask)
        before = int(np.sum(organ_mask))

        filled = ndimage.binary_fill_holes(organ_mask).astype(np.uint8)
        new_voxels = (filled == 1) & ~organ_mask

        result = data.copy()
        result[new_voxels] = 1  # 채워진 부분은 신장으로
        added = int(np.sum(new_voxels))
        print(f"  장기 내부 구멍 채움: +{added:,} voxels (신장으로 라벨링)")
    else:
        label = int(target)
        name = {1: "신장", 2: "종양"}[label]
        mask = (data == label)
        before = int(np.sum(mask))

        filled = ndimage.binary_fill_holes(mask).astype(np.uint8)
        new_voxels = (filled == 1) & ~mask

        result = data.copy()
        result[new_voxels] = label
        added = int(np.sum(new_voxels))
        print(f"  {name} 내부 구멍 채움: +{added:,} voxels")

    return result


# ──────────────────────────────────────────────
# 기능 9: 고립 신장 → 종양 재라벨링
# ──────────────────────────────────────────────

def func_relabel_isolated_kidney(data, **kwargs):
    """종양 인접 고립 신장 component를 종양으로 재라벨링."""
    kidney_mask = (data == 1)
    tumor_mask = (data == 2)

    total_kidney = int(np.sum(kidney_mask))
    if total_kidney == 0:
        print("  신장 라벨 없음")
        return data

    labeled, n_comp = ndimage.label(kidney_mask)
    if n_comp <= 2:
        print(f"  신장 component {n_comp}개 — 고립 없음")
        return data

    sizes = ndimage.sum(kidney_mask, labeled, range(1, n_comp + 1))
    sorted_indices = np.argsort(sizes)[::-1]

    # 상위 2개 = 좌우 신장 본체
    main_labels = set()
    for idx in sorted_indices[:2]:
        main_labels.add(idx + 1)

    # 종양 인접 마스크
    struct = ndimage.generate_binary_structure(3, 1)
    tumor_adj = ndimage.binary_dilation(tumor_mask, structure=struct).astype(bool)

    result = data.copy()
    relabeled_count = 0
    relabeled_voxels = 0

    for i in range(1, n_comp + 1):
        if i in main_labels:
            continue
        comp_mask = (labeled == i)
        comp_size = int(np.sum(comp_mask))

        if np.any(comp_mask & tumor_adj):
            result[comp_mask] = 2
            relabeled_count += 1
            relabeled_voxels += comp_size

    if relabeled_voxels > 0:
        print(f"  고립 신장 {relabeled_count}개 → 종양으로 재라벨링 (+{relabeled_voxels:,} voxels)")
    else:
        print(f"  종양 인접 고립 신장 없음")

    return result


# ──────────────────────────────────────────────
# 메인 루프
# ──────────────────────────────────────────────

FUNCTIONS = {
    "1": ("라벨 상태 분석", func_analyze),
    "2": ("고립 복셀 제거", func_remove_isolated),
    "3": ("저강도 제거 (intensity ≤ 0)", func_remove_low_intensity),
    "4": ("고강도 제거 (intensity ≥ threshold)", func_remove_high_intensity),
    "5": ("종양 smoothing", func_smooth_tumor),
    "6": ("신장+종양 장기 외곽 smoothing", func_smooth_kidney),
    "7": ("Intensity 기반 경계 확장", func_expand_boundary),
    "8": ("내부 구멍 채우기", func_fill_holes),
    "9": ("고립 신장 → 종양 재라벨링", func_relabel_isolated_kidney),
    "r": ("롤백 (직전 상태로 되돌리기)", None),  # 특수 처리
}


def main():
    if len(sys.argv) < 2:
        print("사용법: python segtools.py <케이스 폴더>")
        print("예시:   python segtools.py S004")
        sys.exit(1)

    case_dir = sys.argv[1]
    if not os.path.isdir(case_dir):
        print(f"폴더를 찾을 수 없음: {case_dir}")
        sys.exit(1)

    case_name = os.path.basename(os.path.abspath(case_dir))
    phases = load_case(case_dir)

    if not phases:
        print(f"세그멘테이션 파일을 찾을 수 없음: {case_dir}")
        sys.exit(1)

    print(f"\n케이스: {case_name}")
    print(f"사용 가능한 phase: {', '.join(sorted(phases.keys()))}")

    while True:
        # Phase 선택
        print(f"\n{'─'*50}")
        print(f"Phase 선택 (q: 종료)")
        for p in sorted(phases.keys()):
            ct_status = "CT있음" if phases[p]["img"] else "CT없음"
            print(f"  {p}: {os.path.basename(phases[p]['seg'])} ({ct_status})")
        print(f"  a: 모든 phase에 동일 작업 실행")

        phase_input = input("\n  Phase: ").strip().upper()
        if phase_input in ("Q", "QUIT", "EXIT"):
            print("종료.")
            break

        if phase_input == "A":
            selected_phases = sorted(phases.keys())
        elif phase_input in phases:
            selected_phases = [phase_input]
        else:
            print("  → 유효한 phase를 입력하세요")
            continue

        # 기능 선택
        print(f"\n  기능 선택:")
        for key, (name, _) in FUNCTIONS.items():
            # 롤백은 히스토리 있을 때만 표시
            if key == "r":
                has_history = any(p in rollback_history and len(rollback_history[p]) > 0
                                 for p in selected_phases)
                if has_history:
                    print(f"    {key}: {name}")
            else:
                print(f"    {key}: {name}")
        print(f"    b: 돌아가기")

        func_input = input("\n  기능: ").strip().lower()
        if func_input == "b":
            continue
        if func_input not in FUNCTIONS:
            print("  → 유효한 기능 번호를 입력하세요")
            continue

        func_name, func = FUNCTIONS[func_input]

        # ── 롤백 처리 ──
        if func_input == "r":
            for phase in selected_phases:
                seg_path = phases[phase]["seg"]
                if phase not in rollback_history or len(rollback_history[phase]) == 0:
                    print(f"\n  [{phase} phase] 롤백 히스토리 없음")
                    continue

                prev_data, prev_desc, seg_img = rollback_history[phase][-1]
                print(f"\n  [{phase} phase] 롤백: '{prev_desc}' 이전 상태로 되돌리기")

                save_result(seg_path, prev_data, seg_img)
                rollback_history[phase].pop()

                remain = len(rollback_history[phase])
                print(f"  남은 히스토리: {remain}단계")
            continue

        # ── 일반 기능 실행 ──
        for phase in selected_phases:
            seg_path = phases[phase]["seg"]
            img_path = phases[phase]["img"]

            print(f"\n{'='*50}")
            print(f"  [{phase} phase] {func_name}")
            print(f"{'='*50}")

            # 로드
            seg_img = nib.load(seg_path)
            data = np.round(np.asanyarray(seg_img.dataobj)).astype(np.uint16)
            zooms = seg_img.header.get_zooms()

            ct_data = None
            if img_path and os.path.exists(img_path):
                ct_img = nib.load(img_path)
                ct_data = np.asanyarray(ct_img.dataobj).astype(np.float32)

            # 실행
            result = func(data, ct_data=ct_data, zooms=zooms)

            # 변경 확인
            if np.array_equal(data, result):
                print("\n  변경 없음.")
                continue

            changed = int(np.sum(data != result))
            print(f"\n  변경된 복셀: {changed:,}")

            # 저장 (히스토리에 이전 상태 저장 후 결과 저장)
            if phase not in rollback_history:
                rollback_history[phase] = []
            rollback_history[phase].append((data.copy(), func_name, seg_img))

            backup_file(seg_path)
            save_result(seg_path, result, seg_img)

            history_depth = len(rollback_history[phase])
            print(f"  (롤백 가능: {history_depth}단계)")


if __name__ == "__main__":
    main()
