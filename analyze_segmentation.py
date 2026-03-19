"""
세그멘테이션 라벨 분석 스크립트

사용법:
    python analyze_segmentation.py <nii.gz 파일 경로> [추가 파일 ...]
    python analyze_segmentation.py S003/S003_Segmentation_A.nii.gz
    python analyze_segmentation.py S003/*.nii.gz

출력:
    - 이미지 shape, voxel size
    - 라벨별 voxel 수, 볼륨(mL)
    - 표면 불규칙도 (surface voxel 비율)
    - Connected component 수
    - 신장(label 1) 상세 분석: 좌/우 신장 식별, 고립 복셀, 이상 component 판별
"""

import sys
import glob
import nibabel as nib
import numpy as np
from scipy import ndimage


def analyze_kidney_components(components, vol_shape):
    """
    신장(label 1) component 상세 분석
    - 좌/우 신장 식별 (x축 중심 기준)
    - 고립 복셀 / 쓸모없는 작은 component 판별
    - 이상 여부 경고
    """
    total_voxels = sum(c["size"] for c in components)
    x_center = vol_shape[0] / 2

    # 크기 기준 분류
    KIDNEY_MIN_ML = 10.0       # 신장으로 인정하는 최소 볼륨 (mL)
    NOISE_MAX_VOXELS = 100     # 이 이하면 고립 노이즈로 판단
    SMALL_FRAG_MAX_ML = 10.0   # 이 이하면 작은 조각으로 판단

    kidneys = []
    small_fragments = []
    noise = []

    for c in components:
        if c["volume_ml"] >= KIDNEY_MIN_ML:
            kidneys.append(c)
        elif c["size"] <= NOISE_MAX_VOXELS:
            noise.append(c)
        else:
            small_fragments.append(c)

    # 신장 좌/우 판별 (x축 centroid 기준)
    print()
    print(f"    [신장 분석] 총 {len(components)}개 component, 전체 {total_voxels:,} voxels")
    print()

    if len(kidneys) == 2:
        # x좌표로 좌/우 구분
        kidneys.sort(key=lambda c: c["centroid"][0])
        sides = ["우측(R)", "좌측(L)"] if kidneys[0]["centroid"][0] < x_center else ["좌측(L)", "우측(R)"]
        for k, side in zip(kidneys, sides):
            pct = k["size"] / total_voxels * 100
            print(f"    {side} 신장 (Component {k['id']})")
            print(f"      크기: {k['size']:>12,} voxels ({k['volume_ml']:.1f}mL, 전체의 {pct:.1f}%)")
            print(f"      중심: x={k['centroid'][0]:.0f}, y={k['centroid'][1]:.0f}, z={k['centroid'][2]:.0f}")
            print(f"      범위: [{k['bbox_min'][0]}-{k['bbox_max'][0]}, {k['bbox_min'][1]}-{k['bbox_max'][1]}, {k['bbox_min'][2]}-{k['bbox_max'][2]}]")
        # 좌우 크기 비율 확인
        ratio = kidneys[0]["size"] / max(kidneys[1]["size"], 1)
        if ratio < 0.5 or ratio > 2.0:
            print(f"    ⚠ 경고: 좌우 신장 크기 비율 {ratio:.2f} — 한쪽이 비정상적으로 작거나 큼")
    elif len(kidneys) == 1:
        k = kidneys[0]
        side = "우측(R)" if k["centroid"][0] < x_center else "좌측(L)"
        print(f"    ⚠ 경고: 신장이 1개만 감지됨 ({side} 추정)")
        print(f"      크기: {k['size']:>12,} voxels ({k['volume_ml']:.1f}mL)")
        print(f"      중심: x={k['centroid'][0]:.0f}, y={k['centroid'][1]:.0f}, z={k['centroid'][2]:.0f}")
    elif len(kidneys) == 0:
        print(f"    ⚠ 경고: {KIDNEY_MIN_ML}mL 이상인 component가 없음 — 세그멘테이션 문제 가능성")
    else:
        print(f"    ⚠ 경고: 신장으로 추정되는 component가 {len(kidneys)}개 (2개 예상)")
        for c in kidneys:
            print(f"      Component {c['id']}: {c['size']:>12,} voxels ({c['volume_ml']:.1f}mL), 중심 x={c['centroid'][0]:.0f}")

    # 작은 조각
    if small_fragments:
        print()
        frag_total = sum(c["size"] for c in small_fragments)
        print(f"    작은 조각: {len(small_fragments)}개, 합계 {frag_total:,} voxels")
        for c in small_fragments:
            pct = c["size"] / total_voxels * 100
            print(f"      Component {c['id']}: {c['size']:>8,} voxels ({c['volume_ml']:.2f}mL, {pct:.2f}%), 중심 x={c['centroid'][0]:.0f}, y={c['centroid'][1]:.0f}, z={c['centroid'][2]:.0f}")

    # 고립 노이즈
    if noise:
        print()
        noise_total = sum(c["size"] for c in noise)
        print(f"    고립 노이즈 (≤{NOISE_MAX_VOXELS} voxels): {len(noise)}개, 합계 {noise_total:,} voxels — 제거 권장")
        if len(noise) <= 10:
            for c in noise:
                print(f"      Component {c['id']}: {c['size']:>5} voxels, 중심 x={c['centroid'][0]:.0f}, y={c['centroid'][1]:.0f}, z={c['centroid'][2]:.0f}")
        else:
            for c in noise[:5]:
                print(f"      Component {c['id']}: {c['size']:>5} voxels, 중심 x={c['centroid'][0]:.0f}, y={c['centroid'][1]:.0f}, z={c['centroid'][2]:.0f}")
            print(f"      ... 외 {len(noise) - 5}개")

    if not small_fragments and not noise:
        print()
        print(f"    ✓ 고립 복셀/불필요한 조각 없음")

    print()


