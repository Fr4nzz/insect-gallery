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
            best_xyxy = entry.get("bbox_orig_xyxy")
            if not best_xyxy and all_dets:
                best_xyxy = all_dets[0]["xyxy"]
            if best_xyxy:
                row[f"{prefix}_bbox"] = [round(float(v), 1) for v in best_xyxy]
            if len(all_dets) > 1:
                rest = all_dets[1:5]
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

    # Cap total to SAMPLE_TARGET — drops always retained, trim from keeps
    if len(sampled) > SAMPLE_TARGET:
        # Re-derive after additions
        kept_drops = [r for r in sampled if "drop" in (r["curation_status"] or "")]
        kept_other = [r for r in sampled if "drop" not in (r["curation_status"] or "")]
        budget = max(0, SAMPLE_TARGET - len(kept_drops))
        if len(kept_other) > budget:
            kept_other = random.sample(kept_other, budget)
        sampled = kept_drops + kept_other

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
