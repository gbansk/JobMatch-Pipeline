import os
import shutil
import subprocess

def find_pdflatex_binary() -> str:
    """Finds the pdflatex executable path across standard macOS install locations."""
    path = shutil.which("pdflatex")
    if path:
        return path
        
    common_paths = [
        "/Library/TeX/texbin/pdflatex",
        "/usr/local/bin/pdflatex",
        "/usr/local/texlive/2026/bin/universal-darwin/pdflatex",
        "/usr/local/texlive/2025/bin/universal-darwin/pdflatex",
        "/usr/local/texlive/2024/bin/universal-darwin/pdflatex",
        "/opt/homebrew/bin/pdflatex"
    ]
    for p in common_paths:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
            
    return ""

def compile_latex_to_pdf(tex_content: str, output_filename: str = "cover_letter") -> str:
    """
    Writes raw LaTeX string to disk, compiles it into a PDF using pdflatex,
    and cleans up auxiliary TeX files. Returns path to generated PDF.
    """
    pdflatex_bin = find_pdflatex_binary()
    if not pdflatex_bin:
        print("   ❌ Error: 'pdflatex' binary not found. Make sure BasicTeX/MacTeX is installed and in your PATH.")
        return ""

    build_dir = os.path.join(os.getcwd(), "generated_docs")
    os.makedirs(build_dir, exist_ok=True)
    
    tex_file = os.path.join(build_dir, f"{output_filename}.tex")
    pdf_file = os.path.join(build_dir, f"{output_filename}.pdf")
    
    # 1. Write LaTeX content to file
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(tex_content)

    # 2. Run pdflatex command with strict non-interactive flags
    try:
        cmd = [
            pdflatex_bin,
            "-interaction=batchmode",  # Suppresses interactive prompts entirely
            "-halt-on-error",
            f"-output-directory={build_dir}",
            tex_file
        ]
        
        env = os.environ.copy()
        env["PATH"] = f"/Library/TeX/texbin:/usr/local/bin:{env.get('PATH', '')}"
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, env=env)
            
    except Exception as e:
        print(f"   ❌ Subprocess Error: {e}")

    # 3. Clean up auxiliary files (.aux, .log, .out)
    for ext in [".aux", ".log", ".out"]:
        aux_path = os.path.join(build_dir, f"{output_filename}{ext}")
        if os.path.exists(aux_path):
            os.remove(aux_path)

    # 4. Confirm PDF exists on disk
    if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 0:
        print(f"   📄 Successfully generated PDF: {pdf_file}")
        return pdf_file
    else:
        print(f"   ❌ PDF compilation failed for: {output_filename}")
        return ""
