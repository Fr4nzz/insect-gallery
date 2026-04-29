#!/usr/bin/env python3
"""Build gallery dataset JSON from Insect_AI_Classification data files.

Reads manifest + curation data, merges into a unified dataset, and outputs:
  - public/data/dataset_summary.json  (aggregate stats)
  - public/data/dataset.json          (~10K sample, all curated + random rest)
"""

import json
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

# Paths
BASE = Path("/home/ubuntu/franz/repos/Insect_AI_Classification/data")
MANIFEST_BIOTROVE = BASE / "manifest_biotrove.json"
MANIFEST_GBIF = BASE / "manifest_gbif_gapfill.json"
AUDIT_RESULTS = BASE / "biotrove_audit" / "audit_results.json"
CURATION_GBIF = BASE / "curation_gbif_gapfill.json"
CURATION_BIOTROVE_DIR = BASE  # curation_biotrove_*_checkpoint.json files

OUT_DIR = Path("/home/ubuntu/franz/repos/insect-gallery/public/data")

SAMPLE_TARGET = 40_000      # total sample size cap (keeps page load fast)
KEEPS_PER_FAMILY = 30       # cap "keep" samples per family (prevents Lepidoptera dominance)
SEED = 42


def make_thumbnail_url(url: str) -> str:
    """Replace /medium. with /small. in iNaturalist S3 URLs for thumbnails."""
    return re.sub(r"/medium\.", "/small.", url)


def extract_id_from_path(path: str) -> str:
    """Extract the photo/gbif ID from a save_path or curation path.

    Handles patterns like:
      .../219511694.jpg        -> 219511694
      .../gbif_2248802755.jpg  -> 2248802755
    """
    basename = os.path.basename(path)
    name = os.path.splitext(basename)[0]
    if name.startswith("gbif_"):
        return name[5:]
    return name


# As of the prompt-tightening pass, Claude / Codex emit BARE reject labels
# ("larva", "quality", "other", ...) instead of the historical "drop_larva",
# "drop_quality", "drop_other", ... convention used by Gemini v1/v2/v3, Pro
# recurations, and the gallery UI (filter dropdowns, badge logic). To avoid
# touching all those downstream consumers, normalise at the load boundary:
# bare -> drop_*. Idempotent for already-prefixed labels and for "keep".
_BARE_TO_DROP = {
    "larva": "drop_larva",
    "pupa": "drop_pupa",
    "dead": "drop_dead",
    "habitat": "drop_habitat",
    "quality": "drop_quality",
    "not_insect": "drop_not_insect",
    "multiple": "drop_multiple",
    "other": "drop_other",
}


def normalize_curation_label(label):
    """Translate bare reject labels back to the drop_* form the gallery expects.

    Pass-through for None, "keep", and already-prefixed "drop_*" labels."""
    if not isinstance(label, str):
        return label
    return _BARE_TO_DROP.get(label, label)


def load_json(path: Path) -> any:
    print(f"  Loading {path.name} ...", end=" ")
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        print(f"{len(data)} entries")
    elif isinstance(data, dict) and "results" in data:
        print(f"{len(data['results'])} results")
    else:
        print("loaded")
    return data


def build_curation_lookup(results: list, source_label: str) -> dict:
    """Build a dict mapping ID -> curation info from audit/curation results."""
    lookup = {}
    prefix = "audited" if source_label == "biotrove" else "curated"
    for r in results:
        # Extract ID from path or gbif_id field
        entry_id = None
        if "gbif_id" in r:
            entry_id = str(r["gbif_id"])
        elif "path" in r:
            entry_id = extract_id_from_path(r["path"])

        if entry_id is None:
            continue

        action = r.get("action", "keep").lower()
        if action in ("keep", "crop_and_keep"):
            status = f"{prefix}_keep"
        elif action == "drop":
            status = f"{prefix}_drop"
        else:
            status = f"{prefix}_review"

        issues = r.get("issues", [])
        if isinstance(issues, list):
            issues_str = "; ".join(str(i) for i in issues) if issues else ""
        else:
            issues_str = str(issues)

        lookup[entry_id] = {
            "curation_status": status,
            "curation_issues": issues_str,
            "curation_confidence": r.get("confidence", None),
            "life_stage": r.get("life_stage", ""),
        }
    return lookup


