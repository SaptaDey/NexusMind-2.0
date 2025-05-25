#!/usr/bin/env python
"""
Script to fix Python module imports by adding 'src.' prefix to 'asr_got_reimagined' imports.
"""

import os
import re
from typing import List

# Directory to start scanning for Python files
ROOT_DIR = r"c:\Users\sapta\OneDrive\Desktop\NexusMind"
SRC_DIR = os.path.join(ROOT_DIR, 'src')

def find_python_files(directory: str) -> List[str]:
    """Find all Python files recursively in a directory."""
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def fix_imports_in_file(file_path: str) -> int:
    """
    Fix imports in a Python file by adding 'src.' prefix to 'asr_got_reimagined' imports.
    Returns the number of imports fixed.
    """
    with open(file_path, encoding='utf-8') as f:
        content = f.read()

    # Pattern to match imports that start with 'asr_got_reimagined' but not 'src.asr_got_reimagined'
    pattern = r'(from|import)\s+(?!src\.)asr_got_reimagined'
    replacement = r'\1 src.asr_got_reimagined'

    # Only proceed if matches are found
    new_content, num_replacements = re.subn(pattern, replacement, content)
    if num_replacements > 0:
        print(f"Fixing {num_replacements} imports in {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

    return num_replacements

def main() -> None:
    """Main function to find and fix Python imports."""
    python_files = find_python_files(SRC_DIR)
    total_fixes = 0

    for file_path in python_files:
        fixes = fix_imports_in_file(file_path)
        total_fixes += fixes

    print(f"Fixed {total_fixes} imports across all Python files.")

if __name__ == "__main__":
    main()
