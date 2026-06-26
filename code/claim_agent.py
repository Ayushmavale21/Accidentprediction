from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OUTPUT_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]


PART_PATTERNS = {
    "car": [
        ("front_bumper", r"\bfront\b.*\bbumper\b|\bbumper\b.*\bfront\b|\bparachoques delantero\b"),
        ("rear_bumper", r"\b(rear|back)\b.*\bbumper\b|\bbumper\b.*\b(rear|back)\b|\bparachoques (?:trasero|de atras)\b"),
        ("left_headlight", r"\bleft\b.*\bhead\s*light\b|\bleft headlight\b"),
        ("right_headlight", r"\bright\b.*\bhead\s*light\b|\bright headlight\b"),
        ("headlight", r"\bhead\s*light\b|\bheadlamp\b"),
        ("windshield", r"\bwind\s*shield\b|\bfront glass\b|\bglass\b"),
        ("side_mirror", r"\bside mirror\b|\bmirror\b"),
        ("door", r"\bdoor\b|\bdoor panel\b"),
        ("hood", r"\bhood\b|\bbonnet\b"),
        ("body", r"\bbody panel\b|\bcar body\b|\bbody crack\b"),
        ("fender", r"\bfender\b"),
        ("wheel", r"\bwheel\b|\btire\b|\btyre\b"),
        ("taillight", r"\btail\s*light\b|\btaillight\b"),
    ],
    "laptop": [
        ("screen", r"\bscreen\b|\bdisplay\b"),
        ("keyboard", r"\bkeyboard\b|\bkey\b"),
        ("hinge", r"\bhinge\b"),
        ("trackpad", r"\btrack\s*pad\b|\btouchpad\b"),
        ("lid", r"\blid\b|\btop cover\b"),
        ("body", r"\bouter body\b|\blaptop body\b|\bbody only\b"),
        ("corner", r"\bcorner\b|\bedge\b"),
        ("port", r"\bcharging port\b|\bcharger port\b|\busb\b|\bport\b"),
    ],
    "package": [
        ("package_corner", r"\bcorner\b|\bedge\b|dab gaya"),
        ("box", r"\bbox\b|\bpackage\b|\bparcel\b|\bcardboard\b"),
        ("seal", r"\bseal\b|\btape\b|\bopened\b|\btamper\b"),
        ("label", r"\blabel\b|\baddress\b|\bshipping\b"),
        ("item", r"\bitem inside\b|\bproduct inside\b"),
        ("contents", r"\bcontent\b|\bitem\b|\bproduct\b|\binside\b|\bmissing\b"),
    ],
}


ISSUE_PATTERNS = [
    ("glass_shatter", r"\bshatter(?:ed|ing)?\b|\bsmashed\b"),
    ("crack", r"\bcrack(?:ed|ing)?\b|\bfracture\b"),
    ("dent", r"\bdent(?:ed)?\b|\bding\b"),
    ("scratch", r"\bscratch(?:ed|es)?\b|\bscrape(?:d)?\b|\bmark\b"),
    ("missing_part", r"\bcontents? (?:were )?missing\b|\bproduct inside .*missing\b|\bitem inside .*missing\b|\bmissing\b"),
    ("broken_part", r"\bbroken\b|\bloose\b|\bnot sitting\b|\baffected\b"),
    ("water_damage", r"\bwater\b|\bliquid\b|\bspill(?:ed)?\b|\bwet\b"),
    ("torn_packaging", r"\btamper(?:ed|ing)?\b|\bopened\b|\bseal\b|\btorn\b"),
    ("crushed_packaging", r"\bcrush(?:ed)?\b|\bcollapsed\b|\bsmashed\b|dab gaya"),
    ("stain", r"\boil(?:y)? mark\b|\boil stain\b|\bstain\b"),
]


SEVERITY_BY_ISSUE = {
    "scratch": "low",
    "dent": "medium",
    "crack": "medium",
    "glass_shatter": "high",
    "broken_part": "medium",
    "water_damage": "high",
    "torn_packaging": "medium",
    "crushed_packaging": "medium",
    "missing_part": "high",
    "stain": "low",
}