def analyze_segmentation(path):
    """단일 세그멘테이션 파일 분석"""
    img = nib.load(path)
    data = np.round(np.asanyarray(img.dataobj)).astype(np.uint16)
    zooms = img.header.get_zooms()
    voxel_vol_mm3 = float(zooms[0]) * float(zooms[1]) * float(zooms[2])

    print(f"=== {path} ===")
    print(f"  Shape: {data.shape}")
    print(f"  Voxel size: {zooms[0]:.3f} x {zooms[1]:.3f} x {zooms[2]:.3f} mm")
    print(f"  Data type: {img.header.get_data_dtype()}")
    print()

    labels = np.unique(data)
    print(f"  {'Label':<8} {'Voxels':>12} {'Volume(mL)':>12} {'Surface%':>10} {'Components':>12}")
    print(f"  {'-'*58}")

    for label in labels:
        mask = (data == label).astype(np.uint8)
        voxel_count = int(np.sum(mask))
        volume_ml = voxel_count * voxel_vol_mm3 / 1000

        if label == 0:
            print(f"  {int(label):<8} {voxel_count:>12,} {volume_ml:>12.2f} {'--':>10} {'--':>12}")
            continue

        # 표면 불규칙도
        eroded = ndimage.binary_erosion(mask)
        surface_voxels = voxel_count - int(np.sum(eroded))
        surface_ratio = surface_voxels / max(voxel_count, 1) * 100

        # Connected components
        _, n_components = ndimage.label(mask)

        print(f"  {int(label):<8} {voxel_count:>12,} {volume_ml:>12.2f} {surface_ratio:>9.1f}% {n_components:>12}")

        # Connected component 상세 분석
        if n_components > 1:
            labeled, _ = ndimage.label(mask)
            components = []
            for i in range(1, n_components + 1):
                comp_mask = (labeled == i)
                comp_size = int(np.sum(comp_mask))
                coords = np.argwhere(comp_mask)
                centroid = coords.mean(axis=0)
                bbox_min = coords.min(axis=0)
                bbox_max = coords.max(axis=0)
                comp_vol_ml = comp_size * voxel_vol_mm3 / 1000
                components.append({
                    "id": i,
                    "size": comp_size,
                    "volume_ml": comp_vol_ml,
                    "centroid": centroid,
                    "bbox_min": bbox_min,
                    "bbox_max": bbox_max,
                })
            components.sort(key=lambda x: x["size"], reverse=True)

            # 신장(label 1) 전용 상세 분석
            if int(label) == 1:
                analyze_kidney_components(components, data.shape)
            else:
                for c in components[:10]:
                    vol_str = f"({c['volume_ml']:.1f}mL)"
                    print(f"           Component {c['id']}: {c['size']:>12,} voxels {vol_str:>12}")
                if n_components > 10:
                    print(f"           ... and {n_components - 10} more")

    print()


def main():
    if len(sys.argv) < 2:
        print("사용법: python analyze_segmentation.py <파일경로> [추가파일 ...]")
        print("예시:   python analyze_segmentation.py S003/S003_Segmentation_A.nii.gz")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        expanded = glob.glob(arg)
        if expanded:
            paths.extend(expanded)
        else:
            paths.append(arg)

    for path in sorted(paths):
        analyze_segmentation(path)


if __name__ == "__main__":
    main()
