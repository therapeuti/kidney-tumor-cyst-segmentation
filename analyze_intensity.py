"""
신장/종양 라벨 영역의 CT intensity 분포 분석 스크립트

사용법:
    python analyze_intensity.py <케이스 폴더>
    python analyze_intensity.py S003
    python analyze_intensity.py S003 S004 S005

출력:
    - Phase별 (A/D/P) 신장, 종양의 intensity 분포
    - 평균, 표준편차, 최소, 최대, 사분위수
    - Phase 간 비교
"""

import sys
import os
import glob
import nibabel as nib
import numpy as np


def analyze_intensity(case_dir):
    """케이스 폴더 내 phase별 intensity 분석"""
    case_name = os.path.basename(case_dir)
    print(f"{'=' * 70}")
    print(f"  케이스: {case_name}")
    print(f"{'=' * 70}")

    phases = ["A", "D", "P"]
    results = {}

    for phase in phases:
        seg_path = os.path.join(case_dir, f"{case_name}_Segmentation_{phase}.nii.gz")
        img_path = os.path.join(case_dir, f"{case_name}_image_{phase}.nii.gz")

        if not os.path.exists(seg_path):
            print(f"\n  [{phase} phase] 세그멘테이션 파일 없음: {seg_path}")
            continue
        if not os.path.exists(img_path):
            print(f"\n  [{phase} phase] CT 이미지 파일 없음: {img_path}")
            continue

        seg = nib.load(seg_path)
        seg_data = np.round(np.asanyarray(seg.dataobj)).astype(np.uint16)

        img = nib.load(img_path)
        img_data = np.asanyarray(img.dataobj).astype(np.float32)

        print(f"\n  [{phase} phase]")
        print(f"  {'─' * 66}")

        phase_result = {}

        for label, name in [(1, "신장(kidney)"), (2, "종양(tumor)")]:
            mask = (seg_data == label)
            voxel_count = int(np.sum(mask))

            if voxel_count == 0:
                print(f"    {name}: 라벨 없음")
                continue

            values = img_data[mask]

            stats = {
                "count": voxel_count,
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "p5": float(np.percentile(values, 5)),
                "p25": float(np.percentile(values, 25)),
                "median": float(np.median(values)),
                "p75": float(np.percentile(values, 75)),
                "p95": float(np.percentile(values, 95)),
                "max": float(np.max(values)),
            }
            phase_result[label] = stats

            print(f"    {name} ({voxel_count:,} voxels)")
            print(f"      평균 ± 표준편차:  {stats['mean']:.1f} ± {stats['std']:.1f} HU")
            print(f"      범위:            {stats['min']:.0f} ~ {stats['max']:.0f} HU")
            print(f"      5%ile ~ 95%ile:  {stats['p5']:.0f} ~ {stats['p95']:.0f} HU")
            print(f"      사분위:          Q1={stats['p25']:.0f}, 중앙값={stats['median']:.0f}, Q3={stats['p75']:.0f} HU")

        # 신장과 종양 intensity 겹침 분석
        if 1 in phase_result and 2 in phase_result:
            k = phase_result[1]
            t = phase_result[2]
            print(f"\n    [신장 vs 종양 비교]")
            print(f"      신장 범위 (5~95%ile): {k['p5']:.0f} ~ {k['p95']:.0f} HU")
            print(f"      종양 범위 (5~95%ile): {t['p5']:.0f} ~ {t['p95']:.0f} HU")
            overlap_low = max(k['p5'], t['p5'])
            overlap_high = min(k['p95'], t['p95'])
            if overlap_low < overlap_high:
                print(f"      겹치는 구간:         {overlap_low:.0f} ~ {overlap_high:.0f} HU")
            else:
                print(f"      겹치는 구간:         없음 (잘 구분됨)")
            diff = abs(k['mean'] - t['mean'])
            print(f"      평균 차이:           {diff:.1f} HU")

        results[phase] = phase_result

    # Phase 간 비교
    if len(results) > 1:
        print(f"\n  {'=' * 66}")
        print(f"  [Phase 간 비교]")
        print(f"  {'─' * 66}")

        for label, name in [(1, "신장"), (2, "종양")]:
            phase_means = []
            for phase in phases:
                if phase in results and label in results[phase]:
                    phase_means.append((phase, results[phase][label]))

            if len(phase_means) > 1:
                print(f"    {name} 평균 intensity:")
                for phase, s in phase_means:
                    bar_len = int(s['mean'] / 10)
                    bar = "█" * max(bar_len, 0)
                    print(f"      {phase}: {s['mean']:>7.1f} ± {s['std']:.1f} HU  {bar}")

                means = [s['mean'] for _, s in phase_means]
                print(f"      Phase 간 차이: {max(means) - min(means):.1f} HU")
                print()

    print()


def main():
    if len(sys.argv) < 2:
        print("사용법: python analyze_intensity.py <케이스 폴더> [추가 폴더 ...]")
        print("예시:   python analyze_intensity.py S003")
        sys.exit(1)

    for arg in sys.argv[1:]:
        expanded = glob.glob(arg)
        dirs = expanded if expanded else [arg]
        for d in sorted(dirs):
            if os.path.isdir(d):
                analyze_intensity(d)
            else:
                print(f"폴더를 찾을 수 없음: {d}")


if __name__ == "__main__":
    main()