NEGATION_PATTERNS = [
    r"\bno (?:visible )?(?:damage|scratch|dent|crack|issue)\b",
    r"\b(?:not|isn't|is not|doesn't|does not) (?:damaged|broken|cracked|scratched|dented)\b",
    r"\blooks (?:fine|okay|ok|normal|intact)\b",
]

ALLOWED_RISK_FLAGS = {
    "none",
    "blurry_image",
    "cropped_or_obstructed",
    "low_light_or_glare",
    "wrong_angle",
    "wrong_object",
    "wrong_object_part",
    "damage_not_visible",
    "claim_mismatch",
    "possible_manipulation",
    "non_original_image",
    "text_instruction_present",
    "user_history_risk",
    "manual_review_required",
}

ALLOWED_ISSUES = {
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "broken_part",
    "missing_part",
    "torn_packaging",
    "crushed_packaging",
    "water_damage",
    "stain",
    "none",
    "unknown",
}

ALLOWED_PARTS = {
    "car": {
        "front_bumper",
        "rear_bumper",
        "door",
        "hood",
        "windshield",
        "side_mirror",
        "headlight",
        "taillight",
        "fender",
        "quarter_panel",
        "body",
        "unknown",
    },
    "laptop": {"screen", "keyboard", "trackpad", "hinge", "lid", "corner", "port", "base", "body", "unknown"},
    "package": {"box", "package_corner", "package_side", "seal", "label", "contents", "item", "unknown"},
}

RISK_FLAG_MAP = {
    "image_missing": "damage_not_visible",
    "image_not_file": "damage_not_visible",
    "image_empty": "damage_not_visible",
    "unsupported_image_type": "damage_not_visible",
    "low_resolution": "cropped_or_obstructed",
    "low_detail_or_blank": "blurry_image",
    "image_quality_unverified": "manual_review_required",
    "possible_image_mismatch": "claim_mismatch",
    "prompt_injection_attempt": "text_instruction_present",
    "repeat_claim_history": "user_history_risk",
    "repeat_or_pressure_risk": "manual_review_required",
    "ambiguous_claim_description": "manual_review_required",
    "visual_contradiction": "claim_mismatch",
    "missing_image_evidence": "damage_not_visible",
}


def normalize_risk_flags(flags: list[str]) -> str:
    normalized = []
    for flag in flags:
        value = RISK_FLAG_MAP.get(str(flag).strip().lower(), str(flag).strip().lower())
        if value in ALLOWED_RISK_FLAGS and value != "none":
            normalized.append(value)
    return ";".join(sorted(set(normalized))) or "none"


def normalize_issue(value: str) -> str:
    value = str(value or "unknown").strip().lower()
    aliases = {
        "shatter": "glass_shatter",
        "tampering": "torn_packaging",
        "crushed": "crushed_packaging",
        "missing_contents": "missing_part",
    }
    value = aliases.get(value, value)
    return value if value in ALLOWED_ISSUES else "unknown"


def normalize_part(value: str, claim_object: str) -> str:
    value = str(value or "unknown").strip().lower()
    aliases = {
        "left_headlight": "headlight",
        "right_headlight": "headlight",
        "charging_port": "port",
        "corner": "package_corner" if claim_object == "package" else "corner",
    }
    value = aliases.get(value, value)
    return value if value in ALLOWED_PARTS.get(claim_object, {"unknown"}) else "unknown"


