# MyGraphProject

A Python library for modeling graph structures and performing confidence vector analysis.

## Features

- Define graph elements (nodes, edges, hyperedges)
- Compute and manage confidence vectors
- (Graph state management module has been removed)

## Installation

```bash
pip install mygraphproject
```

## Usage

```python
from mygraphproject.graph_elements import Node, Edge
from mygraphproject.confidence import ConfidenceVector

# Example usage
node_a = Node(id=1, label="A")
node_b = Node(id=2, label="B")
edge = Edge(source=node_a, target=node_b)
conf = ConfidenceVector([0.9, 0.8, 0.95])
```

## Project Structure

```text
MyGraphProject/
├── src/
│   ├── graph_elements.py         # Node, Edge, Hyperedge models
│   ├── confidence.py             # Confidence vector models
│   └── utils.py                  # Utility functions
├── tests/
│   ├── test_graph_elements.py
│   └── test_confidence.py
├── docs/
│   └── usage.md
├── .gitignore
└── README.md
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on GitHub.

## License

This project is licensed under the MIT License.