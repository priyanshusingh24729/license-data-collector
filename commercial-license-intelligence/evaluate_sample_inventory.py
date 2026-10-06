"""
Sample Inventory Evaluation & Verification Script.
Evaluates the updated Commercial License Intelligence pipeline against sample inventory datasets
and computes the 12 required metrics:

1. Total records processed
2. License Required YES count
3. License Required NO count
4. Blank Metric count
5. Metric distribution
6. License Model distribution
7. Classification distribution
8. EOL verified count
9. EOS verified count
10. Missing evidence URL count
11. Validation failures
12. Records corrected by the new logic
"""

import os
import json
import pandas as pd
from typing import Dict, Any, List
from collections import Counter

from backend.inventory.export.standardized_inventory_exporter import (
    StandardizedInventoryExporter,
    FINAL_OUTPUT_COLUMNS,
)
from backend.validation.license_validation_layer import LicenseValidationLayer
from backend.inventory.recognition.lifecycle_service import LifecycleService


def evaluate_dataset(df_raw: pd.DataFrame, dataset_name: str) -> Dict[str, Any]:
    print(f"\n=======================================================")
    print(f"EVALUATING: {dataset_name} ({len(df_raw)} records)")
    print(f"=======================================================")

    records = df_raw.to_dict(orient="records")
    total_records = len(records)

    # Transform through full pipeline
    df_final = StandardizedInventoryExporter.transform_to_final_schema(records)

    # Compute the 12 required metrics
    yes_count = int((df_final["License Required"] == "YES").sum())
    no_count = int((df_final["License Required"] == "NO").sum())

    # Blank metric count: Metric is "" or None or pd.isna
    blank_metric_count = int(df_final["Metric"].apply(lambda x: pd.isna(x) or str(x).strip() in ("", "None", "nan", "NULL")).sum())

    # Metric distribution
    metric_counts = Counter(df_final["Metric"].apply(lambda x: "(blank)" if pd.isna(x) or str(x).strip() in ("", "None", "nan", "NULL") else str(x).strip()))

    # License Model distribution
    model_counts = Counter(df_final["License Model"].apply(lambda x: "(blank)" if pd.isna(x) or str(x).strip() in ("", "None", "nan", "NULL") else str(x).strip()))

    # Classification distribution
    class_counts = Counter(df_final["Classification"].apply(lambda x: "(blank)" if pd.isna(x) or str(x).strip() in ("", "None", "nan", "NULL") else str(x).strip()))

    # EOL verified count (1)
    eol_verified_count = int((df_final["End of Life"] == 1).sum())

    # EOS verified count (1)
    eos_verified_count = int((df_final["End of Support"] == 1).sum())

    # Missing Evidence URL count
    missing_url_count = int(df_final["Evidence URL"].apply(lambda x: pd.isna(x) or str(x).strip() in ("", "None", "nan", "NULL")).sum())

    # Validation failures: records that failed validation or had to be dropped (should be 0)
    validation_failures = 0
    for _, r in df_final.iterrows():
        if r["License Required"] not in ("YES", "NO"):
            validation_failures += 1
        if r["License Required"] == "NO" and r["Metric"] != "No License Required":
            validation_failures += 1
        if r["License Required"] == "NO" and not any(k in str(r["License Model"]) for k in ("Free", "Open Source", "Freeware", "Public Domain", "No License Required")):
            validation_failures += 1

    # Records corrected by new logic: track how many records had fields corrected
    corrected_records_count = 0
    for rec in records:
        app_name = rec.get("Application_Name") or rec.get("Application") or rec.get("raw_application") or rec.get("Name") or ""
        raw_lic = rec.get("License Required") or rec.get("license_required")
        raw_met = rec.get("Metric") or rec.get("metric")
        raw_mod = rec.get("License Model") or rec.get("license_model")
        raw_cls = rec.get("Classification") or rec.get("classification")
        raw_url = rec.get("Evidence URL") or rec.get("evidence_url")

        v = LicenseValidationLayer.validate_and_sanitize({
            "Application Name": app_name,
            "License Required": raw_lic,
            "Metric": raw_met,
            "License Model": raw_mod,
            "Classification": raw_cls,
            "Evidence URL": raw_url,
        })
        if v.get("_corrected_fields"):
            corrected_records_count += 1

    metrics = {
        "dataset_name": dataset_name,
        "total_records": total_records,
        "license_required_yes": yes_count,
        "license_required_no": no_count,
        "blank_metric_count": blank_metric_count,
        "metric_distribution": dict(metric_counts.most_common()),
        "license_model_distribution": dict(model_counts.most_common()),
        "classification_distribution": dict(class_counts.most_common()),
        "eol_verified_count": eol_verified_count,
        "eos_verified_count": eos_verified_count,
        "missing_evidence_url_count": missing_url_count,
        "validation_failures": validation_failures,
        "records_corrected_by_new_logic": corrected_records_count,
    }

    print(f"1. Total Records Processed: {total_records:,}")
    print(f"2. License Required YES: {yes_count:,} ({(yes_count/total_records)*100:.1f}%)")
    print(f"3. License Required NO: {no_count:,} ({(no_count/total_records)*100:.1f}%)")
    print(f"4. Blank Metric Count: {blank_metric_count:,} ({(blank_metric_count/total_records)*100:.1f}%)")
    print("\n5. Metric Distribution:")
    for m, c in metric_counts.most_common():
        print(f"   - {m}: {c:,}")
    print("\n6. License Model Distribution:")
    for lm, c in model_counts.most_common():
        print(f"   - {lm}: {c:,}")
    print("\n6b. License Type Distribution (Legal Family):")
    for lt, c in type_counts.most_common():
        print(f"   - {lt}: {c:,}")
    print("\n7. Classification Distribution:")
    for cl, c in class_counts.most_common():
        print(f"   - {cl}: {c:,}")
    print(f"\n8. EOL Verified (1): {eol_verified_count:,}")
    print(f"9. EOS Verified (1): {eos_verified_count:,}")
    print(f"10. Missing Evidence URL: {missing_url_count:,} ({(missing_url_count/total_records)*100:.1f}%)")
    print(f"11. Validation Failures: {validation_failures:,}")
    print(f"12. Records Corrected by New Logic: {corrected_records_count:,} ({(corrected_records_count/total_records)*100:.1f}%)")

    return metrics


def main():
    results = {}

    # Dataset 1: Uploaded Device Scan Sample (PF490A36_LAPTOP-TTASCMUO_Installation(1).csv)
    p1 = os.path.join("data", "PF490A36_LAPTOP-TTASCMUO_Installation(1).csv")
    if os.path.exists(p1):
        df1 = pd.read_csv(p1)
        results["device_scan_sample"] = evaluate_dataset(df1, "Device Scan Sample (PF490A36)")

    # Dataset 2: Full MVP Benchmark Inventory (mvp_4169_full_license_intelligence.csv)
    p2 = os.path.join("data", "mvp_4169_full_license_intelligence.csv")
    if os.path.exists(p2):
        df2 = pd.read_csv(p2)
        results["mvp_4169_sample"] = evaluate_dataset(df2, "Full Enterprise Inventory (4,169 Apps)")

    with open("data/sample_inventory_evaluation_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nReport exported to data/sample_inventory_evaluation_report.json")


if __name__ == "__main__":
    main()
