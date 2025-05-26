# Git Directory

This folder contains modules for defining graph primitives, confidence models, and persistence logic used in conjunction with version control workflows.

## Project Structure

```text
.
├── graph_elements.py  # Node, Edge, Hyperedge models
├── confidence.py      # Confidence vector models
├── graph_database.py  # Graph persistence layer
└── README.md          # Project documentation
```

## File Descriptions

- **graph_elements.py**: Defines the core graph components (Node, Edge, Hyperedge).  
- **confidence.py**: Implements confidence vector models for weighting or evaluating graph relationships.  
- **graph_database.py**: Provides persistence logic and database integration for storing and querying graph data.  
- **README.md**: This documentation file.

## Getting Started

Import and use the modules in your application:

```python
from git.graph_elements import Node, Edge, Hyperedge
from git.confidence import ConfidenceModel
from git.graph_database import GraphDatabase

# Example:
db = GraphDatabase("sqlite:///graphs.db")
node = Node(id=1, label="Start")
edge = Edge(source=node, target=node)
confidence = ConfidenceModel.initialize_default()
db.save(node, edge, confidence)
```