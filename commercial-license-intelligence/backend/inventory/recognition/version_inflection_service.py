"""
Version-Inflection Engine.
Detects when a software vendor transitioned a product's licensing model across versions
(e.g., Docker Desktop >= 4.0, Terraform >= 1.5.6, Redis >= 7.4, Oracle Java 8u211+, Elasticsearch >= 7.11).
Applies exact version-bound license rules based on the detected product version.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple


@dataclass
class VersionInflectionResult:
    is_inflected: bool
    rule_applied: Optional[str]
    license_model: Optional[str]
    classification: Optional[str]
    license_required: Optional[str]
    metric: Optional[str]
    spdx_id: Optional[str]
    evidence_url: Optional[str] = None
    evidence_quote: Optional[str] = None


class VersionInflectionService:
    """
    Evaluates software versions against historical inflection points where licensing obligations changed.
    """

    @classmethod
    def _parse_version_tuple(cls, ver_str: Optional[str]) -> Tuple[int, ...]:
        """Parses a version string into a comparable integer tuple."""
        if not ver_str:
            return (0, 0, 0)
        # Extract first continuous sequence of digits and dots
        clean = re.sub(r"[^\d\.]", "", ver_str.split("-")[0].split("+")[0].split("_")[0])
        parts = [int(p) for p in clean.split(".") if p.isdigit()]
        return tuple(parts) if parts else (0, 0, 0)

    @classmethod
    def evaluate_version(
        cls,
        app_name: str,
        version: Optional[str],
        publisher: Optional[str] = None,
    ) -> Optional[VersionInflectionResult]:
        """
        Checks if the application and version match a known licensing inflection point.
        Returns VersionInflectionResult if matched, otherwise None.
        """
        if not app_name:
            return None

        low_name = app_name.lower().strip()
        v_str = str(version or "").strip()
        v_tuple = cls._parse_version_tuple(v_str)

        # -------------------------------------------------------------
        # 1. Docker Desktop
        # -------------------------------------------------------------
        if "docker desktop" in low_name:
            # Shift at version 4.0.0 (August 31, 2021)
            if v_tuple >= (4, 0, 0) or not v_str:
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Docker Desktop >= 4.0.0 requires paid commercial subscription (Pro, Team, or Business) for commercial entities >250 employees or >$10M revenue.",
                    license_model="Commercial — Per Seat Subscription",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Users",
                    spdx_id="Proprietary",
                    evidence_url="https://www.docker.com/legal/docker-subscription-service-agreement/",
                    evidence_quote="Docker Desktop requires a paid subscription for commercial entities with more than 250 employees or more than $10 million in annual revenue.",
                )
            else:
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Docker Desktop < 4.0.0 was released under open-source and free terms.",
                    license_model="Free / Open Source",
                    classification="FREE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Apache-2.0",
                    evidence_url="https://www.docker.com/pricing/faq/",
                    evidence_quote="Legacy versions of Docker Desktop prior to 4.0 did not enforce the commercial subscription requirement.",
                )

        # -------------------------------------------------------------
        # 2. HashiCorp Terraform
        # -------------------------------------------------------------
        if re.search(r"\bterraform\b", low_name) and "opentofu" not in low_name:
            # Shift at version 1.5.6 (August 10, 2023: MPL-2.0 -> BSL-1.1)
            if v_tuple >= (1, 5, 6):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Terraform >= 1.5.6 relicensed under Business Source License 1.1 (Source-Available with commercial competitive restrictions).",
                    license_model="BSL-1.1 — Commercial / Source Available",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Named User",
                    spdx_id="BSL-1.1",
                    evidence_url="https://www.hashicorp.com/bsl-faq",
                    evidence_quote="HashiCorp changed the license for Terraform starting with version 1.5.6 from MPL 2.0 to the Business Source License (BSL) v1.1.",
                )
            elif v_tuple > (0, 0, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Terraform < 1.5.6 is licensed under Mozilla Public License 2.0 (Open Source).",
                    license_model="MPL-2.0 — Free/Open Source",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="MPL-2.0",
                    evidence_url="https://github.com/hashicorp/terraform/blob/v1.5.5/LICENSE",
                    evidence_quote="Terraform is licensed under the Mozilla Public License 2.0 for versions up to 1.5.5.",
                )

        # -------------------------------------------------------------
        # 3. Redis
        # -------------------------------------------------------------
        if re.search(r"\bredis\b", low_name) and "valkey" not in low_name and "client" not in low_name:
            # Shift at version 7.4.0 (March 20, 2024: BSD-3 -> RSALv2 / SSPLv1)
            if v_tuple >= (7, 4, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Redis >= 7.4.0 transitioned from BSD-3-Clause to dual RSALv2 / SSPLv1 source-available licenses.",
                    license_model="RSALv2 / SSPL-1.0 — Source Available",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Processor Cores",
                    spdx_id="SSPL-1.0",
                    evidence_url="https://redis.io/legal/licenses/",
                    evidence_quote="Beginning with Redis version 7.4, Redis is licensed under dual RSALv2 and SSPLv1 source-available terms.",
                )
            elif v_tuple > (0, 0, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Redis < 7.4.0 is fully open source under BSD-3-Clause.",
                    license_model="BSD-3-Clause — Free/Open Source",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="BSD-3-Clause",
                    evidence_url="https://redis.io/legal/licenses/",
                    evidence_quote="Redis versions prior to 7.4 remain open source under the 3-Clause BSD License.",
                )

        # -------------------------------------------------------------
        # 4. Elasticsearch
        # -------------------------------------------------------------
        if "elasticsearch" in low_name:
            # Shift 1: 7.11.0 (Feb 2021: Apache 2.0 -> SSPL / Elastic License)
            # Shift 2: 8.15.0 (Aug 2024: AGPLv3 added back)
            if v_tuple >= (8, 15, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Elasticsearch >= 8.15.0 dual-licensed under AGPL-3.0 and Elastic License 2.0.",
                    license_model="AGPL-3.0 — Free/Open Source",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="AGPL-3.0-only",
                    evidence_url="https://www.elastic.co/licensing/elastic-license",
                    evidence_quote="Elasticsearch 8.15+ re-introduced AGPLv3 alongside the Elastic License 2.0.",
                )
            elif v_tuple >= (7, 11, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Elasticsearch 7.11 to 8.14 is licensed under SSPL-1.0 and Elastic License 2.0 (Source-Available).",
                    license_model="SSPL-1.0 — Free to Use",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="SSPL-1.0",
                    evidence_url="https://www.elastic.co/pricing/faq/licensing",
                    evidence_quote="Starting with version 7.11, Elasticsearch source code is under SSPL 1.0 and Elastic License.",
                )
            elif v_tuple > (0, 0, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Elasticsearch < 7.11 is open source under Apache-2.0.",
                    license_model="Apache-2.0 — Free/Open Source",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Apache-2.0",
                    evidence_url="https://www.elastic.co/licensing/elastic-license",
                    evidence_quote="Elasticsearch versions prior to 7.11 were licensed under Apache 2.0.",
                )

        # -------------------------------------------------------------
        # 5. Oracle Java (JDK / JRE)
        # -------------------------------------------------------------
        if ("oracle java" in low_name or "java(tm)" in low_name or "java se" in low_name) and "openjdk" not in low_name:
            # Check Java 8 update number (e.g. 1.8.0_211 or 8u211)
            u_match = re.search(r"(?:1\.8\.0_(\d+)|8u(\d+))", v_str)
            if u_match:
                u_num = int(u_match.group(1) or u_match.group(2))
                if u_num >= 211:
                    return VersionInflectionResult(
                        is_inflected=True,
                        rule_applied=f"Oracle Java 8 update {u_num} (>= 8u211) is licensed under the OTN agreement; requires paid commercial subscription in production.",
                        license_model="Commercial — Per Employee / Named User Plus",
                        classification="COMMERCIAL",
                        license_required="YES",
                        metric="Users",
                        spdx_id="Proprietary",
                        evidence_url="https://www.oracle.com/java/technologies/javase/terms/license/",
                        evidence_quote="Oracle Java 8 release updates after April 16, 2019 (8u211+) require a commercial license for business and production use under the OTN agreement.",
                    )
                else:
                    return VersionInflectionResult(
                        is_inflected=True,
                        rule_applied=f"Oracle Java 8 update {u_num} (<= 8u202) is licensed under the legacy Binary Code License (BCL).",
                        license_model="Freeware — Legacy BCL",
                        classification="FREEWARE",
                        license_required="NO",
                        metric="No License Required",
                        spdx_id="Proprietary",
                        evidence_url="https://www.oracle.com/technetwork/java/javase/terms/license/index.html",
                        evidence_quote="Java SE 8u202 and earlier updates remain under the Binary Code License for personal and commercial desktop use.",
                    )
            # Java 17 to 20: NFTC (No-Fee Terms and Conditions)
            if v_tuple >= (17, 0, 0) and v_tuple < (21, 0, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Oracle Java 17 is under the No-Fee Terms and Conditions (NFTC) license (free for internal business use).",
                    license_model="Free — Oracle NFTC License",
                    classification="FREE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="Proprietary",
                    evidence_url="https://www.oracle.com/downloads/licenses/no-fee-license.html",
                    evidence_quote="Oracle provides the NFTC license for Java 17, allowing free use for development and production.",
                )

        # -------------------------------------------------------------
        # 6. MongoDB
        # -------------------------------------------------------------
        if "mongodb" in low_name and "compass" not in low_name and "enterprise" not in low_name:
            # Shift at version 4.0.0 (October 2018: AGPL-3.0 -> SSPL-1.0)
            if v_tuple >= (4, 0, 0) or not v_str:
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="MongoDB >= 4.0.0 is under the Server Side Public License (SSPL-1.0). Free to run internally.",
                    license_model="SSPL-1.0 — Free to Use",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="SSPL-1.0",
                    evidence_url="https://www.mongodb.com/licensing/server-side-public-license",
                    evidence_quote="MongoDB Community Server 4.0+ is licensed under the Server Side Public License v1.",
                )
            else:
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="MongoDB < 4.0.0 is licensed under GNU AGPL-3.0.",
                    license_model="AGPL-3.0 — Free/Open Source",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="AGPL-3.0-only",
                    evidence_url="https://www.mongodb.com/licensing",
                    evidence_quote="Versions of MongoDB prior to 4.0 were released under the GNU AGPL 3.0.",
                )

        # -------------------------------------------------------------
        # 7. HashiCorp Vault & Consul
        # -------------------------------------------------------------
        if re.search(r"\bvault\b", low_name) and "hashicorp" in str(publisher or "").lower():
            if v_tuple >= (1, 15, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="HashiCorp Vault >= 1.15.0 relicensed under BSL-1.1.",
                    license_model="BSL-1.1 — Commercial / Source Available",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Named User",
                    spdx_id="BSL-1.1",
                    evidence_url="https://www.hashicorp.com/bsl-faq",
                    evidence_quote="Vault 1.15+ moved from MPL 2.0 to the Business Source License.",
                )

        if re.search(r"\bconsul\b", low_name) and "hashicorp" in str(publisher or "").lower():
            if v_tuple >= (1, 16, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="HashiCorp Consul >= 1.16.0 relicensed under BSL-1.1.",
                    license_model="BSL-1.1 — Commercial / Source Available",
                    classification="COMMERCIAL",
                    license_required="YES",
                    metric="Named User",
                    spdx_id="BSL-1.1",
                    evidence_url="https://www.hashicorp.com/bsl-faq",
                    evidence_quote="Consul 1.16+ moved from MPL 2.0 to the Business Source License.",
                )

        # -------------------------------------------------------------
        # 8. Grafana
        # -------------------------------------------------------------
        if re.search(r"\bgrafana\b", low_name):
            # Shift at version 7.5.0 (April 2021: Apache 2.0 -> AGPLv3)
            if v_tuple >= (7, 5, 0):
                return VersionInflectionResult(
                    is_inflected=True,
                    rule_applied="Grafana >= 7.5.0 is licensed under GNU AGPL-3.0.",
                    license_model="AGPL-3.0 — Free/Open Source",
                    classification="OPEN_SOURCE",
                    license_required="NO",
                    metric="No License Required",
                    spdx_id="AGPL-3.0-only",
                    evidence_url="https://grafana.com/licensing/",
                    evidence_quote="Grafana 7.5+ is licensed under the AGPLv3 license.",
                )

        return None
