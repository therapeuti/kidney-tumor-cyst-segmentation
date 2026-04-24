from pathlib import Path


PHASES = ("A", "D", "P")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_case_paths(case_dir: Path) -> dict[str, dict[str, Path | None]]:
    case_name = case_dir.name
    phases: dict[str, dict[str, Path | None]] = {}
    for phase in PHASES:
        seg_path: Path | None = None
        for fmt in (
            f"{case_name}_Segmentation_{phase}.nii.gz",
            f"{case_name}_segmentation_{phase}.nii.gz",
        ):
            candidate = case_dir / fmt
            if candidate.exists():
                seg_path = candidate
                break

        img_path = case_dir / f"{case_name}_image_{phase}.nii.gz"
        has_img = img_path.exists()

        if seg_path is not None or has_img:
            phases[phase] = {
                "seg": seg_path,
                "img": img_path if has_img else None,
            }
    return phases


def discover_case_dirs() -> list[Path]:
    root = repo_root()
    case_dirs: list[Path] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in {"docs", "backend", "frontend", "__pycache__"}:
            continue
        if load_case_paths(child):
            case_dirs.append(child)
    return sorted(case_dirs)


def get_case_dir(case_id: str) -> Path | None:
    root = repo_root()
    case_dir = root / case_id
    if not case_dir.is_dir():
        return None
    if not load_case_paths(case_dir):
        return None
    return case_dir
