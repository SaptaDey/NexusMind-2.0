# Git Directory

This directory contains Git-related models and utilities used throughout the project.

## Project Structure

├── graph_elements.py         # Node, Edge, Hyperedge models  
├── confidence.py             # Confidence vector models  
├── pre-commit-hooks/         # Custom Git hook scripts  
│   ├── check_format.sh       # Ensure code formatting before commits  
│   └── lint_check.sh         # Run linter before commits  
└── setup_hooks.py            # Installer for Git hooks  

## Usage

1. Install Git hooks by running:
   ```bash
   python setup_hooks.py
   ```
2. Add or modify hook scripts under `pre-commit-hooks/`.
3. See individual modules for API and model details.