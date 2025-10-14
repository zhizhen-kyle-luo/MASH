import json
from typing import Dict, Any, List, Optional


class MIMICDataAdapter:
    """Adapter to convert MIMIC-IV-Ext CDM records to game format."""

    PATHOLOGY_MAP = {
        "appendicitis": "acute appendicitis",
        "diverticulitis": "acute diverticulitis",
        "cholecystitis": "acute cholecystitis",
        "pancreatitis": "acute pancreatitis"
    }

    MEDICALLY_INDICATED_TESTS = {
        "appendicitis": ["CBC", "CT abdomen/pelvis with contrast"],
        "diverticulitis": ["CBC", "CT abdomen/pelvis with contrast"],
        "cholecystitis": ["RUQ ultrasound", "CBC", "liver function tests"],
        "pancreatitis": ["lipase", "CT abdomen/pelvis with contrast", "CBC"]
    }

    def __init__(self, mimic_json_path: str):
        with open(mimic_json_path, 'r', encoding='utf-8') as f:
            self.records = json.load(f)

    def convert_to_game_case(self, record: Dict[str, Any], case_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert single MIMIC record to game case format."""
        hadm_id = record["hadm_id"]
        pathology = record.get("pathology", "unknown")

        age, sex = self._extract_demographics(record)
        chief_complaint, brief_history = self._extract_history(record)
        vitals = self._extract_vitals(record)

        diagnosis = self.PATHOLOGY_MAP.get(pathology.lower(), pathology)
        indicated_tests = self.MEDICALLY_INDICATED_TESTS.get(pathology.lower(), [])

        return {
            "case_id": case_id or f"mimic_{hadm_id}",
            "hadm_id": hadm_id,
            "patient_presentation": {
                "age": age,
                "sex": sex,
                "chief_complaint": chief_complaint,
                "brief_history": brief_history,
                "vitals": vitals,
                "raw_hpi": record.get("hpi", ""),
                "raw_pe": record.get("pe", "")
            },
            "ground_truth": {
                "diagnosis": diagnosis,
                "medically_indicated_tests": indicated_tests,
                "pathology": pathology,
                "discharge_diagnosis": record.get("discharge_diagnosis", ""),
                "icd_diagnoses": record.get("icd_diagnoses", []),
                "icd_procedures": record.get("icd_procedures", [])
            },
            "available_tests": {
                "lab_tests": record.get("lab_tests", []),
                "radiology_reports": record.get("radiology_reports", []),
                "microbiology": record.get("microbiology", [])
            }
        }

    def _extract_demographics(self, record: Dict[str, Any]) -> tuple[int, str]:
        """Extract age and sex from HPI or PE."""
        hpi = record.get("hpi", "").lower()
        pe = record.get("pe", "").lower()
        text = hpi + " " + pe

        age = None
        sex = "unknown"

        tokens = text.split()
        for i, token in enumerate(tokens):
            if "year" in token or "yo" in token or "y/o" in token:
                if i > 0:
                    try:
                        age = int(tokens[i-1])
                    except:
                        pass

            if any(word in token for word in ["male", "man", "gentleman"]):
                sex = "male"
            elif any(word in token for word in ["female", "woman", "lady"]):
                sex = "female"

        return age or 50, sex

    def _extract_history(self, record: Dict[str, Any]) -> tuple[str, str]:
        """Extract chief complaint and brief history from HPI."""
        hpi = record.get("hpi", "")
        pathology = record.get("pathology", "abdominal pain")

        chief_complaint = f"{pathology}"

        sentences = hpi.split('.')
        brief_history = '. '.join(sentences[:3]).strip() if sentences else hpi[:200]

        return chief_complaint, brief_history

    def _extract_vitals(self, record: Dict[str, Any]) -> str:
        """Extract vital signs from PE."""
        pe = record.get("pe", "")

        vitals_keywords = ["temp", "hr", "bp", "rr", "spo2", "o2 sat"]
        vitals_lines = []

        for line in pe.split('\n'):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in vitals_keywords):
                vitals_lines.append(line.strip())

        if vitals_lines:
            return " ".join(vitals_lines[:5])

        return "Vitals within normal limits"

    def convert_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Convert all records to game format."""
        records_to_convert = self.records[:limit] if limit else self.records
        return [
            self.convert_to_game_case(record, f"mimic_{i:04d}")
            for i, record in enumerate(records_to_convert)
        ]

    def get_by_pathology(self, pathology: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get cases filtered by pathology."""
        filtered = [r for r in self.records if r.get("pathology", "").lower() == pathology.lower()]

        if limit:
            filtered = filtered[:limit]

        return [
            self.convert_to_game_case(record, f"mimic_{pathology}_{i:03d}")
            for i, record in enumerate(filtered)
        ]
