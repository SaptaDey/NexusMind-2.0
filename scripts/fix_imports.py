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
    Updates import statements in a Python file to add a 'src.' prefix to 'asr_got_reimagined'.
    
    Scans the specified file for import statements referencing 'asr_got_reimagined' without the 'src.' prefix, modifies them in place to include the prefix, and returns the number of import statements updated.
    
    Args:
        file_path: Path to the Python file to be processed.
    
    Returns:
        The number of import statements that were modified.
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
    """
    Processes all Python files in the source directory, updating import statements for 'asr_got_reimagined' to include the 'src.' prefix.
    
    After processing all files, prints the total number of import statements that were updated.
    """
    python_files = find_python_files(SRC_DIR)
    total_fixes = 0

    for file_path in python_files:
        fixes = fix_imports_in_file(file_path)
        total_fixes += fixes

    print(f"Fixed {total_fixes} imports across all Python files.")

if __name__ == "__main__":
    main()
