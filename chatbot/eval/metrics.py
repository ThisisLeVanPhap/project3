from typing import Iterable, Mapping, Sequence


def normalize_identifier(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def is_match(predicted_id: object, ground_truth_id: object) -> bool:
    """
    Match identifiers with simple normalized string rules.

    Behavior:
    - exact match still works for full URLs or other canonical ids
    - partial match also works when a ground-truth keyword/fragment is contained
      inside the predicted identifier
    """
    predicted = normalize_identifier(predicted_id)
    expected = normalize_identifier(ground_truth_id)
    if not predicted or not expected:
        return False
    return predicted == expected or expected in predicted


def matching_field(candidate: Mapping[str, object], ground_truth_id: object) -> str | None:
    """
    Try the same simple normalized match against supported retrieved fields.

    Identifier matching keeps backward compatibility with URL/source-based labels.
    Title matching lets keyword labels like "bảo hành" match relevant retrieved titles.
    """
    if is_match(candidate.get("identifier"), ground_truth_id):
        return "identifier"
    if is_match(candidate.get("title"), ground_truth_id):
        return "title"
    return None


def first_matching_ground_truth(candidate: Mapping[str, object], ground_truth_ids: Iterable[str]) -> tuple[str, str] | None:
    for ground_truth_id in ground_truth_ids:
        field = matching_field(candidate, ground_truth_id)
        if field is not None:
            return str(ground_truth_id).strip(), field
    return None


def recall_at_k(predicted_candidates: Sequence[Mapping[str, object]], ground_truth_ids: Iterable[str], k: int) -> float:
    if k <= 0:
        return 0.0

    expected = [str(item).strip() for item in ground_truth_ids if normalize_identifier(item)]
    if not expected:
        return 0.0

    for candidate in predicted_candidates[:k]:
        if first_matching_ground_truth(candidate, expected) is not None:
            return 1.0
    return 0.0


def reciprocal_rank(predicted_candidates: Sequence[Mapping[str, object]], ground_truth_ids: Iterable[str], k: int | None = None) -> float:
    expected = [str(item).strip() for item in ground_truth_ids if normalize_identifier(item)]
    if not expected:
        return 0.0

    limit = len(predicted_candidates) if k is None else max(0, k)
    for index, candidate in enumerate(predicted_candidates[:limit], start=1):
        if first_matching_ground_truth(candidate, expected) is not None:
            return 1.0 / index
    return 0.0
