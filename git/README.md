# Graph Processing Library

A Python library for modeling and processing graph structures, including nodes, edges, and confidence vectors.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```python
from src.graph_elements import Node, Edge
from src.confidence import ConfidenceVector

# Example usage
node = Node(id="A")
edge = Edge(source=node, target=node)
cv = ConfidenceVector([0.9, 0.8])
```

## Project Structure

```text
.
├── README.md                     # Project documentation
├── src
│   ├── __init__.py               # Package initializer
│   ├── main.py                   # Entry point
│   ├── graph_elements.py         # Node, Edge, Hyperedge models
│   ├── confidence.py             # Confidence vector models
│   └── utils.py                  # Utility functions
└── tests
    ├── test_graph_elements.py    # Tests for graph elements
    └── test_confidence.py        # Tests for confidence vector models
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

MIT License. See LICENSE file for details.