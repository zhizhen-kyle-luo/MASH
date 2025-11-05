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

    # note: this case provides phase 1 input data only (patient presentation, clinical data)
    # phase 2-4 outcomes (pa decisions, claims, appeals, payments) will be simulated by agents
    # validation happens at population level across 15-20 cases, not individual predictions

    # cost reference data for phase 4 calculations (not ground truth validation)
    "cost_reference": {
        "drug_acquisition_cost": 7800.00,  # per infusion
        "administration_fee": 150.00,
        "pa_review_cost": 75.00,
        "claim_review_cost": 50.00,
        "appeal_cost": 180.00
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
