# MASH - Multi-Agent System for Healthcare

Multi-agent healthcare coordination system implementing concepts from Moritz et al. (Nature BME, 2025). Features persona-driven patient simulation integrated with coordinated specialist agents.

## Overview

MASH demonstrates coordinated AI agents communicating in natural language for patient care workflows. A user-facing Concierge agent coordinates with specialized back-office agents:

- **Concierge**: Patient interaction and conversational symptom gathering
- **UrgentCare**: Clinical evaluation and workup recommendations
- **Insurance**: Coverage and authorization decisions
- **Coordinator**: Scheduling and appointment management

## PatientSim Integration

Integrated with PatientSim framework for realistic patient simulation using MIMIC-IV/MIMIC-ED clinical data patterns. Supports 37 unique patient personas across 4 behavioral dimensions:

- **Personalities**: plain, verbose, pleasing, impatient, distrust, overanxious
- **Language proficiency**: A (basic), B (intermediate), C (advanced CEFR)
- **Medical recall**: no_history, low, high
- **Cognitive status**: normal, moderate confusion, high confusion

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Configure environment variables in `.env`:

```bash
AZURE_KEY=your_azure_openai_key
AZURE_ENDPOINT=your_azure_endpoint
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-02-01
```

## Usage

### Run Integration Tests

```bash
python tests/test_patient_simulator.py
```

### Run Persona Demonstrations

```bash
python examples/patient_sim_demo.py
```

### Programmatic Usage

```python
from dotenv import load_dotenv
load_dotenv()

from agents.patient_simulator import MASHPatientSimulator

patient = MASHPatientSimulator(
    personality="overanxious",
    recall_level="low",
    age="52",
    gender="female"
)

response = patient.respond("What brings you in today?")
```

## Workflow Architecture

### Phase 1: Patient Simulation

1. PatientSim generates persona-driven responses
2. Concierge conducts conversational symptom gathering
3. Clinical summary generated from conversation

### Phase 2: Multi-Agent Coordination

4. Concierge requests clinical evaluation from UrgentCare
5. UrgentCare provides workup recommendations
6. Concierge verifies coverage with Insurance agent
7. Insurance returns authorization decision
8. Concierge requests scheduling from Coordinator
9. Coordinator provides availability
10. Concierge presents integrated care plan

## Test Cases

PatientSim-integrated cases demonstrating persona variation:

- `case_patientsim_001.json`: Overanxious 52yo female, chest pain with anxiety
- `case_patientsim_002.json`: Impatient 67yo male with CAD, moderate confusion

Standard EHR cases:

- `case_001.json`: 32yo male, multiple conditions, Aetna
- `case_002.json`: 45yo female, hypertension, Blue Cross
- `case_003.json`: 28yo female, active lifestyle, Aetna

## Project Structure

```
MASH/
├── src/
│   ├── agents/
│   │   ├── patient_simulator.py   # PatientSim integration
│   │   ├── concierge.py           # Patient-facing coordinator
│   │   ├── urgent_care.py         # Clinical evaluation
│   │   ├── insurance.py           # Coverage decisions
│   │   └── coordinator.py         # Scheduling
│   ├── models/
│   │   └── schemas.py             # FHIR-compliant data models
│   ├── graph/
│   │   └── workflow.py            # LangGraph orchestration
│   └── api/
│       └── main.py                # FastAPI endpoints
├── data/
│   └── cases/                     # Test case definitions
├── tests/
│   └── test_patient_simulator.py  # Integration tests
└── examples/
    └── patient_sim_demo.py        # Persona demonstrations
```

## Architecture

### Data Models

- **PatientEHR**: Structured FHIR-compliant medical data
- **ClinicalSummary**: Narrative content from patient conversations
- **Message**: Inter-agent communication format
- **GraphState**: Workflow state preservation

### Design Principles

- FHIR compliance for structured data
- Natural language agent coordination
- Persona-driven patient simulation
- State preservation across agent transitions
- Observable inter-agent communication

## Configuration

Environment variables:

- `AZURE_KEY`: Azure OpenAI API key
- `AZURE_ENDPOINT`: Azure OpenAI endpoint URL
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Model deployment name
- `AZURE_OPENAI_API_VERSION`: API version
- `LOG_LEVEL`: Logging verbosity (default: INFO)
- `TRANSCRIPT_DIR`: Conversation log directory (default: ./transcripts)

## Development

### Running Tests

```bash
pytest tests/
```

### Adding Patient Personas

```python
patient = MASHPatientSimulator(
    personality="verbose",
    recall_level="high",
    confusion_level="normal",
    lang_proficiency_level="C",
    age="45",
    gender="female",
    **additional_ehr_params
)
```

## References

- Moritz et al. "Coordinated AI agents for advancing healthcare." Nature Biomedical Engineering (2025)
- PatientSim: https://github.com/microsoft/PatientSim
- MIMIC-IV: https://physionet.org/content/mimiciv/

## License

Research prototype. See institutional guidelines for usage and distribution.
