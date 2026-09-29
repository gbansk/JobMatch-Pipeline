# JobMatch Pipeline: Automated Career Intelligence & Evaluation System

**JobMatch Pipeline** is an automated, local-first candidate evaluation and job discovery application. By orchestrating targeted web scraping, database deduplication, local Large Language Model (LLM) inference, LaTeX document compilation, and dynamic HTML rendering, JobMatch automates job search and application preparation while keeping your career data 100% private.

An end-to-end Python pipeline designed to automate job discovery, fit analysis, and cover letter creation using local AI model evaluation.

### Key Features
* **Automated Job Scraping & Deduplication:** Ingests live job listings into a local SQLite database, automatically filtering out duplicates.
* **Multi-Track Profile Evaluation:** Evaluates each job description against multiple CV profiles (e.g., Developer vs. Management) using local LLMs via Ollama to compute fit scores and skill alignments.
* **Dynamic LaTeX Cover Letters:** Automatically generates tailored `.tex` cover letters and compiles them into clean PDFs for top-scoring matches.
* **Comprehensive HTML Reporting:** Emits structured JSON summaries and renders a visual Jinja2-powered HTML match report to easily review pipeline results.

---

## 🚀 Key Advantages & Architecture Highlights

### 1. Local LLM Inference via Ollama
* **Complete Privacy & Data Sovereignty**: Unlike cloud-based AI tools (e.g., OpenAI, Anthropic APIs) that require uploading personal resume details, work history, and target applications to third-party servers, JobMatch performs all candidate fit evaluations locally on your machine using Ollama.
* **Zero Running Costs**: Perform unlimited job evaluations, prompt adjustments, and cover letter generations without incurring per-token API fees or subscription costs.
* **Model Flexibility**: Seamlessly switch between local models (e.g., `llama3.2`, `mistral`, `qwen2.5`) via CLI flags (`-m`) based on your available CPU/GPU hardware.

### 2. Intelligent Storage & Deduplication (`db.py`)
* **Canonical Title/Company Hashing**: Employs normalized MD5 hashing on company names and titles (e.g., equating "Senior Go Developer" with "Sr Go Developer") to filter out re-posted or duplicate roles across configurable lookback windows.
* **State-Driven Queue Management**: Explicit state tracking (`pending`, `matched`, `skipped_low_score`, `error`) allows you to adjust evaluation criteria or prompts and re-run analysis on existing database entries without re-scraping target platforms.

### 3. Structured Match Insights (`evaluator.py` & `report_builder.py`)
* **Actionable Gap Analysis**: Goes beyond a simple numerical score (0–100) by extracting structured JSON payloads featuring **Key Alignments** (strong matches to leverage) and **Missing Skills** (gaps to address or prepare for in interviews).
* **Robust JSON Handling**: Includes regex-based extraction to handle non-standard model outputs (e.g., when local models output stacked JSON objects or raw meta-data) ensuring raw JSON code never leaks into rendered LaTeX cover letters.
* **Automated Tailored Cover Letters**: Top-scoring roles automatically trigger LaTeX engine compilation (`pdflatex`) to produce personalized cover letter PDFs tailored to the target listing.
* **Daily Digest Summary Report**: Compiles evaluation runs into a single HTML dashboard (`match_report.html`) complete with visual score badges and color-coded gap lists for quick review.

### 4. Modular & Developer-Friendly
* **Test-Driven Design**: Built with a `pytest` test suite verifying Jinja2 template rendering and structural data assertions prior to deployment.
* **Decoupled Execution**: Flexible CLI flags (such as `--skip-scrape`) allow developers to execute scraping, local inference, and HTML report building together or independently.


---

## 🛠️ System Prerequisites & Installation

### 1. Install & Manage Ollama Service
This project uses **Ollama** for local LLM inference to perform job match evaluations. Because LLM models require substantial RAM/VRAM resources, use the following platform-specific management commands to control the service and free up system memory when you are not running the pipeline.

