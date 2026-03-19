# Kidney & Tumor Segmentation Post-processing

신장(kidney) + 종양(tumor) 세그멘테이션 라벨의 후처리 도구 모음.

## 폴더 구조

```
segmentation/
├── S003/
│   ├── S003_Segmentation_A.nii.gz    # 세그멘테이션 (A phase)
│   ├── S003_image_A.nii.gz           # CT 이미지 (A phase)
│   ├── S003_image_A_kidney_seg.nii.gz # 신장 세그멘테이션 원본
│   └── backup_original/              # 원본 백업
├── S004/
│   ├── S004_segmentation_A.nii.gz
│   ├── S004_image_A.nii.gz
│   └── ...
└── (스크립트들)
```

### 라벨 정의
- `0`: 배경
- `1`: 신장 (kidney)
- `2`: 종양 (tumor)

---

## 최종 도구: segtools.py (대화형)

모든 후처리 기능을 하나의 대화형 프로그램에서 실행.

### 실행

```bash
cd segmentation
python segtools.py S004
```

### 사용 흐름

```
1. Phase 선택 (A / D / P / a=전체)
2. 기능 선택
3. 파라미터 입력 (엔터로 기본값 사용)
4. 실행 → 자동 저장
5. 이미지 뷰어에서 확인
6. 이상하면 r로 롤백, 아니면 다음 기능 진행
7. q로 종료
```

### 기능 목록

| 번호 | 기능 | 설명 |
|------|------|------|
| 1 | 라벨 상태 분석 | 라벨별 voxel 수, intensity 분포, component 수 표시 |
| 2 | 고립 복셀 제거 | 신장/종양의 작은 고립 component 삭제 (신장: 상위 2개, 종양: 상위 1개 유지) |
| 3 | 저강도 제거 | intensity <= 0 HU인 신장/종양 복셀 삭제 (공기/노이즈) |
| 4 | 고강도 제거 | intensity >= threshold(기본 400) HU인 복셀 삭제 (혈관/조영제 등) |
| 5 | 종양 smoothing | closing(사이 채움) → opening(돌출 제거) → gaussian(경계 다듬기) |
| 6 | 장기 외곽 smoothing | 신장+종양을 하나로 합쳐서 외곽 경계를 smooth (종양은 유지) |
| 7 | Intensity 기반 경계 확장 | 라벨 경계에서 intensity >= threshold인 인접 복셀로 확장 |
| r | 롤백 | 직전 상태로 되돌리기 (여러 단계 가능) |

### 권장 작업 순서

```
1. 분석 (기능 1) — 현재 상태 파악
2. 저강도 제거 (기능 3) — intensity <= 0 삭제
3. 고강도 제거 (기능 4) — intensity >= 400 삭제 (필요 시)
4. 고립 복셀 제거 (기능 2) — 노이즈 제거
5. 종양 smoothing (기능 5) — 종양 경계 다듬기
6. 장기 외곽 smoothing (기능 6) — 신장 외곽 다듬기
```

### 파라미터 가이드

**Smoothing 파라미터 (기능 5, 6)**
- `sigma`: Gaussian smoothing 강도 (mm). 클수록 부드러움. 기본 1.0
- `closing 반복`: 구멍/빈 부분 채우기 강도. 클수록 큰 구멍도 채움. 기본 3
- `opening 반복`: 돌출부 제거 강도. 클수록 공격적. 기본 2. 움푹 패이면 줄이기

**Intensity 확장 파라미터 (기능 7)**
- `최소 intensity`: 이 값 이상인 인접 복셀만 라벨링. 기본 120 HU
- `확장 횟수`: 반복 횟수. 매 회 경계에서 1 복셀씩 확장. 기본 5

---

## 개별 스크립트

대화형 도구 외에 CLI 스크립트로도 실행 가능.

### analyze_segmentation.py — 세그멘테이션 분석

라벨별 voxel 수, 볼륨, 표면 불규칙도, component 분석.
신장(label 1)은 좌/우 신장 식별, 고립 복셀 판별 포함.

```bash
python analyze_segmentation.py S004/S004_segmentation_*.nii.gz
```

### analyze_intensity.py — CT intensity 분포 분석

Phase별 신장/종양의 CT intensity 분포, 겹침 구간, phase 간 비교.

```bash
python analyze_intensity.py S004
```

### postprocess.py — 통합 후처리 (자동)

Step 1~3을 한번에 자동 실행하는 CLI 스크립트.

```bash
python postprocess.py S004/S004_segmentation_*.nii.gz
python postprocess.py S004/S004_segmentation_P.nii.gz --tumor-close-iter 5 --tumor-open-iter 1
```

### smooth_tumor.py — 종양 smoothing

종양 라벨만 smoothing. 저강도 삭제 + 고립 신장 재라벨링 전처리 포함.

```bash
python smooth_tumor.py S004/S004_segmentation_*.nii.gz --close-iter 5
```

### smooth_kidney_tumor.py — 신장+종양 통합 smoothing

신장+종양을 하나의 장기로 합쳐서 외곽 smoothing + intensity 기반 경계 확장.

```bash
python smooth_kidney_tumor.py S004/S004_segmentation_*.nii.gz --expand-steps 5 --expand-threshold 120
```

### smooth_segmentation.py — 단일 라벨 smoothing

특정 라벨만 지정하여 smoothing. 가장 기본적인 스크립트.

```bash
python smooth_segmentation.py S004/S004_segmentation_*.nii.gz --target-label 2 --sigma 1.0
```

### remove_tubular.py — 관 구조 제거 (혈관/ureter)

신장의 안쪽(hilum) 방향에서 뻗어나온 가느다란 관 구조를 erosion 기반으로 제거.

```bash
python remove_tubular.py S004/S004_segmentation_*.nii.gz --erosion-iter 5
```

---

## 의존성

```
pip install nibabel numpy scipy
```
