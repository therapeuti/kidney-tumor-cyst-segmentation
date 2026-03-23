# Kidney & Tumor Segmentation Post-processing

신장(kidney) + 종양(tumor) + 물혹(cyst) 세그멘테이션 라벨의 후처리 도구.

## 폴더 구조

```
segmentation/
├── S003/
│   ├── S003_Segmentation_A.nii.gz    # 세그멘테이션 (A phase)
│   ├── S003_image_A.nii.gz           # CT 이미지 (A phase)
│   └── backup_original/              # 원본 백업
├── S004/
│   ├── S004_segmentation_A.nii.gz
│   ├── S004_image_A.nii.gz
│   └── ...
└── segtools.py
```

### 라벨 정의
- `0`: 배경
- `1`: 신장 (kidney)
- `2`: 종양 (tumor)
- `3`: 물혹 (cyst)

---

## segtools.py (대화형)

모든 후처리 기능을 하나의 대화형 프로그램에서 실행.

### 실행

```bash
python segtools.py S004
```

### 사용 흐름

```
1. Phase 선택 (A / D / P / all=전체)
2. 기능 선택
3. 파라미터 입력 (엔터로 기본값 사용)
4. 실행 → 자동 저장
5. 이미지 뷰어에서 확인
6. 실행 후 r로 롤백 또는 enter로 계속 진행
7. q로 종료
```

### 기능 목록

| 번호 | 기능 | 설명 |
|------|------|------|
| 1 | 라벨 상태 분석 | 라벨별 voxel 수, intensity 통계, component 개수/크기 출력 |
| 2 | 고립 복셀 제거 | 신장/종양의 connected component 중 상위 N개만 유지, 나머지 제거 |
| 3 | 저강도 제거 | CT intensity ≤ 0인 신장/종양 복셀을 배경으로 삭제 |
| 4 | 고강도 제거 | CT intensity ≥ threshold(기본 400)인 신장/종양 복셀을 배경으로 삭제 |
| 5 | Smoothing | 대상 선택(종양/물혹/장기 전체 외곽) → closing → opening → Gaussian smoothing |
| 6 | 경계 확장 | 대상 선택(신장/종양/물혹) → intensity 조건(하한 or 양방향) → 반복 dilation |
| 7 | 경계 축소 | 대상 선택(신장(장기 외곽)/종양/물혹) → HU 범위 밖 복셀을 표면부터 반복 깎아냄 |
| 8 | 경계 계단 메꿈 | 26-connectivity closing으로 장기 외곽 계단 형태를 메꾸고 HU 조건 필터링 |
| 9 | 돌출부 제거 | Opening으로 신장 경계의 얇은 돌출부 제거 (종양 인접 보호) |
| 10 | 내부 구멍 채우기 | 대상 선택(신장/종양/물혹/장기 전체) → 내부 빈 공간 채움 |
| 11 | 고립 신장 → 종양 재라벨링 | 종양 인접 고립 신장 component를 종양으로 변경 |
| 12 | 볼록 껍질 기반 라벨링 | 대상 선택(종양/물혹) → 시드로 3D Convex Hull → 내부 채움 |
| 13 | 세그멘테이션 합치기 | 외부 파일에서 신장 라벨을 가져와 현재 파일의 신장을 교체 |
| 14 | Phase 비교 분석 | 모든 phase 동시 로드 → 라벨별 크기 비교, Dice 계수, 불일치 영역 분석 |
| r | 롤백 | 직전 상태로 되돌리기 (다단계 히스토리) |

### 파라미터 가이드

**Smoothing (기능 5)**
- `sigma`: Gaussian smoothing 강도 (mm). 클수록 부드러움. 기본 1.0
- `closing 반복`: 구멍/빈 부분 채우기 강도. 클수록 큰 구멍도 채움. 기본 2~3
- `opening 반복`: 돌출부 제거 강도. 클수록 공격적. 기본 1~2

**경계 확장 (기능 6)**
- `intensity 조건`: 하한만(≥ threshold) 또는 양방향(평균 ± tolerance) 선택
- `확장 횟수`: 매 회 경계에서 1복셀씩 확장. 기본 5

**경계 축소 (기능 7)**
- `HU 범위`: 대상 라벨의 평균 ± tolerance. 범위 밖 표면 복셀을 깎아냄
- `최대 반복`: 표면 1겹씩 반복. 기본 1

---

## 의존성

```
pip install nibabel numpy scipy
```
