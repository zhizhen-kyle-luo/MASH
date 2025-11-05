"""
Infliximab for Crohn's Disease - SPECIALTY MEDICATION PA VALIDATION

case format for specialty medication pa:
- patient_presentation: demographics, symptoms, medical history
- medication_request: drug details, dosing, clinical rationale
- step_therapy_documentation: prior failures, disease severity
- ground_truth_payer_actions: pa approval/denial, appeal outcomes
- ground_truth_financial: drug costs, admin costs, pa costs

source: https://pmc.ncbi.nlm.nih.gov/articles/PMC8077752/
case: 60yo female with moderate-severe crohn's disease requiring infliximab
"""

INFLIXIMAB_CASE = {
    "case_id": "infliximab_crohns_2015",
    "pa_type": "specialty_medication",

    "patient_presentation": {
        "patient_id": "PT-2015-002",
        "age": 60,
        "sex": "F",
        "admission_date": "2015-06-01",
        "admission_source": "Direct",

        "chief_complaint": "10-day history of small intestinal stenosis, abdominal pain, watery diarrhea",

        "vital_signs": {
            "temperature": "Normal",
            "heart_rate": "Normal",
            "blood_pressure": "Normal",
            "respiratory_rate": "Normal"
        },

        "medical_history": [
            "Crohn's disease (diagnosed 2015)",
            "Small intestinal stenosis",
            "Hypercholesterolemia"
        ],

        "medications": [
            "Mesalazine 3 g/day (failed therapy - symptoms only partially controlled)"
        ],

        "presenting_symptoms": "Patient with confirmed Crohn's disease presenting with intestinal stenosis, persistent abdominal pain, and watery diarrhea 3-4 times daily despite mesalazine therapy. Disease activity documented by colonoscopy and biopsy."
    },

    "available_test_results": {
        "labs": {
            "inflammatory_markers": {
                "fecal_calprotectin": "827.162 µg/g (CRITICALLY ELEVATED - normal <50 µg/g)",
                "indication": "Severe active intestinal inflammation"
            },
            "nutritional_status": {
                "albumin": "36.1 g/L (LOW - normal 40-55 g/L)",
                "indication": "Hypoalbuminemia reflects disease severity and malnutrition"
            },
            "hematology": {
                "leukocytes": "3.2 × 10⁹/L (low-normal)",
                "platelets": "123 × 10⁹/L (low - normal 125-350)",
                "indication": "Mild cytopenias consistent with chronic inflammation"
            },
            "chemistry": {
                "calcium": "2.18 mmol/L (LOW - normal 2.25-2.75)",
                "magnesium": "0.82 mmol/L (normal 0.7-1.0)",
                "cholesterol": "3.35 mmol/L (elevated - normal 1.89-3.1)"
            },
            "tb_screening": {
                "t_spot_tb": "Negative",
                "indication": "Required before initiating anti-TNF therapy"
            }
        },

        "imaging": {
            "colonoscopy": "Secondary intestinal stenosis visualized",
            "3d_ct": "Confirmed Crohn's disease with small bowel involvement",
            "biopsy": "Positive for Crohn's disease pathology"
        }
    },

    "medication_request": {
        "medication_name": "Infliximab (Remicade)",
        "j_code": "J1745",
        "dosage": "5 mg/kg",
        "route": "Intravenous infusion",
        "frequency": "Induction: Week 0, 2, 6. Maintenance: Every 8 weeks",
        "duration": "Ongoing (chronic therapy)",

        "icd10_codes": [
            "K50.00 - Crohn's disease of small intestine without complications",
            "K50.8 - Other Crohn's disease (stenosis)"
        ],

        "clinical_rationale": """
Patient has moderate-to-severe Crohn's disease with documented:
1. Active inflammation: Fecal calprotectin 827 µg/g (>16x upper limit of normal)
2. Structural damage: Small intestinal stenosis on colonoscopy and CT
3. Systemic impact: Hypoalbuminemia (36.1 g/L), malnutrition
4. Failed conventional therapy: Mesalazine 3 g/day provided only partial symptom control
5. Persistent symptoms: Daily abdominal pain, diarrhea 3-4x/day

Infliximab (anti-TNF-α biologic) indicated per ACG/AGA guidelines for:
- Moderate-severe CD refractory to conventional therapy
- Active inflammation with elevated biomarkers
- Need for mucosal healing and prevention of complications
""",

        "prior_therapies_failed": [
            "Mesalazine 3 g/day - inadequate response, persistent symptoms and inflammation"
        ],

        "step_therapy_completed": True,
        "step_therapy_documentation": "Patient trialed conventional 5-ASA therapy (mesalazine) with documented inadequate response"
    },

    "ground_truth_diagnoses": {
        "primary": [
            "Crohn's disease of small intestine (K50.00)",
            "Intestinal stenosis (K50.8)"
        ],
        "severity": "Moderate-to-severe based on fecal calprotectin, hypoalbuminemia, and stenosis"
    },

    "ground_truth_payer_actions": {
        "initial_decision": {
            "status": "DENIED",
            "denial_reason": """Prior authorization denied. Reasons:
1. Insufficient documentation of step therapy: No evidence of corticosteroid trial
2. Insufficient disease severity documentation: Request additional endoscopic scoring (CDAI, SES-CD)
3. Missing documentation: No documented failure of immunomodulator therapy (azathioprine/6-MP)
4. Cost concerns: Infliximab is high-cost biologic ($2,500-$5,000 per infusion)

Payer suggests: Step therapy with azathioprine or prednisone before approving biologic therapy.""",

            "payer_rationale": "Deny due to incomplete step therapy ladder despite elevated inflammatory markers"
        },

        "appeal_process": {
            "method": "Peer-to-peer with medical director + written appeal",
            "provider_arguments": [
                "Fecal calprotectin 827 µg/g indicates severe active inflammation",
                "Hypoalbuminemia (36.1 g/L) indicates significant disease severity",
                "Intestinal stenosis represents structural complication requiring aggressive therapy",
                "Mesalazine failure documented - patient requires biologic escalation",
                "Steroids contraindicated in stenotic disease (perforation risk)",
                "ACG guidelines support biologics for moderate-severe CD after 5-ASA failure"
            ],
            "appeal_outcome": "APPROVED",
            "payer_final_reasoning": "Given severe inflammation (fecal calprotectin), structural complication (stenosis), and contraindication to steroids, biologic therapy is medically necessary. Approved for 8-week induction + maintenance."
        }
    },

    "ground_truth_financial": {
        "medication_costs": {
            "drug_name": "Infliximab (Remicade)",
            "j_code": "J1745",
            "cost_per_mg": 24.00,
            "patient_weight_kg": 65,
            "dose_mg_per_kg": 5,
            "total_dose_mg": 325,
            "drug_acquisition_cost": 7800.00,
            "administration_fee": 150.00,
            "total_per_infusion": 7950.00
        },

        "annual_costs": {
            "induction_cost": 23850.00,
            "maintenance_cost": 47700.00,
            "total_year_1": 71550.00
        },

        "if_approved": {
            "payer_pays": 63909.00,
            "patient_copay": 7641.00,
            "total_drug_cost": 71550.00
        },

        "if_denied_no_appeal": {
            "patient_switches_insurance": "Likely",
            "provider_samples_burden": "Provider may provide samples short-term",
            "disease_progression_cost": "Potential hospitalization, surgery if untreated",
            "estimated_progression_cost": 45000.00
        },

        "administrative_costs": {
            "provider_pa_submission": 50.00,
            "payer_pa_review": 25.00,
            "provider_appeal_p2p": 180.00,
            "payer_appeal_review": 120.00,
            "total_administrative_burden": 375.00
        },

        "actual_outcome": {
            "authorization_status": "approved",
            "approved_after_appeal": True,
            "total_cost_including_admin": 71925.00
        }
    },

    "insurance_info": {
        "plan_type": "MA",
        "payer_name": "Medicare Advantage",
        "authorization_required": True,
        "utilization_review_criteria": "NCCN guidelines, ACG/AGA Crohn's disease guidelines, step therapy requirements"
    }
}


def get_infliximab_case():
    """returns infliximab specialty medication pa case for simulation"""
    return INFLIXIMAB_CASE
