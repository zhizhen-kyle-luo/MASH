"""
AppriseMD Sepsis Case - VALIDATION EXAMPLE

This is ONE test case for validating the ABM.
The simulation is designed to handle ANY case following this data structure.

Case Format (generic):
- patient_presentation: dict (symptoms, vitals, history)
- available_test_results: dict (labs, imaging)
- ground_truth_diagnoses: dict (actual diagnosis, DRG)
- ground_truth_payer_actions: dict (actual denial/appeal outcome)
- ground_truth_financial: dict (actual payment)

Future cases should follow this same structure but with different clinical data.

CASE FORMAT SPECIFICATION:

case_dict = {
    "case_id": str,
    "patient_presentation": {
        "age": int,
        "sex": "M" or "F",
        "chief_complaint": str,
        "vital_signs": dict,
        "medical_history": list[str],
        "medications": list[str],
        "presenting_symptoms": str
    },
    "available_test_results": {
        "labs": dict,
        "imaging": dict
    },
    "ground_truth_diagnoses": {
        "primary": list[str],
        "drg": str
    },
    "ground_truth_payer_actions": {
        "initial_decision": {...},
        "appeal_process": {...}
    },
    "ground_truth_financial": {
        "drg_assignment": {
            "drg_code": str,
            "drg_description": str,
            "payment_amount": float
        },
        "if_approved_inpatient": {...},
        "if_denied_observation": {...}
    },
    "insurance_info": {...}
}

ADDING NEW CASES:
To add a new case (e.g., hip fracture, stroke, CHF exacerbation):
1. Create new file following this structure
2. Replace clinical data with new case details
3. NO CODE CHANGES needed in simulation_runner.py or agents
4. The ABM is case-agnostic and works for any medical admission scenario

AppriseMD Case: 75yo Male with Sepsis + NSTEMI
Source: https://apprisemd.com/case-study-ama-inpatient-denial-overturned/
Date: June 15-16, 2019
"""

