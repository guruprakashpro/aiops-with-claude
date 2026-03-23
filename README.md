# AIops with Claude

A hands-on learning project demonstrating **7 optimization techniques** for building production-grade AI operations systems with LLMs. Each demo shows a before/after comparison with real metrics.

## Architecture

```
aiops-with-claude/
├── src/
│   ├── llm_client.py              # Unified LLM client (Groq, retry, streaming)
│   ├── config.py                  # Model config & routing logic
│   ├── optimizations/
│   │   ├── 01_streaming.py        # Streaming vs batch responses
│   │   ├── 02_structured_output.py # JSON mode vs regex parsing
│   │   ├── 03_tool_use.py         # Agentic loop with function calling
│   │   ├── 04_parallel_processing.py # asyncio concurrent processing
│   │   ├── 05_model_selection.py  # Fast vs smart model routing
│   │   ├── 06_prompt_optimization.py # Prompt engineering techniques
│   │   └── 07_async_batching.py   # Batch prompting + async grouping
│   ├── 01_log_analysis/           # Use case: streaming log analysis
│   ├── 02_incident_rca/           # Use case: tool-use root cause analysis
│   ├── 03_alert_triage/           # Use case: structured parallel triage
│   ├── 04_runbook_gen/            # Use case: runbook generation
│   ├── 05_anomaly_detection/      # Use case: multi-turn conversation
│   └── 06_multi_agent_pipeline/   # Use case: full AIops pipeline
├── run_all_demos.py               # Master runner with Rich summary
└── requirements.txt
```

## Quick Start

### Prerequisites

