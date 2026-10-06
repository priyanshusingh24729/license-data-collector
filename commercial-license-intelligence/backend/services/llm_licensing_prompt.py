"""
Authoritative LLM Licensing Prompt and Validation Service.
Implements prompt engineering guidelines and structured output schemas
strictly adhering to Section 11 & Sections 1-10:

- Uses exact application/product/version without hallucinating
- Prevents guessing licensing metrics or inferring licensing from inventory quantities
- Never confuses free software with zero installations
- Never treats missing evidence as proof that software is supported
- Never fabricates EOL/EOS dates or evidence URLs
- Prioritizes official vendor sources
- Returns structured JSON validated via LicenseValidationLayer
- Enforces strict cross-field consistency
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List, Union

from backend.validation.license_validation_layer import (
    LicenseValidationLayer,
    ALLOWED_METRICS,
    ALLOWED_LICENSE_MODELS,
    ALLOWED_CLASSIFICATIONS,
)
from backend.inventory.recognition.lifecycle_service import LifecycleService

logger = logging.getLogger(__name__)

LLM_SYSTEM_PROMPT = """You are the Senior Commercial Software License Intelligence Auditor.
Your objective is to produce factually accurate, evidence-backed software licensing intelligence.

STRICT OPERATIONAL RULES:

1. EXACT IDENTITY:
- You must evaluate the software using the EXACT application name, product, and version provided.
- Do NOT substitute a different product or make assumptions about unstated editions.

2. LICENSE REQUIRED (Strict YES or NO only):
- Must contain ONLY "YES" or "NO".
- Never return "UNKNOWN", "CONTEXT_DEPENDENT", "N/A", or blank.
- Genuine commercial entitlement or paid software required -> "YES".
- Genuine free / open-source / no-license-required software under relevant terms -> "NO".
- CRITICAL: Never determine "License Required" from inventory quantity (e.g. quantity=0 does NOT mean free or no license required).

3. LICENSING METRIC (Controlled Vocabulary):
- Allowed values:
  * "Users"
  * "Devices"
  * "Installations"
  * "Concurrent Users"
  * "Concurrent Devices"
  * "CAL"
  * "PVU"
  * "Processor Cores"
  * "Processors"
  * "No License Required"
  * "" (leave blank if not reliably established)
- CRITICAL: Do NOT infer Metric from a numeric inventory quantity (e.g., Quantity = 0 must NEVER cause Metric = "Users").
- The Metric represents the licensing entitlement unit, NOT the installation count.
- If License Required = "NO", Metric MUST be "No License Required".
- If the licensing metric cannot be established from reliable evidence, leave it as "" (blank). Never guess.

4. LICENSE MODEL (Logically Matches Metric):
- Allowed values:
  * "Per User"
  * "Per Device"
  * "Per Installation"
  * "Subscription"
  * "Per Core"
  * "Per Processor"
  * "Concurrent User"
  * "Concurrent Device"
  * "CAL"
  * "PVU"
  * "Freeware"
  * "Open Source"
  * "Free / Open Source"
  * "No License Required"
  * "Per Core / Server + CAL"
  * "" (blank)
- Must logically agree with Metric:
  * Metric "Users" -> "Per User" or "Subscription"
  * Metric "Processor Cores" -> "Per Core"
  * Metric "Devices" -> "Per Device"
  * Metric "Installations" -> "Per Installation"
  * Metric "No License Required" -> "No License Required"
- Never return "UNKNOWN". Use "" (blank) if not reliably established.

5. CLASSIFICATION:
- Allowed values: "COMMERCIAL", "OPEN_SOURCE", "FREE", "FREE_AND_PAID", "TRIAL", "OS_BUNDLED", or "" (blank).
- Never return "UNKNOWN". If not reliably established, leave blank "".

6. VERSION-AWARE LIFECYCLE (EOL / EOS):
- Must be version-aware based on the exact version string provided.
- Do NOT assume a product is supported just because modern releases are active.
- Verified currently active / supported -> 0
- Verified End of Life / End of Support -> 1
- No reliable information -> null (do NOT falsely return 0).
- Never fabricate dates or lifecycle milestones.

7. EVIDENCE URL:
- Must be an authoritative official vendor or documentation URL.
- NEVER fabricate URLs.
- NEVER provide search engine links (e.g. google.com, bing.com, duckduckgo.com).
- If no authoritative URL exists, leave as "" (blank).

