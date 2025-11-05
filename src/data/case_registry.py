"""
case registry - central import and registration of all simulation cases
"""

from src.data.cases.specialty_medications.infliximab_crohns_case import (
    INFLIXIMAB_CASE,
    get_infliximab_case
)
from src.data.cases.inpatient_admissions.apprisemd_sepsis_case import (
    APPRISEMD_CASE,
    get_apprisemd_case
)

# registry of all available cases
CASE_REGISTRY = {
    # specialty medications
    "infliximab_crohns_2015": INFLIXIMAB_CASE,

    # inpatient admissions
    "apprisemd_sepsis_2024": APPRISEMD_CASE,
}

# case getter functions
CASE_GETTERS = {
    "infliximab_crohns_2015": get_infliximab_case,
    "apprisemd_sepsis_2024": get_apprisemd_case,
}

def get_case(case_id: str):
    """retrieve case by id"""
    if case_id not in CASE_GETTERS:
        raise ValueError(f"case {case_id} not found in registry. available: {list(CASE_GETTERS.keys())}")
    return CASE_GETTERS[case_id]()

def list_cases():
    """list all available case ids"""
    return list(CASE_REGISTRY.keys())

def get_cases_by_type(pa_type: str):
    """get all cases of a specific PA type"""
    return [
        case_id for case_id, case_data in CASE_REGISTRY.items()
        if case_data.get("pa_type") == pa_type
    ]