- Python 3.12+ (required — pydantic-core not yet compatible with 3.14)
- [Groq API key](https://console.groq.com) (free tier, no credit card)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/guruprakashpro/aiops-with-claude.git
cd aiops-with-claude

# 2. Create virtual environment with Python 3.12
python3.12 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Groq API key
export GROQ_API_KEY=your_key_here
# Or create a .env file: echo "GROQ_API_KEY=your_key" > .env
```

### Run All Demos

```bash
# Run all 7 optimization demos
python run_all_demos.py

# Run specific demos only
python run_all_demos.py --only 01,04,07

# Run a single demo directly
python src/optimizations/03_tool_use.py
```

## The 7 Optimization Techniques

### 01 — Streaming
**Benefit: 10x faster perceived latency**

Stream tokens as they arrive instead of waiting for the full response. Critical for user-facing applications.

```python
# Non-streaming: user waits 3s for first token
response = client.complete(messages=[...])

# Streaming: user sees first token in <200ms
for chunk in client.stream(messages=[...]):
    print(chunk, end="", flush=True)
```

```
Run: python src/optimizations/01_streaming.py
```

---

### 02 — Structured Output
**Benefit: Zero parsing failures, reliable data extraction**

Use JSON mode + Pydantic models instead of regex parsing LLM responses.

```python
# Before: fragile regex
severity = re.search(r'P[1-4]', response).group()

# After: guaranteed JSON with validation
class TriageResult(BaseModel):
    severity: str
    action: str
    escalate: bool

result = TriageResult(**json.loads(response))
```

```
Run: python src/optimizations/02_structured_output.py
```

---

### 03 — Tool Use / Function Calling
**Benefit: Grounded answers — no hallucinations on system state**

Let the LLM call your functions to fetch real data before answering.

```python
TOOLS = [
    {"name": "get_service_metrics", "description": "...", "parameters": {...}},
    {"name": "get_recent_deployments", ...},
]

# LLM decides what to check, YOUR code executes it
response = client.create(messages=messages, tools=TOOLS, tool_choice="auto")
```

```
Run: python src/optimizations/03_tool_use.py
```

---

### 04 — Parallel Processing
**Benefit: 10x speedup — process 10 alerts in time of 1**

LLM calls are I/O-bound. Use `asyncio.gather()` for concurrent processing.

```python
# Sequential: 10 alerts × 2s = 20s
for alert in alerts:
    results.append(await process(alert))

# Parallel: all 10 alerts ≈ 2s
sem = asyncio.Semaphore(5)  # max 5 concurrent
results = await asyncio.gather(*[process(a, sem) for a in alerts])
```

```
Run: python src/optimizations/04_parallel_processing.py
```

---

### 05 — Smart Model Selection
**Benefit: 3-5x faster + lower cost on simple tasks**

Route tasks to the right model. Not everything needs the most powerful model.

| Task Type | Model | Why |
|-----------|-------|-----|
| Classification, yes/no, labels | `llama-3.1-8b-instant` (FAST) | Pattern matching, no reasoning chain |
| Root cause analysis, runbooks | `llama-3.3-70b-versatile` (SMART) | Multi-step reasoning required |

```
Run: python src/optimizations/05_model_selection.py
```

---

### 06 — Prompt Optimization
**Benefit: 40-60% token reduction, faster responses**

Four techniques to write better prompts:

1. **Verbose → Concise**: Remove greetings and filler words
2. **Output format spec**: Show exact JSON schema, not natural language description
3. **Few-shot examples**: Calibrate the model to your exact definitions
4. **Negative constraints**: `DO NOT explain X` prevents padding

```python
# Before (verbose): 200+ tokens, vague output
"Hello! I was wondering if you could please help me with something..."

# After (concise): 40 tokens, structured output
system = "You are an SRE. JSON: {severity: P1-P4, action: str, escalate: bool}"
user = f"Alert: {alert_text}"
```

```
Run: python src/optimizations/06_prompt_optimization.py
```

---

### 07 — Async Batching with Dynamic Grouping
**Benefit: 60% token savings + max throughput**

Combine batch prompting (multiple items per LLM call) with async concurrency and priority grouping.

```
Individual calls:  20 alerts × 120 tokens = 2,400 tokens, 20 API calls
Smart batching:    ~400 tokens, 6 API calls (all processed concurrently)

Strategy:
  High priority  → batches of 3 (fast turnaround)
  Medium priority → batches of 4
  Low priority   → single large batch (max efficiency)
  All groups     → processed concurrently with asyncio
```

```
Run: python src/optimizations/07_async_batching.py
```

---

## The Formula

```
right model  ×  optimized prompt  ×  async batching  ×  streaming
    ↓                  ↓                   ↓                ↓
 3-5x cost        40-60% tokens        60% tokens      10x UX speed
  savings           reduction           savings
```

**Combined: production-grade AIops at minimal cost and latency.**

## Models Used

This project uses [Groq](https://console.groq.com) (free tier):

| Model | Variable | Best For |
|-------|----------|----------|
| `llama-3.1-8b-instant` | `FAST_MODEL` | Classification, extraction, labels |
| `llama-3.3-70b-versatile` | `SMART_MODEL` | RCA, runbooks, complex reasoning |

To switch to Claude (Anthropic), update `src/llm_client.py`:
```python
from anthropic import Anthropic
client = Anthropic()
# Use model="claude-opus-4-6" or "claude-haiku-4-5"
```

## Use Cases

| Folder | Scenario | Techniques Used |
|--------|----------|-----------------|
| `01_log_analysis` | Real-time log triage | Streaming + Model selection |
| `02_incident_rca` | Root cause analysis | Tool use + Smart model |
| `03_alert_triage` | Bulk alert processing | Structured output + Parallel |
| `04_runbook_gen` | Incident runbook creation | Prompt optimization + Caching |
| `05_anomaly_detection` | Anomaly detection chat | Multi-turn + Context management |
| `06_multi_agent_pipeline` | Full AIops pipeline | All techniques combined |

## Requirements

```
groq>=1.1.1
anthropic>=0.86.0
pydantic>=2.0.0
rich>=13.0.0
python-dotenv>=1.0.0
httpx>=0.24.0
```
