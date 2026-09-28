import json
import os
import re
import subprocess

DEFAULT_OLLAMA_MODEL = "llama3.2"

def strip_ansi_codes(text: str) -> str:
    """Removes ANSI escape codes, terminal control artifacts, and restores word spacing."""
    if not text:
        return ""
    
    # Remove ANSI terminal escape sequences
    ansi_regex = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_regex.sub('', text)

    # Remove residual terminal cursor/delete sequences like [6D or [4D
    cleaned = re.sub(r'\[\d+[A-Za-dKk]', '', cleaned)

    # Clean up double spacing while preserving double newlines for paragraphs
    paragraphs = cleaned.split("\n\n")
    cleaned_paragraphs = []
    for p in paragraphs:
        # Re-space single lines cleanly
        single_line = " ".join(p.split())
        cleaned_paragraphs.append(single_line)

    return "\n\n".join(cleaned_paragraphs)


def build_ollama_prompt(cv_data: dict, job_description: str) -> str:
    """Builds the prompt instructing Ollama to evaluate job fit and generate cover letter content."""
    basics = cv_data.get("basics", {})
    name = basics.get("name", "Candidate")
    skills = ", ".join(cv_data.get("skills", []))
    
    experience_list = cv_data.get("work", cv_data.get("experience", []))
    exp_summary = ""
    for exp in experience_list:
        company = exp.get("company", exp.get("name", ""))
        position = exp.get("position", exp.get("role", ""))
        summary = exp.get("summary", "")
        exp_summary += f"- {position} at {company}: {summary}\n"

    prompt = f"""
You are an expert career consultant evaluating job compatibility for {name}.

Candidate Skills: {skills}
Candidate Experience:
{exp_summary}

Job Description:
{job_description}

Instructions:
Return ONLY a raw JSON object (no markdown formatting, no code blocks) with the following key/value pairs:
- "fit_score": integer between 0 and 100 based on skill overlap and experience relevance.
- "key_alignments": a list of 2 to 4 concise bullet points highlighting key matching skills or background strengths.
- "missing_skills": a list of 1 to 3 concise bullet points identifying key missing skills or gaps relative to the job.
- "cover_letter_body": a 3-paragraph tailored cover letter body written in the FIRST PERSON ("I", "my", "me").
"""
    return prompt.strip()


def query_ollama(prompt: str, model: str = "llama3.2") -> str:
    """Queries local Ollama instance via subprocess with clean output encoding."""
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8"
        )
        return strip_ansi_codes(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Ollama execution failed: {e}")


def parse_llm_response(response: str) -> tuple[str, int, list[str], list[str]]:
    """Parses JSON response from LLM or falls back cleanly if response formatting deviates."""
    cleaned = response.strip()
    
    # Strip Markdown code fence blocks if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        score = int(data.get("fit_score", 75))
        body_text = str(data.get("cover_letter_body", "")).strip()
        key_alignments = data.get("key_alignments", [])
        missing_skills = data.get("missing_skills", [])
        
        if not isinstance(key_alignments, list):
            key_alignments = []
        if not isinstance(missing_skills, list):
            missing_skills = []

        return body_text, score, key_alignments, missing_skills
    except json.JSONDecodeError:
        # Fallback for legacy FIT_SCORE text responses
        score = 75
        body_lines = []
        for line in response.strip().split("\n"):
            if "FIT_SCORE:" in line:
                match = re.search(r"\d+", line)
                if match:
                    score = int(match.group())
            else:
                body_lines.append(line)

        body_text = "\n".join(body_lines).strip()
        return body_text, score, [], []


def evaluate_job(
    cv_path: str,
    job_description: str,
    model: str = DEFAULT_OLLAMA_MODEL,
    template_path: str = "cover_letter_template.tex",
    output_tex: str = "output/pdf/cover_letter.tex"
) -> tuple[str, int, list[str], list[str]]:
    """Loads CV, queries Ollama, renders cover letter, and returns (body_text, score, key_alignments, missing_skills)."""
    with open(cv_path, "r", encoding="utf-8") as f:
        cv_data = json.load(f)

    prompt = build_ollama_prompt(cv_data, job_description)
    raw_response = query_ollama(prompt, model=model)
    body_text, fit_score, key_alignments, missing_skills = parse_llm_response(raw_response)

    return body_text, fit_score, key_alignments, missing_skills
