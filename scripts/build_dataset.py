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

OUT_DIR = Path("/home/ubuntu/franz/repos/insect-gallery/public/data")

SAMPLE_TARGET = 10_000
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

    # Process BioTrove manifest
    print(f"\n  Processing {len(biotrove)} BioTrove entries...")
    all_records = []
    curated_records = []

    for entry in biotrove:
        photo_id = str(entry.get("photo_id", entry.get("gbif_id", "")))
        url = entry.get("url", "")

        curation = audit_lookup.get(photo_id, None)

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

    # Sample dataset: all curated + random from the rest
    curated_ids = {r["id"] for r in curated_records}
    uncurated = [r for r in all_records if r["id"] not in curated_ids]

    remaining_budget = max(0, SAMPLE_TARGET - len(curated_records))
    random.seed(SEED)
    sampled_uncurated = random.sample(uncurated, min(remaining_budget, len(uncurated)))

    sampled = curated_records + sampled_uncurated
    random.shuffle(sampled)

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
