# Claude Code Analytics Platform

A telemetry analytics platform for exploring Claude Code usage data.

## Setup

### Prerequisites

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution)
- pip 26.0.1 (installed automatically inside the conda environment)

### Create and activate the environment

`environment.yml` references `requirements.txt` via `-r requirements.txt`, so both files must be present.

```bash
conda env create -f environment.yml
conda activate provectus_task
```

### Update an existing environment

```bash
conda env update -f environment.yml --prune
conda activate provectus_task
```

### Verify the installation

```bash
python -c "import duckdb, streamlit, pandas, plotly, tqdm, pytest; print('All dependencies OK')"
```

## Project Structure

```
.
├── environment.yml        # Conda environment specification
├── requirements.txt       # pip-compatible dependency list
├── data_generation/       # Data generation scripts (do not modify)
├── knowledge/             # Reference documentation
├── src/                   # Application source code
├── tests/                 # Test suite
└── app.py                 # Streamlit dashboard (created in later tasks)
```

## Running Tests

```bash
pytest tests/
```

## Running the Dashboard

```bash
streamlit run app.py
```
