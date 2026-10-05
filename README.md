# Patent Taxonomy Extraction Pipeline

This repository contains a LangGraph-based AI pipeline designed to automate the extraction of complex technical properties (e.g., Tensile Strength, Modulus, Density) from patent documents into a structured Excel taxonomy. 

It uses Large Language Models (LLMs) to synthesize data ranges, correlate multidimensional properties (like MD/TD), and filter for inventive examples based on human-provided reasoning comments.

## Prerequisites & Installation

1. **Python & `uv`:** The project uses `uv` for fast Python dependency management. Make sure `uv` is installed on your system.
2. **Dependencies:** Install the project dependencies by running:
   ```bash
   uv sync
   ```
3. **API Keys:** You must configure your API keys (e.g., OpenAI, Google Patents API) in a `.env` file in the root directory.

## Execution Guide

### Basic Execution (All Patents)
To process all patents found in the specified Excel sheet, run the pipeline using the following command:

```bash
uv run python run.py --excel "data/review/Fresh_Test_Copy (1).xlsx" --sheet "Human reasoning" --header-row 3 --reasoning "data/review/Fresh_Test_Copy (1).xlsx"
```

### Targeted Execution (Single Patent)
If you are testing changes or only want to process a single patent to save costs/time, use the `--patent` flag followed by the patent number:

```bash
uv run python run.py --excel "data/review/Fresh_Test_Copy (1).xlsx" --sheet "Human reasoning" --header-row 3 --reasoning "data/review/Fresh_Test_Copy (1).xlsx" --patent EP3350236B1
```

---

## Command Line Arguments Reference

- `--excel`: **(Required)** Path to the target Excel file where data should be read from and written to.
- `--sheet`: **(Required)** The name of the specific sheet inside the Excel workbook to process (e.g., `"Human reasoning"`).
- `--header-row`: The 1-indexed row number where the "leaf" column headers are located (e.g., `3`). 
- `--reasoning`: Path to the Excel file containing human reasoning comments. This enables the LLM to understand *why* and *how* a human mapped a value, improving extraction accuracy. Usually, this points to the same Excel file.
- `--patent`: *(Optional)* A specific patent number to process. If omitted, the script auto-detects all patents in the sheet and processes them sequentially.

## Important Notes & Troubleshooting

1. **Close Excel Before Running:** Always ensure the target Excel file is **CLOSED** in Microsoft Excel before executing `run.py`. If the file is open, the script will encounter a `Permission Denied` error when it attempts to save the updated data at the end of the pipeline.
2. **Pipeline Traces:** For every patent processed, a detailed Markdown trace file is generated in `logs/traces/<PATENT_NUMBER>_trace.md`. This is invaluable for debugging LLM extractions, as it shows exactly what text chunks were provided and the exact prompt responses.
3. **Data Formatting:** The pipeline writes the extracted values to the Excel file using two phases:
   - **Phase 1 (Raw Extraction):** Extracts and synthesizes raw ranges (e.g., `MD: 51 - 158 g/mil | TD: 312 - 430 g/mil`).
   - **Phase 2 (Formatting):** Ensures the final string written to the cell strictly adheres to the requested taxonomy format.


Run

uv run python run.py --excel "data/review/Fresh_Test_Copy (1).xlsx" --sheet "Human reasoning" --header-row 1 --start-row 4 --reasoning "data/review/Fresh_Test_Copy (1).xlsx"

Pipeline