# Bayyinah | بيّنة

Bayyinah is a bilingual, multi-agent web application that transforms Excel and CSV files into clear, traceable analytics and interactive dashboards.

بيّنة منصة ثنائية اللغة تحوّل ملفات Excel وCSV إلى تحليلات واضحة ولوحات تفاعلية بأرقام قابلة للتتبّع.

## Live Demo

[Open Bayyinah](https://excel-analytics-app.vercel.app/)

## Key Features

- Upload and inspect XLSX or CSV files.
- Detect missing values and choose automatic treatment, manual entry, or row deletion.
- Generate verified KPIs, charts, tables, and detailed insights.
- Ask questions about the analyzed dataset in natural language.
- Switch between Arabic and English.
- Keep calculations deterministic and traceable instead of relying on the language model for arithmetic.

## Multi-Agent Workflow

1. **Data Cleaning Agent** — validates structure, profiles columns, and handles data-quality issues.
2. **Analysis & Calculation Agent** — builds the analysis plan and computes verified results.
3. **Dashboard & Insights Agent** — validates the output and prepares charts, tables, and insights.

```text
XLSX / CSV → Data Loader → Cleaning Agent → Analysis Agent → Dashboard Agent → Interactive Dashboard
```

## Tech Stack

- **Frontend:** Next.js, React, TypeScript, Zod, ECharts
- **Backend:** FastAPI, Python, Pandas, DuckDB, Pydantic
- **AI Workflow:** LangGraph with Groq or Ollama
- **Deployment:** Vercel and PythonAnywhere

## Repository Structure

```text
frontend/   Next.js user interface
backend/    FastAPI API and multi-agent workflow
samples/    Sample datasets for testing
scripts/    Development and validation utilities
```

> No real API keys or uploaded user datasets are stored in this repository.
