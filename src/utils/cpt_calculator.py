from typing import Optional, Dict


class CPTCostCalculator:
    """CPT code extraction and cost calculation using CMS fee schedules."""

    PHYSICIAN_VISIT_COST = 300.0

    def __init__(self):
        self.cpt_map = {
            "ecg": "93000",
            "electrocardiogram": "93000",
            "ekg": "93000",
            "troponin": "84484",
            "cardiac troponin": "84484",
            "troponin i": "84484",
            "troponin t": "84484",
            "chest x-ray": "71046",
            "chest xray": "71046",
            "cxr": "71046",
            "ct chest": "71250",
            "ct angiography": "71275",
            "stress test": "93015",
            "cardiac stress test": "93015",
            "echocardiogram": "93306",
            "echo": "93306",
            "bmp": "80048",
            "basic metabolic panel": "80048",
            "cmp": "80053",
            "comprehensive metabolic panel": "80053",
            "cbc": "85025",
            "complete blood count": "85025",
            "bnp": "83880",
            "b-type natriuretic peptide": "83880",
            "d-dimer": "85379",
            "ct head": "70450",
            "head ct": "70450",
            "mri brain": "70551",
            "lumbar puncture": "62270",
            "cardiac catheterization": "93458",
        }

        self.cost_schedule = {
            "93000": 50.0,
            "84484": 35.0,
            "71046": 85.0,
            "71250": 450.0,
            "71275": 750.0,
            "93015": 200.0,
            "93306": 350.0,
            "80048": 25.0,
            "80053": 45.0,
            "85025": 15.0,
            "83880": 40.0,
            "85379": 50.0,
            "70450": 500.0,
            "70551": 800.0,
            "62270": 300.0,
            "93458": 2000.0,
        }

    def extract_cpt_code(self, test_name: str) -> Optional[str]:
        normalized = test_name.lower().strip()
        return self.cpt_map.get(normalized)

    def get_cost(self, cpt_code: str) -> float:
        return self.cost_schedule.get(cpt_code, 100.0)

    def calculate_test_cost(self, test_name: str) -> float:
        cpt_code = self.extract_cpt_code(test_name)
        if cpt_code:
            return self.get_cost(cpt_code)
        return 100.0

    def calculate_total_cost(
        self,
        tests: list[str],
        num_visits: int = 1
    ) -> Dict[str, float]:
        visit_cost = self.PHYSICIAN_VISIT_COST * num_visits
        test_costs = sum(self.calculate_test_cost(test) for test in tests)
        total = visit_cost + test_costs

        return {
            "visit_cost": visit_cost,
            "test_costs": test_costs,
            "total_cost": total
        }
