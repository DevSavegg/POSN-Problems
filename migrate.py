import os
import json
import shutil
import glob
import re
from pathlib import Path

# Import pypandoc for robust HTML to LaTeX conversion
import pypandoc

# Configuration
OLD_DIR = "Old"
MIGRATE_DIR = "Migrate"

# Ensure Pandoc is installed on the system
try:
    pypandoc.get_pandoc_version()
except OSError:
    print("Pandoc engine not found. Downloading and installing automatically...")
    pypandoc.download_pandoc()

def html_to_latex(text):
    if not text:
        return ""
    try:
        # Pandoc handles all tags, lists, and special character escaping automatically
        return pypandoc.convert_text(text, 'latex', format='html')
    except Exception as e:
        print(f"Error converting HTML: {e}")
        return text

def migrate_problems():
    Path(MIGRATE_DIR).mkdir(parents=True, exist_ok=True)
    old_path = Path(OLD_DIR)
    problem_files = list(old_path.rglob("problem.json"))

    if not problem_files:
        print(f"No problem.json files found in {OLD_DIR}/")
        return

    print(f"Found {len(problem_files)} problems to migrate.")
    
    # Track successfully migrated tasks for the contest.yaml
    migrated_tasks = []

    for json_path in problem_files:
        with open(json_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Error reading JSON in {json_path}. Skipping.")
                continue
        
        # 1. Extract Metadata & Sanitize Task Name
        raw_task_name = data.get("display_id", json_path.parent.name)
        title = data.get("title", raw_task_name)
        
        task_name = re.sub(r'[^a-zA-Z0-9_]', '_', raw_task_name).strip('_')
        task_name = re.sub(r'_+', '_', task_name)
        
        time_limit_ms = data.get("time_limit", 1000)
        time_limit_sec = time_limit_ms / 1000.0
        if time_limit_sec.is_integer():
            time_limit_sec = int(time_limit_sec)
            
        memory_limit = data.get("memory_limit", 256)

        # 2. Setup Directories
        task_dir = Path(MIGRATE_DIR) / task_name
        input_dir = task_dir / "input"
        output_dir = task_dir / "output"
        statement_dir = task_dir / "statement"
        gen_dir = task_dir / "gen"

        for d in [input_dir, output_dir, statement_dir, gen_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 3. Process Test Cases
        testcase_dir = json_path.parent / "testcase"
        n_input = 0
        
        if testcase_dir.exists():
            in_files = list(testcase_dir.glob("*.in"))
            valid_pairs = []
            for inf in in_files:
                base_name = inf.stem
                outf = testcase_dir / f"{base_name}.out"
                if outf.exists():
                    try:
                        num = int(base_name)
                        valid_pairs.append((num, inf, outf))
                    except ValueError:
                        print(f"Skipping non-numeric testcase: {inf.name} in {task_name}")

            valid_pairs.sort(key=lambda x: x[0])
            n_input = len(valid_pairs)

            for new_idx, (_, old_in, old_out) in enumerate(valid_pairs):
                shutil.copy2(old_in, input_dir / f"input{new_idx}.txt")
                shutil.copy2(old_out, output_dir / f"output{new_idx}.txt")

        # 4. Generate task.yaml with Dynamic Public Testcases
        num_public = min(n_input, 5)
        public_testcases = ", ".join(map(str, range(num_public)))

        yaml_content = f"""name: "{task_name}"
title: "{title}"
time_limit: {time_limit_sec}
memory_limit: {memory_limit}
n_input: {n_input}
public_testcases: {public_testcases}
infile: ""
outfile: ""
token_mode: infinite
"""
        with open(task_dir / "task.yaml", "w", encoding="utf-8") as f:
            f.write(yaml_content)

        # 5. Generate GEN file
        if n_input > 0:
            with open(gen_dir / "GEN", "w", encoding="utf-8") as f:
                f.write(f"# ST: 100\n")
                for i in range(1, n_input + 1):
                    f.write(f"{i}\n")

        # 6. Parse HTML to LaTeX and Generate statement.tex
        raw_desc = data.get('description', {}).get('value', 'No description provided.')
        raw_in_desc = data.get('input_description', {}).get('value', 'No input description provided.')
        raw_out_desc = data.get('output_description', {}).get('value', 'No output description provided.')

        tex_content = f"""\\documentclass{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{a4wide}}

\\begin{{document}}

\\section*{{{title}}}

{html_to_latex(raw_desc)}

\\subsection*{{Input}}
{html_to_latex(raw_in_desc)}

\\subsection*{{Output}}
{html_to_latex(raw_out_desc)}

\\end{{document}}
"""
        with open(statement_dir / "statement.tex", "w", encoding="utf-8") as f:
            f.write(tex_content)

        migrated_tasks.append(task_name)
        print(f"Successfully migrated: {task_name} ({n_input} test cases, {num_public} public)")

    # 7. Generate contest.yaml
    if migrated_tasks:
        print(f"\nGenerating contest.yaml for {len(migrated_tasks)} tasks...")
        
        # Format the tasks list for YAML
        tasks_yaml = "\n".join([f'  - "{t}"' for t in migrated_tasks])
        
        contest_yaml_content = f"""name: "migrated_contest"
description: "Contest auto-generated from problem migration"
tasks:
{tasks_yaml}
users:
  - username: "u1"
    password: "p1"
    ip: null
  - username: "u2"
    password: "p2"
    ip: null
token_mode: infinite
"""
        with open(Path(MIGRATE_DIR) / "contest.yaml", "w", encoding="utf-8") as f:
            f.write(contest_yaml_content)
            
        print("Migration complete!")

if __name__ == "__main__":
    migrate_problems()