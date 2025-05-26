# Git Module

This directory provides utilities and scripts for Git-related operations in the project.

## Overview

- Custom Git commands to streamline repository workflows  
- Hook scripts for automated checks on code changes  
- Graph utilities for visualizing and managing repository history data  

## Project Structure

```
git/
├── commands/
│   ├── init.py                    # Repository initialization commands
│   ├── commit.py                  # Enhanced commit workflows
│   └── push.py                    # Remote push and management tools
├── hooks/
│   ├── pre-commit                 # Lint and test runner pre-commit hook
│   └── pre-push                   # Test suite pre-push hook
├── graph/
│   ├── graph_elements.py          # Node, Edge, and Hyperedge models
│   ├── confidence.py              # Confidence vector models
│   └── utils.py                   # Helper functions for graph data
└── README.md                      # This file
```

## Usage

1. Install the Git hooks:
   ```bash
   ln -s ../../git/hooks/pre-commit .git/hooks/pre-commit
   ln -s ../../git/hooks/pre-push   .git/hooks/pre-push
   ```
2. Run custom commands:
   ```bash
   python git/commands/init.py
   ```

## License

This module is released under the MIT License.