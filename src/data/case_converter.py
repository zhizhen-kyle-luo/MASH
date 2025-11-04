"""
Convert raw case dictionaries to structured Pydantic models
"""
from datetime import datetime
from src.models.schemas import (
    PatientDemographics,
    InsuranceInfo,
    AdmissionNotification,
    ClinicalPresentation,
    LabResult,
    ImagingResult,
    MedicationRequest,
    PAType
)


def convert_case_to_models(case_dict):
    """
    Convert raw case dictionary to structured models for simulation.

    This allows cases to be stored as simple dicts but converted to
    Pydantic models when needed by the simulation.

    handles both inpatient admission and specialty medication pa types.
    """
    patient_pres = case_dict["patient_presentation"]
    insurance = case_dict["insurance_info"]
    pa_type = case_dict.get("pa_type", PAType.INPATIENT_ADMISSION)

    patient_demographics = PatientDemographics(
        patient_id=patient_pres["patient_id"],
        age=patient_pres["age"],
        sex=patient_pres["sex"],
        mrn=patient_pres.get("patient_id")
    )

    insurance_info = InsuranceInfo(
        plan_type=insurance["plan_type"],
        payer_name=insurance["payer_name"],
        member_id=patient_demographics.patient_id,
        authorization_required=insurance["authorization_required"]
    )

    admission_date_str = patient_pres["admission_date"]
    if isinstance(admission_date_str, str):
        admission_date = datetime.strptime(admission_date_str, "%Y-%m-%d").date()
    else:
        admission_date = admission_date_str

    admission = AdmissionNotification(
        patient_demographics=patient_demographics,
        insurance=insurance_info,
        admission_date=admission_date,
        admission_source=patient_pres["admission_source"],
        chief_complaint=patient_pres["chief_complaint"],
        preliminary_diagnoses=[]
    )

    clinical_presentation = ClinicalPresentation(
        chief_complaint=patient_pres["chief_complaint"],
        history_of_present_illness=patient_pres.get("presenting_symptoms", ""),
        vital_signs=patient_pres["vital_signs"],
        physical_exam_findings="",
        medical_history=patient_pres["medical_history"]
    )

    case_dict["admission"] = admission
    case_dict["clinical_presentation"] = clinical_presentation
    case_dict["pa_type"] = pa_type

    # convert medication-specific data if present
    if pa_type == PAType.SPECIALTY_MEDICATION and "medication_request" in case_dict:
        med_req = case_dict["medication_request"]
        medication_request = MedicationRequest(
            medication_name=med_req["medication_name"],
            j_code=med_req.get("j_code"),
            dosage=med_req["dosage"],
            frequency=med_req["frequency"],
            duration=med_req["duration"],
            icd10_codes=med_req.get("icd10_codes", []),
            clinical_rationale=med_req["clinical_rationale"],
            prior_therapies_failed=med_req.get("prior_therapies_failed", []),
            step_therapy_completed=med_req.get("step_therapy_completed", False)
        )
        case_dict["medication_request_model"] = medication_request

    return case_dict
