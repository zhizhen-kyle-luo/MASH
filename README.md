# MASH: Multi-Agent Systems for Healthcare

## Healthcare AI Arms Race Simulation

Game-theoretic multi-agent simulation studying adversarial dynamics in healthcare AI adoption.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# Run test with real MIMIC data
python examples/test_nested_iteration.py
```

## Architecture

**Two-Phase Nested Iteration Game:**

### Phase 1: Iterative Encounter
Provider orders tests → Payer authorizes/denies → Provider reacts (appeal/order anyway/accept)
- Up to 10 iterations
- Stops when confidence ≥0.9 OR max iterations OR workup complete

### Phase 2: Retrospective Scrutiny
Patient AI second opinion + Lawyer malpractice review (parallel)

## Project Structure

```
MASH/
├── data/
│   ├── mimic_raw.json          # 2,712 real MIMIC-IV-Ext cases
│   └── cases/                  # (empty - cleaned up)
├── src/
│   ├── agents/
│   │   ├── provider.py         # Iterative decision-making
│   │   ├── payor.py            # Real-time authorization
│   │   ├── patient_game.py     # Retrospective AI shopping
│   │   ├── lawyer.py           # Malpractice review
│   │   ├── game_agent.py       # Base agent class
│   │   └── base.py             # Abstract agent
│   ├── data/
│   │   └── mimic_adapter.py    # MIMIC → game format
│   ├── models/
│   │   └── schemas.py          # GameState, IterationRecord, decisions
│   ├── simulation/
│   │   └── game_runner.py      # Nested iteration orchestration
│   └── utils/
│       ├── cpt_calculator.py   # CPT cost calculation
│       └── payoff_functions.py # Agent payoff formulas
├── examples/
│   └── test_nested_iteration.py # Demo with real MIMIC data
├── experiments/
│   └── run_experiments.py      # LLM asymmetry + payment model experiments
└── tests/
    └── test_agents.py          # Unit tests
```

## Key Features

- **Real Patient Cases**: 2,712 MIMIC-IV-Ext CDM records (appendicitis, diverticulitis, cholecystitis, pancreatitis)
- **Nested Iteration Loop**: Provider-payer interaction up to 10 rounds
- **Confidence Tracking**: Bayesian updating (0-1 scale)
- **Real-time Authorization**: Payer approves/denies during encounter
- **Appeal Mechanism**: Provider can appeal denials with justification
- **Order-Despite-Denial**: Provider can "eat cost" to order tests anyway
- **Iteration History**: Full tracking of each interaction
- **Game-Theoretic Payoffs**: Utilities for all 4 agents

## Data

**MIMIC-IV-Ext Clinical Decision Making v1.1**
- 2,712 cases from NEJM Case Records
- 4 abdominal pathologies
- Ground truth diagnoses
- Lab tests, radiology reports, ICD codes

## Independent Variables

1. **LLM Strength Asymmetry**: Symmetric (all GPT-4) vs Asymmetric (provider GPT-3.5)
2. **Payment Model**: Fee-for-service vs Value-based
3. **Patient Persona**: 37 combinations (personality, language, recall, confusion)
4. **Escalation Level**: 0-10 (defensiveness/aggressiveness)
5. **Confidence Threshold**: When to stop iterating (default 0.9)

## Dependent Variables

### Iteration-Level
- Number of iterations to convergence
- Confidence trajectory
- Tests approved/denied per iteration
- Appeal rate and success rate
- Order-despite-denial rate

### System-Level
- Total system costs
- Diagnostic accuracy
- Defensive medicine index
- Trust index
- Equilibrium type (cooperative vs competitive)

## Expected Findings

**Cooperative Equilibrium (Unstable)**
- Low AI (3-4/10), appropriate testing, 2-3 iterations, ~$200/case, high trust

**Competitive Arms Race (Stable but Inefficient)**
- High AI (8-9/10), defensive medicine, 7-10 iterations, ~$3000/case, low trust

**Hypothesis**: Rational self-interest drives competitive equilibrium (Prisoner's Dilemma)

## Research Contribution

- First simulation of adversarial healthcare AI dynamics with iterative clinical decision-making
- Models real-time payer authorization pressure
- Demonstrates appeal mechanisms and order-despite-denial strategies
- Tracks confidence evolution through diagnostic workup
- Policy implications for AI regulation and payment reform

## Configuration

Required `.env` variables:
```
AZURE_KEY=your_key
AZURE_ENDPOINT=your_endpoint
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment
```

## Citation

```
@article{mash2025,
  title={Healthcare AI Arms Race: A Multi-Agent Simulation Study},
  author={Your Name},
  year={2025}
}
```

## License

MIT
