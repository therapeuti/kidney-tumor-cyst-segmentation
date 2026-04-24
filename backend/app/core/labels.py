from segtools_core import LABEL_METADATA


def label_metadata_list() -> list[dict[str, object]]:
    colors = {
        0: [0, 0, 0, 0],
        1: [80, 170, 255, 180],
        2: [255, 80, 80, 180],
        3: [255, 210, 80, 180],
    }
    return [
        {
            "id": label_id,
            "key": meta["key"],
            "name": meta["name_en"],
            "color": colors.get(label_id, [255, 255, 255, 180]),
        }
        for label_id, meta in sorted(LABEL_METADATA.items())
    ]
