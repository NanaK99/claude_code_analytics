# LLM Usage Log

This document describes the AI tools used to build the Claude Code Usage Analytics Platform,
with representative examples of key prompts and how the generated output was validated.

---

## 1. Tools Used

| Tool | Model | Role | Phase |
|------|-------|------|-------|
| **Claude Code** (CLI) | claude-sonnet-4-6 | Primary driver: architecture design, all code generation, test writing, debugging | Throughout |
| **Claude.ai** (co-work) | claude-sonnet-4-6 | Preparing the insights presentation (slide structure, narrative, findings summary) | Deliverable phase |
| **OpenAI Codex** | codex-1 | Spot-check verification of generated modules; attempted UI styling task | Mid / late phases |

---

## 2. Representative Prompt Patterns

The prompts below are summarized from the actual working sessions and grouped by purpose.
Together, they show that AI was used not only for code generation, but also for
understanding the dataset, preserving project knowledge, installing helpful tools, and
reviewing generated output critically.

### Understanding the data first and preserving that knowledge

Before moving into implementation, I used Claude Code to understand the generated telemetry
data and keep that understanding available for later sessions. Representative prompts were:

- asking to generate the data locally and show concrete examples from it
- asking to show a sample event from the dataset
- asking for a short reference document describing the data format and saving it under a
  `knowledge/` directory
- asking for a `CLAUDE.md` file that points future sessions to the `knowledge/` directory
  and reminds the model to pay attention to practical setup details such as the conda
  environment

This was important because the project depends on remembering the event structure, field
names, and local execution setup across multiple sessions. In other words, Claude Code was
used partly as a coding assistant and partly as a project-memory tool.

### Requesting better tooling and reusable skills

I also used Claude Code to improve its own usefulness for the project. A representative
prompt here was asking it to download and set up the
`K-Dense-AI/claude-scientific-skills` repository. The goal was to add more specialized
skills for data analysis and related tasks, so later sessions could work more efficiently
with the dataset and analytics workflow.

### Making architectural and implementation choices explicit

The early design sessions were focused on project structure and constraints rather than
immediate coding. Representative prompts included:

- asking Claude Code to decide the architecture, directory structure, and high-level plan
  based on the assignment PDF and the data-generation code
- clarifying that the project should run fully locally for now
- clarifying that ingestion should be handled by a separate script
- explicitly specifying technology choices such as Streamlit for the dashboard, FastAPI
  for the API layer, and Pydantic for schema definitions

These prompts show that the model was guided with concrete architectural constraints rather
than being asked to make all design decisions on its own.

### Reviewing and questioning generated proposals

The sessions were also iterative and corrective. When Claude Code proposed something that
felt too broad, too complex, or potentially incorrect, it was challenged directly. Examples
of this pattern include:

- asking why a multi-page dashboard was necessary, why those specific pages were chosen,
  and what alternatives existed
- asking whether a short two-month history would be sufficient for ML-oriented forecasting
- pointing out that a forecast bug was not just a trailing-zero row issue, but a real bug
  where the last visible day became zero when the filter window was narrowed
- asking to highlight the "Forecast & Anomalies" tab more clearly in the Streamlit UI

This type of prompting is important to document because it shows that the AI outputs were
actively reviewed, questioned, and corrected, not passively accepted.

### Implementing concrete features after the design was clearer

Overall, these prompt patterns reflect the full development workflow:

1. understand the data and save key knowledge for reuse
2. install or configure better tools
3. shape the architecture with explicit constraints
4. review and question AI output
5. implement and refine concrete features

---

## 3. Validation Approach

Generated code was validated through three complementary layers.

### Automated tests

The main validation layer was automated testing, with a test-first workflow used in the
later structured implementation work: tests were written first, then code was generated or
implemented to satisfy them. In total, the project used 38 tests covering schema (4),
parser (8), ETL (5), and queries (21).

These tests were not just a final check. They were part of the iteration loop: failures
surfaced concrete bugs, and those failures were then fed back into follow-up prompts to
correct the generated code. This was especially useful for query behavior, parsing logic,
and API-facing response handling.

### AI cross-check with Codex

Key modules such as the parser, query layer, and API routers were also reviewed with
OpenAI Codex as a second opinion. This did not replace tests, but it was useful as an
additional review pass on structure and implementation choices. In practice, Codex mostly
confirmed the overall direction and did not find major issues beyond those already exposed
by the test suite.

### Manual review

Manual review remained essential, especially for architecture, correctness, and security.
Architecture decisions such as schema design, API structure, router boundaries, and auth
placement were reviewed before being treated as complete.