8. OUTPUT FORMAT:
Output MUST be a single, valid JSON object matching this schema:
{
  "application_name": "<exact or canonical application name>",
  "version": "<exact version string>",
  "os": "<OS string>",
  "license_required": "YES" | "NO",
  "metric": "<controlled metric or blank>",
  "license_model": "<controlled model or blank>",
  "classification": "<controlled classification or blank>",
  "is_end_of_support": 0 | 1 | null,
  "is_end_of_life": 0 | 1 | null,
  "evidence_url": "<official vendor URL or blank>",
  "evidence_summary": "<brief factual justification>"
}
"""


class LLMLicensingPromptService:
    """
    Service providing structured prompt construction, LLM response parsing,
    and rigorous cross-field validation.
    """

    @classmethod
    def get_system_prompt(cls) -> str:
        """Returns the hardened system prompt enforcing all intelligence rules."""
        return LLM_SYSTEM_PROMPT.strip()

    @classmethod
    def build_user_prompt(
        cls,
        application_name: str,
        version: Optional[str] = None,
        operating_system: Optional[str] = "Windows",
        publisher: Optional[str] = None,
        evidence_snippets: Optional[List[str]] = None,
        inventory_quantity: Optional[int] = None,
    ) -> str:
        """
        Builds the user prompt for a specific software inventory item.
        Explicitly warns against inferring licensing facts from inventory quantities.
        """
        prompt_lines = [
            "Please analyze this software inventory record and provide verified licensing intelligence:",
            f"- Application Name: {application_name.strip()}",
            f"- Version: {version.strip() if version else 'N/A'}",
            f"- Operating System: {operating_system.strip() if operating_system else 'Windows'}",
            f"- Publisher / Vendor: {publisher.strip() if publisher else 'UNKNOWN'}",
        ]

        if inventory_quantity is not None:
            prompt_lines.append(
                f"- Inventory Installation Count: {inventory_quantity} "
                "(WARNING: Do NOT use this count to infer licensing metric or license requirement!)"
            )

        if evidence_snippets:
            prompt_lines.append("\nReference Evidence / Context Snippets:")
            for i, snip in enumerate(evidence_snippets[:5], 1):
                clean_s = " ".join(snip.split())
                prompt_lines.append(f"[{i}] {clean_s[:500]}")

        prompt_lines.append(
            "\nReturn ONLY the structured JSON object. Adhere strictly to the controlled vocabularies and validation rules."
        )
        return "\n".join(prompt_lines)

    @classmethod
    def parse_and_validate_response(
        cls,
        raw_response: str,
        fallback_record: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Parses LLM output JSON, extracts the fields, and runs them through
        LicenseValidationLayer to guarantee 100% adherence to consistency rules.
        """
        fallback = fallback_record or {}
        extracted_data: Dict[str, Any] = {}

        # 1. Extract JSON block from markdown fences if present
        clean_text = raw_response.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
        if json_match:
            clean_text = json_match.group(1)
        else:
            # Try raw curly braces
            brace_match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
            if brace_match:
                clean_text = brace_match.group(1)

        try:
            extracted_data = json.loads(clean_text)
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}. Raw content: {raw_response[:200]}")
            extracted_data = {}

        # 2. Extract fields with fallbacks
        app_name = extracted_data.get("application_name") or fallback.get("Application Name") or fallback.get("raw_application") or ""
        ver_val = extracted_data.get("version") or fallback.get("Version") or fallback.get("raw_version") or ""
        os_val = extracted_data.get("os") or fallback.get("OS") or fallback.get("Operating_System") or "Windows"
        
        lic_req = extracted_data.get("license_required") or fallback.get("License Required") or fallback.get("license_required")
        metric_val = extracted_data.get("metric") or fallback.get("Metric") or fallback.get("metric")
        lic_model = extracted_data.get("license_model") or fallback.get("License Model") or fallback.get("license_model")
        class_val = extracted_data.get("classification") or fallback.get("Classification") or fallback.get("classification")
        ev_url = extracted_data.get("evidence_url") or fallback.get("Evidence URL") or fallback.get("evidence_url")
        
        eos_val = extracted_data.get("is_end_of_support")
        eol_val = extracted_data.get("is_end_of_life")

        # 3. Check LifecycleService for authoritative lifecycle if LLM didn't verify
        life_override = None
        if eos_val is None and eol_val is None:
            life_override = LifecycleService.evaluate_lifecycle(
                app_name=str(app_name),
                version=str(ver_val) if ver_val else None,
                publisher=fallback.get("raw_vendor") or fallback.get("canonical_vendor"),
            )

        candidate_record = {
            "Application Name": app_name,
            "Version": ver_val,
            "OS": os_val,
            "License Required": lic_req,
            "Metric": metric_val,
            "License Model": lic_model,
            "Classification": class_val,
            "End of Support": eos_val,
            "End of Life": eol_val,
            "Evidence URL": ev_url,
        }

        # 4. Enforce backend validation rules and sanitize
        validated_record = LicenseValidationLayer.validate_and_sanitize(
            candidate_record,
            lifecycle_override=life_override,
        )

        return validated_record
