#!/usr/bin/env python3
"""
This script extracts a clean version of stage_4_evidence.py by:
1. Reading the original file
2. Fixing indentation and line spacing 
3. Writing the clean version to a new file
"""
import io
import os
import re


def extract_clean_stage4_evidence():
    """
    Cleans and reformats the stage_4_evidence.py file by correcting indentation, spacing, and common syntax issues.
    
    Reads the original file, replaces tabs with spaces, removes trailing whitespace, and inserts newlines between certain adjacent statements to address syntax errors. The cleaned content is saved to a new file with a `.clean` extension. Prints a message indicating success or failure.
    """
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    original_path = os.path.join(project_dir, 'src', 'asr_got_reimagined', 'domain', 'stages', 'stage_4_evidence.py')
    clean_path = os.path.join(project_dir, 'src', 'asr_got_reimagined', 'domain', 'stages', 'stage_4_evidence.py.clean')

    try:
        with open(original_path, encoding='utf-8') as original_file:
            content = original_file.read()

        # Use StringIO to process line by line
        buffer = io.StringIO(content)
        lines = []

        for line in buffer:
            # Fix indentation: tabs to spaces and normalize whitespace
            line = line.replace('\t', '    ')
            # Remove trailing whitespace
            line = line.rstrip() + '\n'
            lines.append(line)

        # Join lines back into a single string
        clean_content = ''.join(lines)

        # Fix common syntax errors
        # 1. Fix lines that need newlines between statements
        clean_content = re.sub(r'(\S+)\s+([a-zA-Z_][a-zA-Z0-9_]*\s*[=:])', r'\1\n\2', clean_content)

        # Write cleaned content
        with open(clean_path, 'w', encoding='utf-8') as clean_file:
            clean_file.write(clean_content)

        print(f"Created cleaned version at {clean_path}")

    except Exception as e:
        print(f"Error extracting clean version: {e}")

if __name__ == "__main__":
    extract_clean_stage4_evidence()