1. **Install Ollama**:
   Download and install Ollama from [ollama.com](https://ollama.com/).

2. **Pull the Default Model**:
   By default, the pipeline uses `llama3.2`. Pull the model before running the application:
   ```bash
   ollama pull llama3.2
   ```

3. **Managing the Service (Start, Stop, Status)**:

   * **Linux (systemd)**:
     ```bash
     # Start Ollama service
     sudo systemctl start ollama

     # Stop Ollama service (frees all RAM/GPU memory immediately)
     sudo systemctl stop ollama

     # Check service status
     sudo systemctl status ollama
     ```

   * **macOS**:
     * **GUI Application**: Quit Ollama from the menu bar item, or reopen it from Applications.
     * **Terminal (Process Control)**:
       ```bash
       # Unload model from active memory
       ollama stop llama3.2

       # Stop Ollama process
       pkill ollama
       ```

   * **Windows (Command Prompt / PowerShell)**:
     * **System Tray App**: Right-click the Ollama icon in the Taskbar system tray and select **Quit Ollama**.
     * **PowerShell / CMD**:
       ```powershell
       # Unload model from active memory
       ollama stop llama3.2

       # Stop Ollama process
       Stop-Process -Name "ollama app" -Force
       ```

4. **Verify Ollama Service**:
   Ensure the service is active and responsive on any platform:
   ```bash
   # List installed models
   ollama list

   # Test query to verify responsiveness
   ollama run llama3.2 "Hello, respond with OK"
   ```

---

### 2. Python Environment Setup
Python **3.10+** is required.

1. **Verify Python Version**:
   * **Linux / macOS**:
     ```bash
     python3 --version
     ```
   * **Windows (PowerShell / CMD)**:
     ```powershell
     python --version
     ```

2. **Clone the Repository**:
   ```bash
   git clone <your-repo-url>
   cd jobmatch
   ```

3. **Create a Virtual Environment**:
   * **Linux / macOS**:
     ```bash
     python3 -m venv venv
     ```
   * **Windows (PowerShell / CMD)**:
     ```powershell
     python -m venv venv
     ```

4. **Activate the Virtual Environment**:
   * **Linux / macOS (Bash / Zsh)**:
     ```bash
     source venv/bin/activate
     ```
   * **Windows (PowerShell)**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   * **Windows (Command Prompt / CMD)**:
     ```cmd
     .\venv\Scripts\activate.bat
     ```

5. **Install Dependencies**:
   * **Linux / macOS**:
     ```bash
     pip install --upgrade pip
     pip install -r requirements.txt
     ```
   * **Windows**:
     ```powershell
     python -m pip install --upgrade pip
     pip install -r requirements.txt
     ```

6. **Verify Environment Setup**:
   * **Linux / macOS**:
     ```bash
     python3 -c "import jobspy, jinja2, sqlite3; print('✅ All core Python imports verified successfully!')"
     ```
   * **Windows**:
     ```powershell
     python -c "import jobspy, jinja2, sqlite3; print('✅ All core Python imports verified successfully!')"
     ```

---

### 3. LaTeX Engine Setup (Optional - for PDF Cover Letters)
If you want automatic compilation of `.tex` files into `.pdf` cover letters, ensure `pdflatex` is installed on your system:

* **Linux (Ubuntu / Debian)**: `sudo apt install texlive-latex-extra`
* **Linux (Arch Linux)**: `sudo pacman -S texlive-bin texlive-core`
* **macOS**: `brew install --cask mactex-no-gui` (or install [MacTeX](https://www.tug.org/mactex/))
* **Windows**: Install [MiKTeX](https://miktex.org/download) or [TeX Live](https://www.tug.org/texlive/windows.html) and ensure `pdflatex` is added to your System PATH.

*(Note: If LaTeX is not installed, the pipeline will still generate `.tex` source files and compile the rendered HTML digest report without crashing).*

---

## 📁 Repository Structure & Configuration

```text
├── db.py                      # SQLite database schema, deduplication, and state tracking
├── evaluator.py               # Ollama prompt building and JSON response parser
├── cover_letter.py            # LaTeX cover letter rendering engine & JSON sanitization
├── report_builder.py          # Jinja2 HTML digest report renderer
├── main.py                    # Pipeline CLI orchestration entry point
├── report_template.html       # Production Jinja2 HTML report layout
├── cover_letter_template.tex  # Base LaTeX cover letter template
├── profiles/                  # Directory for candidate CV profiles (e.g., developer.json)
├── tests/                     # Pytest suite verifying rendering, DB, and pipeline logic
│   ├── conftest.py
│   ├── test_cover_letter.py
│   ├── test_db.py
│   ├── test_evaluator.py
│   ├── test_main.py
│   ├── test_pdf_rendering.py
│   └── test_report_builder.py
├── jobs.db                    # Auto-generated SQLite database (created on first run)
└── output/                    # Pipeline output directory
    ├── match_report.html      # Visual Jinja2 summary report
    ├── report_data.json       # Structured run metadata and scores
    └── pdfs/                  # Generated .tex source files and compiled PDFs
```

### Profiles Configuration (`profiles/`)
Place one or more CV profile JSON files inside the `profiles/` directory (e.g., `developer.json`, `management.json`). The pipeline evaluates each unprocessed job against all profiles in this directory and selects the highest-scoring track for the final match report.

---

## 🚀 Usage & Pipeline Execution

### 1. Full Pipeline Run (Scrape + Evaluate + Report)
Scrape LinkedIn for target roles, evaluate matches with Ollama, generate cover letters, and write the HTML summary:

* **Linux / macOS**:
  ```bash
  python3 main.py -s "Software Engineer" -l "Melbourne, Australia" -n 15
  ```
* **Windows**:
  ```powershell
  python main.py -s "Software Engineer" -l "Melbourne, Australia" -n 15
  ```

---

### 2. Command Line Arguments & Switches

| Argument | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--search` | `-s` | `"Software Engineer"` | Search query string or job title for LinkedIn scraper |
| `--location` | `-l` | `"Melbourne, Australia"` | Target search location |
| `--count` | `-n` | `15` | Target number of job listings to scrape |
| `--profiles` | `-p` | `"profiles"` | Directory containing profile JSON files |
| `--model` | `-m` | `"llama3.2"` | Local Ollama model to execute |
| `--template` | `-t` | `"cover_letter_template.tex"` | Base LaTeX cover letter template path |
| `--outdir` | `-o` | `"generated_docs"` | Directory where generated reports and PDFs are written |
| `--min-score` | | `70` | Minimum match fit score (0–100) required to compile a PDF cover letter |
| `--skip-scrape`| | `False` | Skip scraping and process pending jobs already in `jobs.db` |

---

### 3. Running Without Scraping
To process pending jobs already saved in `jobs.db` without calling the LinkedIn scraper:

* **Linux / macOS**:
  ```bash
  python3 main.py --skip-scrape
  ```
* **Windows**:
  ```powershell
  python main.py --skip-scrape
  ```

---

## 🔄 Re-evaluating Database Jobs

The pipeline tracks job evaluation outcomes using the `verdict` column (`NULL`/`pending`, `matched`, `skipped_low_score`, `error`).

To force the pipeline to re-process previously evaluated job records:

* **Linux / macOS**:
  ```bash
  # Reset all job verdicts in SQLite back to pending
  sqlite3 jobs.db "UPDATE job_listings SET verdict = 'pending';"

  # Run evaluation on the queued records
  python3 main.py --skip-scrape
  ```

* **Windows (PowerShell)**:
  ```powershell
  # Reset all job verdicts in SQLite back to pending
  sqlite3 jobs.db "UPDATE job_listings SET verdict = 'pending';"

  # Run evaluation on the queued records
  python main.py --skip-scrape
  ```

To re-process only the first 2 job listings in your database:
* **Linux / macOS**:
  ```bash
  sqlite3 jobs.db "UPDATE job_listings SET verdict = 'pending' WHERE rowid IN (SELECT rowid FROM job_listings LIMIT 2);"
  python3 main.py --skip-scrape
  ```
* **Windows**:
  ```powershell
  sqlite3 jobs.db "UPDATE job_listings SET verdict = 'pending' WHERE rowid IN (SELECT rowid FROM job_listings LIMIT 2);"
  python main.py --skip-scrape
  ```

## ⚠️ Known Model Quirks & Edge Cases

* **Stacked JSON Outputs:** Smaller local models (like `llama3.2`) can output multiple JSON objects back-to-back instead of a single merged object. `cover_letter.py` automatically parses and isolates `cover_letter_body` via regex to prevent metadata from appearing in rendered PDFs.
* **Missing Contact Fields:** If optional profile details (like phone or full address) are missing, double line breaks (`\\`) in the LaTeX template are automatically cleaned up via regex to prevent LaTeX compilation errors.

---

## 🧪 Testing

Run the unit test suite with `pytest` to verify template rendering and pipeline data assertions:

```bash
pytest
```