def main():
    print("Building insect gallery dataset...\n")

    # Load all data
    biotrove = load_json(MANIFEST_BIOTROVE)
    gbif = load_json(MANIFEST_GBIF)
    audit_data = load_json(AUDIT_RESULTS)
    curation_data = load_json(CURATION_GBIF)

    # Build curation lookups
    print("\n  Building curation lookups...")
    audit_lookup = build_curation_lookup(audit_data["results"], "biotrove")
    gbif_curation_lookup = build_curation_lookup(curation_data["results"], "gbif")
    print(f"    Audit lookup: {len(audit_lookup)} entries")
    print(f"    GBIF curation lookup: {len(gbif_curation_lookup)} entries")

    # Load current BioTrove curation results (from gemini-3-flash-preview runs)
    biotrove_curation_lookup = {}
    for cp_file in sorted(CURATION_BIOTROVE_DIR.glob("curation_biotrove_*_checkpoint.json")):
        cp_data = load_json(cp_file)
        for rel_key, result in cp_data.items():
            # rel_key = "Order/Family/filename.jpg" -> extract photo_id from filename
            filename = os.path.basename(rel_key)
            photo_id = os.path.splitext(filename)[0]
            if photo_id.startswith("gbif_"):
                photo_id = photo_id[5:]

            label = result.get("label", "keep")
            if label == "keep":
                status = "curated_keep"
            elif label.startswith("drop"):
                status = "curated_drop"
            else:
                status = "curated_review"

            # Was this image touched by Pro re-curation?
            pro = result.get("pro_recurate")
            # Determine the "authoritative" model for the current label:
            #   - If Pro reviewed this image, Pro is authoritative (rescued or confirmed drop)
            #   - Otherwise the original Flash verdict stands
            if pro:
                # Was the current label changed by Pro? (rescued: drop_X -> keep,
                # or relabeled: drop_X -> drop_Y)
                flash_was = pro.get("flash_label_was")
                if label == "keep" and flash_was and flash_was.startswith("drop"):
                    pro_outcome = "rescued"           # Pro promoted to keep
                elif flash_was and label != flash_was:
                    pro_outcome = "relabeled_drop"    # Pro changed drop reason
                else:
                    pro_outcome = "confirmed_drop"    # Pro agreed with Flash
                authoritative_model = "gemini-3.1-pro-preview"
            else:
                pro_outcome = None
                authoritative_model = "gemini-3-flash-preview"

            biotrove_curation_lookup[photo_id] = {
                "curation_status": status,
                "curation_issues": label if label != "keep" else "",
                "curation_confidence": result.get("confidence"),
                "life_stage": "",
                "curation_model": authoritative_model,
                "pro_reviewed": bool(pro),
                "pro_outcome": pro_outcome,                                  # rescued / relabeled_drop / confirmed_drop / null
                "pro_label": pro.get("pro_label") if pro else None,          # what Pro said (keep, drop_X, ...)
                "pro_confidence": pro.get("pro_confidence") if pro else None,
                "pro_reason": pro.get("pro_reason") if pro else None,        # short text justification
                "flash_label_was": pro.get("flash_label_was") if pro else None,
                "rel_key": rel_key,
            }
    if biotrove_curation_lookup:
        print(f"    BioTrove full curation lookup: {len(biotrove_curation_lookup)} entries")

    # Load segmentation/detection filter confidence per image.
    # Two interchangeable producers — YOLO v12 (fast, insect-specific) preferred,
    # falling back to SAM3 (slow, generic). Whichever ran most recently wins
    # per-image; both are surfaced in the gallery.
    # v3 curation: Gemini 3 Flash second pass with YOLO context burned in.
    # Each entry has label / confidence / use_yolo_crop / reasoning.
    v3_lookup = {}
    v3_path = BASE / "curation_v3.json"
    if v3_path.exists():
        v3_raw = load_json(v3_path)
        for rel_key, entry in v3_raw.items():
            base = os.path.basename(rel_key)
            photo_id = os.path.splitext(base)[0]
            if photo_id.startswith("gbif_"):
                photo_id = photo_id[5:]
            v3_lookup[photo_id] = {
                "v3_label": entry.get("label"),
                "v3_confidence": entry.get("confidence"),
                "v3_use_yolo_crop": entry.get("use_yolo_crop"),
                "v3_reasoning": entry.get("reasoning"),
            }
        print(f"    v3 curation lookup: {len(v3_lookup)} entries")

    # OpenAI Codex sweep: same 45 images run at 3 models × 2 efforts via
    # `codex exec` CLI (subscription auth). Field naming normalises model
    # IDs (gpt-5.4 -> gpt54, gpt-5.4-mini -> gpt54mini, etc.) so JS keys
    # don't need quoting.
    codex_lookup = {}
    codex_combos = [
        ("gpt-54",       "gpt54",      "low"),
        ("gpt-54",       "gpt54",      "medium"),
        ("gpt-54-mini",  "gpt54mini",  "low"),
        ("gpt-54-mini",  "gpt54mini",  "medium"),
        ("gpt-53-codex", "gpt53codex", "low"),
        ("gpt-53-codex", "gpt53codex", "medium"),
    ]
    for file_model, short_model, effort in codex_combos:
        path = BASE / f"curation_codex_{file_model}_{effort}.json"
        if not path.exists():
            continue
        raw = load_json(path)
        for rel_key, entry in raw.items():
            photo_id = os.path.splitext(os.path.basename(rel_key))[0]
            if photo_id.startswith("gbif_"):
                photo_id = photo_id[5:]
            codex_lookup.setdefault(photo_id, {})[f"codex_{short_model}_{effort}_label"] = normalize_curation_label(entry.get("label"))
            codex_lookup[photo_id][f"codex_{short_model}_{effort}_confidence"] = entry.get("confidence")
            if "use_yolo_crop" in entry:
                codex_lookup[photo_id][f"codex_{short_model}_{effort}_use_yolo_crop"] = entry.get("use_yolo_crop")
            if entry.get("reason"):
                codex_lookup[photo_id][f"codex_{short_model}_{effort}_reason"] = entry.get("reason")
        print(f"    Codex {file_model}/{effort}: {len(raw)} entries")

    # Claude Opus 4.7 smoke test: same 45 images run at 3 effort levels
    # (low / medium / high) via `claude -p` CLI shellout. Lets us spot-check
    # whether more reasoning produces different verdicts on the same input.
    claude_lookup = {}
    # Sources for Claude curation, in order of priority. Smoke-test files
    # (45 images × 3 effort levels) populate claude_low/medium/high. The
    # Plecoptera 300-image full-family curation (single effort=low) only
    # populates claude_low, but it overlaps with the Codex comparison
    # manifest so we get Claude vs Codex on the same images.
    claude_sources = [
        ("low",    "curation_claude_smoketest_low.json"),
        ("medium", "curation_claude_smoketest_medium.json"),
        ("high",   "curation_claude_smoketest_high.json"),
        ("low",    "curation_claude_low_plecoptera.json"),
    ]
    # Auto-discover sharded outputs from larger runs so future tests
    # (e.g. _1k_test_shard0of5.json ... _shard4of5.json) get picked up
    # without editing this list. Each shard infers effort from "low"|"medium"|
    # "high" in its filename; defaults to "low".
    #
    # Sort by mtime DESCENDING — newest first — so when two runs cover the
    # same images (e.g. _tsv_450 reprocesses ids that appear in _1k_test),
    # the newer / better-method run wins via the "first slot wins" dedup
    # logic below. The hardcoded smoketest list above still loads first.
    for shard_path in sorted(
        BASE.glob("curation_claude_*_shard*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        if any(shard_path.name == fname for _, fname in claude_sources):
            continue
        name = shard_path.name
        if "_medium_" in name or name.startswith("curation_claude_medium"):
            shard_effort = "medium"
        elif "_high_" in name or name.startswith("curation_claude_high"):
            shard_effort = "high"
        else:
            shard_effort = "low"
        claude_sources.append((shard_effort, shard_path.name))
    for effort, fname in claude_sources:
        path = BASE / fname
        if not path.exists():
            continue
        raw = load_json(path)
        for rel_key, entry in raw.items():
            photo_id = os.path.splitext(os.path.basename(rel_key))[0]
            if photo_id.startswith("gbif_"):
                photo_id = photo_id[5:]
            # Don't overwrite if already populated (smoke-test files take
            # precedence over the Plecoptera bulk file for any image
            # appearing in both).
            slot = claude_lookup.setdefault(photo_id, {})
            if slot.get(f"claude_{effort}_label"):
                continue
            slot[f"claude_{effort}_label"] = normalize_curation_label(entry.get("label"))
            slot[f"claude_{effort}_confidence"] = entry.get("confidence")
            # New v2 schema fields (only present on the latest run; gracefully
            # absent on older smoketest files):
            if "use_yolo_crop" in entry:
                claude_lookup[photo_id][f"claude_{effort}_use_yolo_crop"] = entry.get("use_yolo_crop")
            if entry.get("reason"):
                claude_lookup[photo_id][f"claude_{effort}_reason"] = entry.get("reason")
        print(f"    Claude {effort} smoke-test lookup: {len(raw)} entries")

    # Gemini 3.1 Flash Lite, ONE image per request (no grid). Drop-in
    # replacement for the gridded Pro curator that the Neocyba metrosideros
    # adjudication showed gets boosted accuracy from single-image input.
    #
    # We bucket per `thinkingLevel` (off/low/medium/high) by parsing the
    # FILENAME, since the `effort` field inside older JSON files is wrong
    # (they say "low" even when no thinking config was sent at all). The
    # filename convention from scripts/curate_with_flash_lite.py is:
    #   curation_flash_lite_singleimg_<effort>_<timestamp>.json  (newer)
    #   curation_flash_lite_singleimg_<timestamp>.json          (older = "off")
    flash_lite_lookup = {}
    import re as _re
    for path in sorted(BASE.glob("curation_flash_lite_*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True):
        # Three filename patterns:
        #   curation_flash_lite_singleimg_<effort>_<ts>.json          (effort-tagged)
        #   curation_flash_lite_singleimg_<ts>.json                   (legacy = "off")
        #   curation_flash_lite_seg_<mode>_<effort>_<ts>.json         (segments experiment)
        m_seg = _re.match(
            r"curation_flash_lite_seg_(?P<mode>single|multi)_"
            r"(?P<eff>minimal|low|medium|high)_[\d_]+\.json$",
            path.name,
        )
        if m_seg:
            field_prefix = f"flash_lite_seg_{m_seg.group('mode')}_{m_seg.group('eff')}"
        else:
            m = _re.match(
                r"curation_flash_lite_singleimg_(?P<eff>off|low|medium|high)_[\d_]+\.json$",
                path.name,
            )
            if m:
                field_prefix = f"flash_lite_{m.group('eff')}"
            elif _re.match(r"curation_flash_lite_singleimg_[\d_]+\.json$", path.name):
                field_prefix = "flash_lite_off"
            else:
                continue
        try:
            raw = load_json(path)
        except Exception:
            continue
        for rel_key, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            photo_id = os.path.splitext(os.path.basename(rel_key))[0]
            if photo_id.startswith("gbif_"):
                photo_id = photo_id[5:]
            slot = flash_lite_lookup.setdefault(photo_id, {})
            key_label = f"{field_prefix}_label"
            if slot.get(key_label):  # newest-first wins per bucket
                continue
            slot[key_label] = normalize_curation_label(entry.get("label"))
            slot[f"{field_prefix}_confidence"] = entry.get("confidence")
            if "use_yolo_crop" in entry:
                slot[f"{field_prefix}_use_yolo_crop"] = entry.get("use_yolo_crop")
            if "keep_segments" in entry:  # legacy schema (s)
                slot[f"{field_prefix}_keep_segments"] = entry.get("keep_segments")
            if "keep_full" in entry:  # new schema: kf (full-coverage)
                slot[f"{field_prefix}_keep_full"] = entry.get("keep_full")
            if "keep_partial" in entry:  # new schema: kp (partial-coverage)
                slot[f"{field_prefix}_keep_partial"] = entry.get("keep_partial")
            if "use_full_image" in entry:
                slot[f"{field_prefix}_use_full_image"] = entry.get("use_full_image")
            if entry.get("reason"):
                slot[f"{field_prefix}_reason"] = entry.get("reason")
        print(f"    Flash Lite [{field_prefix}] lookup: {len(raw)} entries from {path.name}")

    # Gemini 3.1 Pro batch curation. Same image manifest as Claude (the
    # diverse-300 stratified sample). Each entry records its `effort`
    # (low/medium/high) so we key the field names by effort — same pattern
    # as Claude's claude_low/medium/high. Lets the gallery show all efforts
    # side-by-side and surface within-model disagreement.
    gemini_pro_lookup = {}
    for path in sorted(BASE.glob("curation_gemini_pro_*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            raw = load_json(path)
        except Exception:
            continue
        for rel_key, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            photo_id = os.path.splitext(os.path.basename(rel_key))[0]
            if photo_id.startswith("gbif_"):
                photo_id = photo_id[5:]
            effort = entry.get("effort", "low")
            slot = gemini_pro_lookup.setdefault(photo_id, {})
            key_label = f"gemini_pro_{effort}_label"
            if slot.get(key_label):  # newest-first wins per effort
                continue
            slot[key_label] = normalize_curation_label(entry.get("label"))
            slot[f"gemini_pro_{effort}_confidence"] = entry.get("confidence")
            if "use_yolo_crop" in entry:
                slot[f"gemini_pro_{effort}_use_yolo_crop"] = entry.get("use_yolo_crop")
            if entry.get("reason"):
                slot[f"gemini_pro_{effort}_reason"] = entry.get("reason")
        print(f"    Gemini Pro lookup: {len(raw)} entries from {path.name}")

    sam3_lookup = {}
    yolo_lookup = {}
    for fname, lookup, prefix in (
        (BASE / "yolo_v12_crops_summary.json", "yolo", "yolo"),
        (BASE / "sam3_crops_summary.json", "sam3", "sam3"),
    ):
        if not fname.exists():
            continue
        data = load_json(fname)
        target = yolo_lookup if prefix == "yolo" else sam3_lookup
        for rel_key, entry in data.items():
            base = os.path.basename(rel_key)
            photo_id = os.path.splitext(base)[0]
            if photo_id.startswith("gbif_"):
                photo_id = photo_id[5:]
            row = {
                f"{prefix}_confidence": entry.get("best_conf", 0.0),
                f"{prefix}_kept": entry.get("kept", False),
                f"{prefix}_reason": entry.get("reason"),
            }
            # Bboxes in original pixel coords. The gallery normalizes against
            # naturalWidth/Height at render time, so we don't need image_size
            # here. We keep the BEST det for the primary overlay, plus up to
            # 4 others to visualize NMS / multi-insect frames.
            #
            # bbox_orig_xyxy is only populated for kept entries by the python
            # filter script. For below_threshold and no_detection cases we
            # fall back to the highest-score box in all_dets, so the user can
            # still see what YOLO was looking at — this is the whole point of
            # the gallery: spot-check whether YOLO generalizes to nature shots
            # vs the white-background light-trap photos it was trained on.
            all_dets = sorted(
                entry.get("all_dets") or [],
                key=lambda d: -d.get("score", 0),
            )

            # NMS-dedup at IoU 0.5 so the user sees the same numbered
            # bbox set Gemini sees — YOLO sometimes emits near-duplicate
            # detections of the same insect, which makes #2/#3 redundant
            # and the model picks them over the actually-distinct second
            # insect. Same logic as `nms_dedup()` in
            # scripts/curate_with_flash_lite_segments.py.
            def _iou(a, b):
                ax0, ay0, ax1, ay1 = a
                bx0, by0, bx1, by1 = b
                ix0, iy0 = max(ax0, bx0), max(ay0, by0)
                ix1, iy1 = min(ax1, bx1), min(ay1, by1)
                iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
                inter = iw * ih
                if inter == 0: return 0.0
                aa = max(0, ax1 - ax0) * max(0, ay1 - ay0)
                bb = max(0, bx1 - bx0) * max(0, by1 - by0)
                u = aa + bb - inter
                return inter / u if u > 0 else 0.0
            deduped = []
            for d in all_dets:
                if any(_iou(d["xyxy"], k["xyxy"]) > 0.5 for k in deduped):
                    continue
                deduped.append(d)

            # Drop tiny noise bboxes — same rule the curator script uses
            # so the gallery's numbered overlay matches what Gemini saw.
            # Drop any bbox whose area is < 50% of the best (#1)'s area.
            if deduped:
                def _area(d):
                    x0, y0, x1, y1 = d["xyxy"]
                    return max(0, x1 - x0) * max(0, y1 - y0)
                anchor = _area(deduped[0])
                if anchor > 0:
                    threshold = anchor * 0.5
                    deduped = [d for d in deduped if _area(d) >= threshold]

            best_xyxy = entry.get("bbox_orig_xyxy")
            if not best_xyxy and deduped:
                best_xyxy = deduped[0]["xyxy"]
            if best_xyxy:
                row[f"{prefix}_bbox"] = [round(float(v), 1) for v in best_xyxy]
            if len(deduped) > 1:
                rest = deduped[1:5]
                row[f"{prefix}_other_dets"] = [
                    {
                        "xyxy": [round(float(v), 1) for v in d["xyxy"]],
                        "score": round(float(d.get("score", 0)), 3),
                    }
                    for d in rest
                ]
            # Surface gemini_label so we can compare gemini vs yolo in the UI.
            if "gemini_label" in entry:
                row["gemini_label"] = entry["gemini_label"]
            target[photo_id] = row
        print(f"    {prefix.upper()} confidence lookup: {len(target)} entries")

    # Process BioTrove manifest
    print(f"\n  Processing {len(biotrove)} BioTrove entries...")
    all_records = []
    curated_records = []

    for entry in biotrove:
        photo_id = str(entry.get("photo_id", entry.get("gbif_id", "")))
        url = entry.get("url", "")

        # Prefer full curation (gemini-3-flash-preview) over old audit (flash-lite)
        curation = biotrove_curation_lookup.get(photo_id) or audit_lookup.get(photo_id)

        sam3 = sam3_lookup.get(photo_id, {})
        yolo = yolo_lookup.get(photo_id, {})
        record = {
            "id": photo_id,
            "url": url,
            "thumbnail_url": make_thumbnail_url(url),
            "order": entry.get("order", ""),
            "family": entry.get("family", ""),
            "genus": entry.get("genus", ""),
            "species": entry.get("species", ""),
            "scientific_name": entry.get("scientific_name", ""),
            "common_name": entry.get("common_name", ""),
            "source": "biotrove",
            "curation_status": curation["curation_status"] if curation else "not_curated",
            "curation_issues": curation["curation_issues"] if curation else "",
            "curation_confidence": curation["curation_confidence"] if curation else None,
            "life_stage": curation["life_stage"] if curation else "",
            "curation_model": curation.get("curation_model") if curation else None,
            "pro_reviewed": curation.get("pro_reviewed", False) if curation else False,
            "pro_outcome": curation.get("pro_outcome") if curation else None,
            "pro_label": curation.get("pro_label") if curation else None,
            "pro_confidence": curation.get("pro_confidence") if curation else None,
            "pro_reason": curation.get("pro_reason") if curation else None,
            "flash_label_was": curation.get("flash_label_was") if curation else None,
            "sam3_confidence": sam3.get("sam3_confidence"),
            "sam3_kept": sam3.get("sam3_kept"),
            "sam3_bbox": sam3.get("sam3_bbox"),
            "yolo_confidence": yolo.get("yolo_confidence"),
            "yolo_kept": yolo.get("yolo_kept"),
            "yolo_reason": yolo.get("yolo_reason"),
            "yolo_bbox": yolo.get("yolo_bbox"),
            "yolo_other_dets": yolo.get("yolo_other_dets"),
            "yolo_gemini_label": yolo.get("gemini_label"),
            **(v3_lookup.get(photo_id, {})),
            **(claude_lookup.get(photo_id, {})),
            **(gemini_pro_lookup.get(photo_id, {})),
            **(flash_lite_lookup.get(photo_id, {})),
            **(codex_lookup.get(photo_id, {})),
        }

        all_records.append(record)
        if curation:
            curated_records.append(record)

    # Process GBIF gap-fill manifest
    print(f"  Processing {len(gbif)} GBIF entries...")
    for entry in gbif:
        gbif_id = str(entry.get("gbif_id", ""))
        url = entry.get("url", "")

        curation = gbif_curation_lookup.get(gbif_id, None)
        sam3 = sam3_lookup.get(gbif_id, {})
        yolo = yolo_lookup.get(gbif_id, {})

        # GBIF entries don't have scientific_name/common_name fields
        species = entry.get("species", "")
        genus = entry.get("genus", "")

        record = {
            "id": gbif_id,
            "url": url,
            "thumbnail_url": make_thumbnail_url(url),
            "order": entry.get("order", ""),
            "family": entry.get("family", ""),
            "genus": genus,
            "species": species,
            "scientific_name": species,  # species field has full binomial
            "common_name": "",
            "source": "gbif",
            "curation_status": curation["curation_status"] if curation else "not_curated",
            "curation_issues": curation["curation_issues"] if curation else "",
            "curation_confidence": curation["curation_confidence"] if curation else None,
            "life_stage": curation["life_stage"] if curation else "",
            "sam3_confidence": sam3.get("sam3_confidence"),
            "sam3_kept": sam3.get("sam3_kept"),
            "sam3_bbox": sam3.get("sam3_bbox"),
            "yolo_confidence": yolo.get("yolo_confidence"),
            "yolo_kept": yolo.get("yolo_kept"),
            "yolo_reason": yolo.get("yolo_reason"),
            "yolo_bbox": yolo.get("yolo_bbox"),
            "yolo_other_dets": yolo.get("yolo_other_dets"),
            "yolo_gemini_label": yolo.get("gemini_label"),
            **(v3_lookup.get(photo_id, {})),
            **(claude_lookup.get(photo_id, {})),
            **(gemini_pro_lookup.get(photo_id, {})),
            **(flash_lite_lookup.get(photo_id, {})),
            **(codex_lookup.get(photo_id, {})),
        }

        all_records.append(record)
        if curation:
            curated_records.append(record)

    print(f"\n  Total records: {len(all_records)}")
    print(f"  Curated/audited records: {len(curated_records)}")

    # Build summary stats from ALL records
    print("\n  Computing summary stats...")
    order_counts = Counter(r["order"] for r in all_records)
    family_counts = Counter(r["family"] for r in all_records)
    source_counts = Counter(r["source"] for r in all_records)
    curation_counts = Counter(r["curation_status"] for r in all_records)

    # Top families per order
    families_by_order = defaultdict(Counter)
    for r in all_records:
        families_by_order[r["order"]][r["family"]] += 1

    summary = {
        "total_images": len(all_records),
        "sampled_images": None,  # filled below
        "orders": dict(order_counts.most_common()),
        "families": dict(family_counts.most_common(50)),
        "families_by_order": {
            order: dict(fam_counts.most_common(20))
            for order, fam_counts in sorted(families_by_order.items())
        },
        "sources": dict(source_counts),
        "curation_status": dict(curation_counts),
    }

    # Sample dataset
    # Strategy:
    #   1. Keep ALL "drop_*" curation records — these are the interesting ones to
    #      review (potential mislabels, OOD candidates, life-stage issues). Always
    #      reviewable in full.
    #   2. Sample "keep" records, capped at KEEPS_PER_FAMILY per family so that
    #      one giant family (e.g. Lepidoptera Noctuidae) doesn't dominate.
    #   3. Add uncurated samples only to ensure MIN_PER_ORDER coverage of orders
    #      that haven't been curated yet.
    #   4. If still under SAMPLE_TARGET, top up with random keeps.
    random.seed(SEED)

    drops = [r for r in curated_records if "drop" in (r["curation_status"] or "")]
    keeps = [r for r in curated_records if "drop" not in (r["curation_status"] or "")]

    # Bucket keeps by family
    keeps_by_family = defaultdict(list)
    for r in keeps:
        keeps_by_family[(r["order"], r["family"])].append(r)

    sampled_keeps = []
    for fam_key, fam_records in keeps_by_family.items():
        if len(fam_records) <= KEEPS_PER_FAMILY:
            sampled_keeps.extend(fam_records)
        else:
            sampled_keeps.extend(random.sample(fam_records, KEEPS_PER_FAMILY))

    sampled = list(drops) + sampled_keeps
    sampled_ids = {r["id"] for r in sampled}

    # Ensure minimum representation per order (100 images each)
    MIN_PER_ORDER = 100
    uncurated_by_order = defaultdict(list)
    for r in all_records:
        if r["id"] not in sampled_ids:
            uncurated_by_order[r["order"]].append(r)

    sampled_order_counts = Counter(r["order"] for r in sampled)
    for order, uncurated_list in uncurated_by_order.items():
        current = sampled_order_counts.get(order, 0)
        need = max(0, MIN_PER_ORDER - current)
        if need > 0:
            extra = random.sample(uncurated_list, min(need, len(uncurated_list)))
            sampled.extend(extra)
            for r in extra:
                sampled_ids.add(r["id"])

    # Force-include any record that has Claude smoke-test data OR Codex
    # comparison data, so all 45 imgs surface in the gallery for spot-check.
    def _has_claude(r):
        return any(r.get(f"claude_{e}_label") for e in ("low", "medium", "high"))

    def _has_codex(r):
        for sm in ("gpt54", "gpt54mini", "gpt53codex"):
            for e in ("low", "medium"):
                if r.get(f"codex_{sm}_{e}_label"):
                    return True
        return False

    def _has_gemini_pro(r):
        return any(r.get(f"gemini_pro_{e}_label") for e in ("low", "medium", "high"))

    def _has_flash_lite(r):
        if any(r.get(f"flash_lite_{e}_label") for e in ("off", "low", "medium", "high")):
            return True
        for mode in ("single", "multi"):
            for e in ("minimal", "low", "medium", "high"):
                if r.get(f"flash_lite_seg_{mode}_{e}_label"):
                    return True
        return False

    pinned_ids = {r["id"] for r in all_records
                  if _has_claude(r) or _has_codex(r) or _has_gemini_pro(r)
                  or _has_flash_lite(r)}
    for r in all_records:
        if r["id"] in pinned_ids and r["id"] not in sampled_ids:
            sampled.append(r)
            sampled_ids.add(r["id"])

    # Cap total to SAMPLE_TARGET — drops + smoke-test pins always retained,
    # trim from generic keeps.
    if len(sampled) > SAMPLE_TARGET:
        kept_pinned = [
            r for r in sampled
            if "drop" in (r["curation_status"] or "") or r["id"] in pinned_ids
        ]
        kept_other = [
            r for r in sampled
            if "drop" not in (r["curation_status"] or "") and r["id"] not in pinned_ids
        ]
        budget = max(0, SAMPLE_TARGET - len(kept_pinned))
        if len(kept_other) > budget:
            kept_other = random.sample(kept_other, budget)
        sampled = kept_pinned + kept_other

    random.shuffle(sampled)
    print(f"\n  Sample composition: {sum(1 for r in sampled if 'drop' in (r['curation_status'] or ''))} drops + "
          f"{sum(1 for r in sampled if 'keep' in (r['curation_status'] or '') and r['curation_status'] != 'not_curated')} keeps + "
          f"{sum(1 for r in sampled if r['curation_status'] == 'not_curated')} uncurated")

    summary["sampled_images"] = len(sampled)

    # Sample stats
    sample_order_counts = Counter(r["order"] for r in sampled)
    sample_source_counts = Counter(r["source"] for r in sampled)
    sample_curation_counts = Counter(r["curation_status"] for r in sampled)
    summary["sample_orders"] = dict(sample_order_counts.most_common())
    summary["sample_sources"] = dict(sample_source_counts)
    summary["sample_curation_status"] = dict(sample_curation_counts)

    # Write outputs
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_path = OUT_DIR / "dataset_summary.json"
    print(f"\n  Writing {summary_path} ...")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    dataset_path = OUT_DIR / "dataset.json"
    print(f"  Writing {dataset_path} ({len(sampled)} records)...")
    with open(dataset_path, "w") as f:
        json.dump(sampled, f)

    print(f"\n  Done! Summary: {summary_path}")
    print(f"  Dataset: {dataset_path} ({os.path.getsize(dataset_path) / 1024 / 1024:.1f} MB)")

    # Print key stats
    print(f"\n  === Summary ===")
    print(f"  Total images in pipeline: {len(all_records)}")
    print(f"  Sampled for gallery: {len(sampled)}")
    print(f"  Orders: {len(order_counts)}")
    print(f"  Families: {len(family_counts)}")
    print(f"  Sources: {dict(source_counts)}")
    print(f"  Curation: {dict(curation_counts)}")


if __name__ == "__main__":
    main()