APPRISEMD_CASE = {
    "case_id": "apprisemd_sepsis_nstemi_2019",

    "patient_presentation": {
        "patient_id": "PT-2019-001",
        "age": 75,
        "sex": "M",
        "admission_date": "2019-06-15",
        "admission_source": "ER",

        "chief_complaint": "Fevers, body aches, shortness of breath, chills",

        "vital_signs": {
            "temperature": "101.3°F",
            "heart_rate": "99 bpm (tachycardic)",
            "blood_pressure": "140/90 mmHg",
            "respiratory_rate": "18/min",
            "oxygen_saturation": "Normal on room air"
        },

        "medical_history": [
            "Type 2 diabetes mellitus",
            "Hypertension",
            "Chronic urinary retention (self-catheterizes)",
            "Diabetic peripheral neuropathy (on gabapentin)",
            "Chronic kidney disease Stage 3 (baseline Cr 1.33)"
        ],

        "medications": [
            "Gabapentin (diabetic neuropathy)",
            "Antihypertensive medications",
            "Diabetes medications"
        ],

        "presenting_symptoms": "Patient presents with fever, chills, body aches, and shortness of breath. Has chronic urinary retention and self-catheterizes."
    },

    "available_test_results": {
        "labs": {
            "cbc": {
                "wbc": "5.50 K/uL (normal)",
                "rbc": "5.03 M/uL",
                "hemoglobin": "15.0 g/dL"
            },
            "bmp": {
                "sodium": "140 mmol/L",
                "potassium": "4.5 mmol/L",
                "bun": "19 mg/dL",
                "creatinine": "1.33 mg/dL (elevated, consistent with CKD Stage 3)",
                "glucose": "150-201 mg/dL (hyperglycemic)"
            },
            "cardiac_markers": {
                "troponin_1": "359 ng/L (initial)",
                "troponin_2": "577 ng/L (4 hours later - RISING)",
                "troponin_3": "773 ng/L (8 hours later - RISING, confirms NSTEMI)"
            },
            "lactate": "7.2 mmol/L (CRITICALLY ELEVATED - indicates severe sepsis)",
            "ptt": "23.0 seconds",
            "procalcitonin": "Minimally elevated",
            "d_dimer": "3570 ng/mL (elevated)",
            "urinalysis": {
                "rbc": "6-10 per HPF",
                "wbc": "51-99 per HPF (ELEVATED)",
                "nitrite": "Positive",
                "leukocyte_esterase": "1+",
                "bacteria": "4+ (HEAVY)",
                "epithelial_cells": "0-5"
            },
            "urine_culture": "Positive for Klebsiella oxytoca (confirms UTI)"
        },

        "imaging": {
            "ekg": "Normal sinus rhythm, rate 99. Right bundle branch block (RBBB) and left anterior fascicular block (LAFB). Inferior infarct, age indeterminate (old).",

            "chest_xray": "No acute cardiopulmonary process",

            "ct_abdomen_pelvis": "Negative for acute pathology. No abscess, no obstruction.",

            "cta_chest": "Negative for pulmonary embolism"
        }
    },

    "ground_truth_diagnoses": {
        "primary": [
            "Severe sepsis (R65.20) - Lactate 7.2 mmol/L",
            "Acute urinary tract infection (N39.0) - Klebsiella oxytoca",
            "NSTEMI (I21.4) - Rising troponins 359 → 577 → 773"
        ],
        "drg": "871 - Septicemia or severe sepsis with MCC",
        "mcc_qualifier": "Elevated lactate > 4.0 mmol/L qualifies as MCC"
    },

    "treatment_given": {
        "medications": [
            "IV Rocephin (ceftriaxone) - broad-spectrum antibiotic",
            "IV Heparin - anticoagulation for NSTEMI",
            "Aspirin",
            "Statins",
            "Beta-blockers"
        ],
        "monitoring": "Cardiac telemetry, frequent vital signs",
        "consultations": "Cardiology recommended medical management"
    },

    "patient_course": {
        "initial_condition": "Tachycardic and febrile",
        "response_to_treatment": "Began feeling better after one dose IV antibiotics",
        "day_2_status": "Asymptomatic, adamant about leaving",
        "physician_recommendation": "48 hours IV anticoagulation and cardiac monitoring",
        "echocardiogram": "Scheduled but patient did not want to wait",
        "discharge_disposition": "Left Against Medical Advice (AMA) on Day 2 morning"
    },

    "ground_truth_payer_actions": {
        "initial_decision": {
            "status": "DENIED - Suggest observation instead",
            "denial_reason": """To qualify for admission, evidence-based clinical guidelines require one or more conditions – listed as unstable vital signs or mental state, a spreading infection, acute kidney failure, related symptoms that do not resolve or a complex medical procedure – must persist past the observation period.

Despite having UTI and mild heart attack, symptoms resolved, and patient elected to leave AMA. Patient received incomplete care and did not qualify for inpatient admission.""",

            "payer_rationale": "Symptoms improved quickly, patient left after 1 night, insufficient severity for inpatient level"
        },

        "appeal_process": {
            "method": "Peer-to-peer discussion with payer's medical director",
            "provider_arguments": [
                "Acute UTI with severe sepsis (lactate 7.2 mmol/L)",
                "Significant rise in troponins up to 773 ng/L (NSTEMI)",
                "Patient started on IV antibiotics and IV Heparin",
                "Cardiologists recommended medical management on Hospital Day 2",
                "Patient left Against Medical Advice (incomplete treatment)"
            ],
            "appeal_outcome": "APPROVED",
            "payer_final_reasoning": "Given the likelihood of ongoing treatment if the patient had stayed, inpatient level of care is justified"
        }
    },

    "ground_truth_financial": {
        "drg_assignment": {
            "drg_code": "871",
            "drg_description": "Septicemia or severe sepsis with MCC",
            "payment_amount": 11564.00
        },

        "if_approved_inpatient": {
            "hospital_receives": 11564.00,
            "patient_copay": 350.00,
            "total_to_hospital": 11564.00
        },

        "if_denied_observation": {
            "hospital_receives": 4500.00,
            "patient_copay": 100.00,
            "total_to_hospital": 4500.00,
            "hospital_loss": 7064.00
        },

        "actual_outcome": {
            "level_authorized": "inpatient",
            "payment_received": 11564.00,
            "denial_overturned": True
        }
    },

    "insurance_info": {
        "plan_type": "MA",
        "payer_name": "UnitedHealthcare Medicare Advantage",
        "authorization_required": True,
        "utilization_review_criteria": "InterQual / MCG guidelines"
    }
}


def get_apprisemd_case():
    """Returns the complete AppriseMD case for simulation"""
    return APPRISEMD_CASE
