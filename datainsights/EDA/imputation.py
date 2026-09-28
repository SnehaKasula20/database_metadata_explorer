from __future__ import annotations

from typing import Any, Dict, List, Optional


class ImputationRecommender:

    @classmethod
    def add_recommendations(
        cls,
        profiles: List[Dict[str, Any]],
        date_rules: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        updated_profiles = []
        for p in profiles:
            p_copy = dict(p)
            missing_cnt = p_copy.get("missing_count", 0)
            category = p_copy.get("category", "")
            stats = p_copy.get("statistics", {})

            if missing_cnt == 0:
                method = "None (Complete)"
                reason = "No missing values detected."
            elif category in {"NUMERICAL_DISCRETE", "NUMERICAL_CONTINUOUS"}:
                skew = abs(stats.get("skewness", 0))
                if skew > 1.0:
                    method = "Median Imputation"
                    reason = f"Skewed distribution detected (|skew|={skew:.2f} > 1.0); median imputation is robust to outliers."
                else:
                    method = "Mean Imputation"
                    reason = "Symmetric numerical distribution detected; mean imputation preserves central tendency."
            elif category in {"CATEGORICAL_NOMINAL", "CATEGORICAL_ORDINAL", "BOOLEAN"}:
                method = "Mode Imputation"
                reason = "Categorical/Discrete column; mode imputation replaces missing values with the most frequent value."
            else:
                method = "Constant / Flag Imputation"
                reason = "Missing indicator token or placeholder imputation recommended for unclassified text/date missing entries."

            p_copy["recommended_method"] = method
            p_copy["reason"] = reason
            p_copy["recommendation"] = {
                "method": method,
                "reason": reason
            }
            updated_profiles.append(p_copy)

        return updated_profiles