@dataclass
class ImageObservation:
    image_id: str
    path: str
    exists: bool
    valid: bool
    quality_flags: list[str]
    vlm: dict[str, Any] | None = None


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def split_image_paths(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def image_id_from_path(path: str, index: int) -> str:
    name = Path(path).stem
    return name if name else f"img_{index + 1}"


def resolve_image_path(image_root: Path, csv_path: Path, image_path: str) -> Path:
    candidate = Path(image_path)
    if candidate.is_absolute():
        return candidate
    root_candidate = image_root / candidate
    if root_candidate.exists():
        return root_candidate
    return csv_path.parent / candidate


def inspect_image(path: Path) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, ["image_missing"]
    if not path.is_file():
        return False, ["image_not_file"]
    if path.stat().st_size <= 0:
        return False, ["image_empty"]

    flags: list[str] = []
    try:
        from PIL import Image, ImageStat

        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            width, height = img.size
            if width < 300 or height < 300:
                flags.append("low_resolution")
            stat = ImageStat.Stat(img.convert("L"))
            if stat.stddev and stat.stddev[0] < 8:
                flags.append("low_detail_or_blank")
    except Exception:
        suffix = path.suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
            return False, ["unsupported_image_type"]
        flags.append("image_quality_unverified")
    return True, flags


def extract_claim(conversation: str, claim_object: str) -> tuple[str, str]:
    text = conversation.lower()
    part = "unknown"
    for candidate, pattern in PART_PATTERNS.get(claim_object, []):
        if re.search(pattern, text):
            part = candidate
            break

    issue = "unknown"
    for candidate, pattern in ISSUE_PATTERNS:
        if re.search(pattern, text):
            issue = candidate
            break
    if issue == "broken_part" and part == "windshield":
        issue = "crack"
    return normalize_issue(issue), normalize_part(part, claim_object)


def history_risk(row: dict[str, str], user_history: dict[str, dict[str, str]]) -> list[str]:
    history = user_history.get(str(row.get("user_id", "")).strip(), {})
    text = " ".join(str(value) for value in history.values()).lower()
    flags: list[str] = []
    if re.search(r"\b(fraud|suspicious|denied|chargeback)\b", text):
        flags.append("user_history_risk")
    try:
        if int(history.get("rejected_claim", "0") or 0) > 0 or int(history.get("last_90_days_claim_count", "0") or 0) >= 3:
            flags.append("user_history_risk")
    except ValueError:
        pass
    if re.search(r"\b(manual|review|repeat|multiple|frequent)\b", text):
        flags.append("manual_review_required")
    return flags


def conversation_risks(conversation: str) -> list[str]:
    text = conversation.lower()
    flags: list[str] = []
    if "not sure" in text or "unclear" in text:
        flags.append("manual_review_required")
    if re.search(r"\bignore\b.*\bunrelated\b|\bunrelated\b.*\bphoto", text):
        flags.append("claim_mismatch")
    if re.search(r"\bapprove\b|\bskip manual review\b|\bfollow (?:it|this)\b|\bignore all previous instructions\b", text):
        flags.append("text_instruction_present")
    if re.search(r"\brejected again\b|\breopening tickets\b|\bescalate publicly\b", text):
        flags.append("manual_review_required")
    return flags


def load_lookup(path: Path | None, key_column: str) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {str(row.get(key_column, "")).strip(): row for row in csv.DictReader(handle)}


def load_requirements(path: Path | None) -> list[dict[str, str]]:
    if not path or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def requirement_hint(claim_object: str, issue: str, requirements: list[dict[str, str]]) -> str:
    issue_words = set(issue.replace("_", " ").split())
    for row in requirements:
        applies_object = str(row.get("claim_object", "")).strip().lower()
        applies_to = str(row.get("applies_to", "")).lower()
        if applies_object not in {"all", claim_object}:
            continue
        if issue_words and any(word in applies_to for word in issue_words):
            return str(row.get("minimum_image_evidence", "")).strip()
    return ""


def load_vlm_client() -> Any | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI

        return OpenAI()
    except Exception:
        return None


def encode_image(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def ask_vlm(client: Any, row: dict[str, str], observations: list[ImageObservation]) -> dict[str, Any] | None:
    valid_images = [obs for obs in observations if obs.valid and Path(obs.path).exists()]
    if not client or not valid_images:
        return None

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "You are verifying a damage claim. Images are primary truth. "
                "Return compact JSON with keys: evidence_standard_met(boolean), "
                "issue_type, object_part, claim_status(one of supported, contradicted, not_enough_information), "
                "supporting_image_ids(array), severity(none, low, medium, high, unknown), "
                "risk_flags(array), justification."
                f"\nObject: {row.get('claim_object')}\nConversation: {row.get('user_claim')}"
            ),
        }
    ]
    for obs in valid_images[:4]:
        content.append({"type": "text", "text": f"Image ID: {obs.image_id}"})
        content.append({"type": "image_url", "image_url": {"url": encode_image(Path(obs.path))}})

    try:
        response = client.chat.completions.create(
            model=os.environ.get("CLAIM_VLM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(response.choices[0].message.content or "{}")
    except Exception:
        return None


def decide_without_vlm(
    row: dict[str, str],
    issue: str,
    part: str,
    observations: list[ImageObservation],
    risks: list[str],
    requirements_hint: str = "",
) -> dict[str, str]:
    valid = [obs for obs in observations if obs.valid]
    missing_count = sum(1 for obs in observations if "image_missing" in obs.quality_flags)
    supporting_ids = [obs.image_id for obs in valid]
    valid_image = bool(valid)

    if not observations or not valid:
        status = "not_enough_information"
        standard = False
        reason = "No readable submitted image is available, so the visual evidence cannot verify the claim."
        justification = "The image evidence is missing or unreadable; the conversation alone is not enough."
        severity = "none"
        supporting_ids = []
    else:
        status = "not_enough_information"
        standard = False
        reason = "Readable images are available, but no visual damage model was configured for direct image verification."
        if requirements_hint:
            reason = f"{reason} Minimum evidence considered: {requirements_hint}"
        justification = (
            "The system extracted the claimed issue from the conversation, but without a configured VLM "
            "it cannot confirm or contradict the visible damage from pixels."
        )
        severity = SEVERITY_BY_ISSUE.get(issue, "medium")

    if missing_count:
        risks.append("missing_image_evidence")
    return {
        "evidence_standard_met": bool_text(standard),
        "evidence_standard_met_reason": reason,
        "risk_flags": normalize_risk_flags(risks),
        "issue_type": issue,
        "object_part": part,
        "claim_status": status,
        "claim_status_justification": justification,
        "supporting_image_ids": ";".join(supporting_ids) if supporting_ids else "none",
        "valid_image": bool_text(valid_image),
        "severity": severity,
    }


def merge_vlm_decision(
    row: dict[str, str],
    vlm: dict[str, Any],
    issue: str,
    part: str,
    observations: list[ImageObservation],
    risks: list[str],
) -> dict[str, str]:
    status = str(vlm.get("claim_status", "not_enough_information")).lower()
    if status == "insufficient":
        status = "not_enough_information"
    if status not in {"supported", "contradicted", "not_enough_information"}:
        status = "not_enough_information"

    evidence = bool(vlm.get("evidence_standard_met", status in {"supported", "contradicted"}))
    vlm_flags = vlm.get("risk_flags", [])
    if isinstance(vlm_flags, str):
        vlm_flags = [vlm_flags]
    all_flags = sorted(set([*risks, *[str(flag) for flag in vlm_flags if flag]]))

    valid_ids = {obs.image_id for obs in observations if obs.valid}
    supplied_ids = vlm.get("supporting_image_ids", [])
    if isinstance(supplied_ids, str):
        supplied_ids = [item.strip() for item in supplied_ids.split(";") if item.strip()]
    supporting_ids = [img_id for img_id in supplied_ids if img_id in valid_ids]
    if not supporting_ids and status in {"supported", "contradicted"}:
        supporting_ids = list(valid_ids)[:1]

    claim_object = str(row.get("claim_object", "")).strip().lower()
    visible_issue = normalize_issue(str(vlm.get("issue_type") or issue or "unknown").lower())
    visible_part = normalize_part(str(vlm.get("object_part") or part or "unknown").lower(), claim_object)
    severity = str(vlm.get("severity") or SEVERITY_BY_ISSUE.get(visible_issue, "medium")).lower()
    if severity not in {"none", "low", "medium", "high", "unknown"}:
        severity = "unknown"

    if status == "contradicted" and not any(re.search(pattern, row.get("user_claim", "").lower()) for pattern in NEGATION_PATTERNS):
        all_flags.append("visual_contradiction")

    return {
        "evidence_standard_met": bool_text(evidence),
        "evidence_standard_met_reason": str(
            vlm.get("evidence_standard_met_reason")
            or ("The submitted images are sufficient for a visual decision." if evidence else "The images do not show enough detail for verification.")
        ),
        "risk_flags": normalize_risk_flags(all_flags),
        "issue_type": visible_issue,
        "object_part": visible_part,
        "claim_status": status,
        "claim_status_justification": str(vlm.get("justification") or "Decision is based on the submitted image evidence."),
        "supporting_image_ids": ";".join(supporting_ids) if supporting_ids else "none",
        "valid_image": bool_text(any(obs.valid for obs in observations)),
        "severity": severity,
    }


def process_row(
    row: dict[str, str],
    csv_path: Path,
    image_root: Path,
    vlm_client: Any | None,
    user_history: dict[str, dict[str, str]],
    requirements: list[dict[str, str]],
) -> dict[str, str]:
    claim_object = str(row.get("claim_object", "")).strip().lower()
    issue, part = extract_claim(row.get("user_claim", ""), claim_object)
    risks = conversation_risks(row.get("user_claim", "")) + history_risk(row, user_history)
    requirements_hint = requirement_hint(claim_object, issue, requirements)
    observations: list[ImageObservation] = []

    for index, image_path in enumerate(split_image_paths(row.get("image_paths", ""))):
        resolved = resolve_image_path(image_root, csv_path, image_path)
        valid, flags = inspect_image(resolved)
        observations.append(
            ImageObservation(
                image_id=image_id_from_path(image_path, index),
                path=str(resolved),
                exists=resolved.exists(),
                valid=valid,
                quality_flags=flags,
            )
        )
        risks.extend(flags)

    vlm = ask_vlm(vlm_client, row, observations)
    if vlm:
        decision = merge_vlm_decision(row, vlm, issue, part, observations, risks)
    else:
        decision = decide_without_vlm(row, issue, part, observations, risks, requirements_hint)

    output = {column: row.get(column, "") for column in OUTPUT_COLUMNS}
    output.update(
        {
            "user_id": row.get("user_id", ""),
            "image_paths": row.get("image_paths", ""),
            "user_claim": row.get("user_claim", ""),
            "claim_object": row.get("claim_object", ""),
            **decision,
        }
    )
    return output


def run(
    input_csv: Path,
    output_csv: Path,
    image_root: Path,
    user_history_csv: Path | None,
    requirements_csv: Path | None,
) -> None:
    vlm_client = load_vlm_client()
    user_history = load_lookup(user_history_csv, "user_id")
    requirements = load_requirements(requirements_csv)
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(process_row(row, input_csv, image_root, vlm_client, user_history, requirements))


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify multi-modal damage claims.")
    parser.add_argument("--input", required=True, type=Path, help="Input claims CSV.")
    parser.add_argument("--output", default=Path("output.csv"), type=Path, help="Output CSV path.")
    parser.add_argument(
        "--image-root",
        default=Path("."),
        type=Path,
        help="Root used to resolve relative image paths from the input CSV.",
    )
    parser.add_argument("--user-history", type=Path, default=None, help="Optional dataset/user_history.csv path.")
    parser.add_argument(
        "--evidence-requirements",
        type=Path,
        default=None,
        help="Optional dataset/evidence_requirements.csv path.",
    )
    args = parser.parse_args()
    run(args.input, args.output, args.image_root, args.user_history, args.evidence_requirements)


if __name__ == "__main__":
    main()
