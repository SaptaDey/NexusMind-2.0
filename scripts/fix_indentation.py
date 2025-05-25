#!/usr/bin/env python3
"""
This script fixes indentation issues in Python files by re-formatting them.
"""
import os
import sys


def fix_indentation_issues(filepath: str) -> None:
    """
    Reformats a Python file to replace tabs with spaces and remove trailing whitespace.
    
    Opens the specified file, replaces all tab characters with four spaces, trims trailing whitespace from each line, and writes the cleaned content back to the file. Prints an error message if the file cannot be processed.
    """
    try:
        with open(filepath, encoding='utf-8') as file:
            lines = file.readlines()

        # Remove any odd spacing and control characters
        cleaned_lines = []
        for line in lines:
            # Replace tabs with 4 spaces
            cleaned_line = line.replace('\t', '    ')
            # Remove trailing whitespace
            cleaned_line = cleaned_line.rstrip() + '\n'
            cleaned_lines.append(cleaned_line)

        # Write the fixed content back
        with open(filepath, 'w', encoding='utf-8') as file:
            file.writelines(cleaned_lines)

        print(f"Fixed indentation in {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")


def find_python_files(start_dir: str):
    """Find all Python files in the given directory and its subdirectories."""
    for root, _, files in os.walk(start_dir):
        for file in files:
            if file.endswith('.py'):
                yield os.path.join(root, file)


def main():
    """
    Processes all Python files in the 'src' directory to fix indentation issues.
    
    Determines the base directory from the first command-line argument or defaults to the parent of the script's directory. If the 'src' subdirectory exists, applies indentation fixes to each Python file within it; otherwise, prints an error and exits.
    """
    # Get the base directory of the project
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    src_dir = os.path.join(base_dir, 'src')

    if not os.path.exists(src_dir):
        print(f"Error: Source directory '{src_dir}' not found.")
        return

    # Process each Python file
    for python_file in find_python_files(src_dir):
        fix_indentation_issues(python_file)


if __name__ == "__main__":
    main()
