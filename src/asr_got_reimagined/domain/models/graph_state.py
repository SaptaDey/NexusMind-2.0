import uuid
from typing import Any, Optional, TypeVar

import networkx as nx
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from .common import TimestampedModel
from .graph_elements import Edge, Hyperedge, Node  # Import your domain models

TNode = TypeVar("TNode", bound=Node)
TEdge = TypeVar("TEdge", bound=Edge)
THyperedge = TypeVar("THyperedge", bound=Hyperedge)


class GraphStatistics(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    hyperedge_count: int = 0
    layer_count: int = 0
    # Add more specific stats as needed, e.g., counts by node_type


class ASRGoTGraph(TimestampedModel):
    """
    Core graph data structure for ASR-GoT, using NetworkX internally.
    Implements aspects of the mathematical formalism from P1.11.
    Manages domain model instances (Node, Edge, Hyperedge).
    """

    id: str = Field(default_factory=lambda: f"graph-{uuid.uuid4()}")
    # We store domain model instances in dictionaries for quick access by ID
    nodes: dict[str, Node] = Field(default_factory=dict)
    edges: dict[str, Edge] = Field(default_factory=dict)  # Edge ID to Edge object
    hyperedges: dict[str, Hyperedge] = Field(default_factory=dict)

    # Layer structure (P1.23)
    layers: dict[str, set[str]] = Field(
        default_factory=dict
    )  # Layer name to set of node_ids

    # Internal NetworkX graph for topology and algorithms
    # It will store node IDs and edge IDs (or tuples for edges)
    # Node attributes in nx_graph can point back to Node objects or store lightweight data
    nx_graph: nx.MultiDiGraph = Field(default_factory=nx.MultiDiGraph, exclude=True)

    # Metadata about the graph itself, e.g., current stage, overall query
    graph_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("nx_graph", mode="before")
    @classmethod
    def init_nx_graph(cls, v):
        return v or nx.MultiDiGraph()

    def add_node(self, node: Node) -> None:
        if node.id in self.nodes:
            logger.warning(f"Node with ID {node.id} already exists. Overwriting.")
        self.nodes[node.id] = node
        # Add to NetworkX graph. Store essential data for quick access, or just the ID.
        # For simplicity, we can store the full Pydantic model dict, but be mindful of memory
        # if graphs are huge. Or, just store key attributes.
        self.nx_graph.add_node(
            node.id,
            type=node.type.value,
            label=node.label,
            confidence=node.confidence.model_dump(),
        )  # Add pydantic model directly
        logger.debug(f"Added node '{node.label}' (ID: {node.id}) to graph.")
        if node.metadata.layer_id:
            self.assign_node_to_layer(node.id, node.metadata.layer_id)
        self.touch()

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def remove_node(self, node_id: str) -> Optional[Node]:
        node = self.nodes.pop(node_id, None)
        if node:
            if self.nx_graph.has_node(node_id):
                self.nx_graph.remove_node(node_id)
            # Also remove from any layers
            for layer_name, node_ids_in_layer in list(self.layers.items()):
                if node_id in node_ids_in_layer:
                    node_ids_in_layer.remove(node_id)
                    if not node_ids_in_layer:  # Remove layer if empty
                        del self.layers[layer_name]
            # TODO: Also handle removal of incident edges & hyperedges
            logger.info(
                f"Removed node ID: {node_id}. Further cleanup of edges/hyperedges might be needed."
            )
            self.touch()
        return node

    def add_edge(self, edge: Edge) -> None:
        if edge.id in self.edges:
            logger.warning(f"Edge with ID {edge.id} already exists. Overwriting.")
        if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
            raise ValueError(
                f"Cannot add edge '{edge.id}': Source or target node does not exist."
            )
        self.edges[edge.id] = edge
        # Use edge.id as the key in MultiDiGraph for potentially multiple edges between nodes
        self.nx_graph.add_edge(
            edge.source_id,
            edge.target_id,
            key=edge.id,  # Important for MultiDiGraph to distinguish multiple edges
            type=edge.type.value,
            id=edge.id,
            confidence=edge.confidence,
        )
        logger.debug(
            f"Added edge '{edge.type.value}' (ID: {edge.id}) from {edge.source_id} to {edge.target_id}."
        )
        self.touch()

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        return self.edges.get(edge_id)

    def remove_edge(self, edge_id: str) -> Optional[Edge]:
        edge = self.edges.pop(edge_id, None)
        if edge:
            if self.nx_graph.has_edge(edge.source_id, edge.target_id, key=edge_id):
                self.nx_graph.remove_edge(edge.source_id, edge.target_id, key=edge_id)
            logger.info(f"Removed edge ID: {edge_id}.")
            self.touch()
        return edge

    def add_hyperedge(self, hyperedge: Hyperedge) -> None:
        if hyperedge.id in self.hyperedges:
            logger.warning(
                f"Hyperedge with ID {hyperedge.id} already exists. Overwriting."
            )
        for node_id in hyperedge.node_ids:
            if node_id not in self.nodes:
                raise ValueError(
                    f"Cannot add hyperedge '{hyperedge.id}': Node {node_id} does not exist."
                )
        self.hyperedges[hyperedge.id] = hyperedge
        # Representation in nx_graph for hyperedges can be tricky.
        # Common approaches:
        # 1. Star graph: Create a central "hyperedge node" and connect all involved nodes to it.
        # 2. Clique: Add edges between all pairs of nodes in the hyperedge (can make graph dense).
        # For now, we just store it separately. Visualization/algorithms might need to handle it.
        logger.debug(
            f"Added hyperedge (ID: {hyperedge.id}) connecting nodes: {hyperedge.node_ids}."
        )
        self.touch()

    def get_hyperedge(self, hyperedge_id: str) -> Optional[Hyperedge]:
        return self.hyperedges.get(hyperedge_id)

    def remove_hyperedge(self, hyperedge_id: str) -> Optional[Hyperedge]:
        hyperedge = self.hyperedges.pop(hyperedge_id, None)
        if hyperedge:
            logger.info(f"Removed hyperedge ID: {hyperedge_id}.")
            self.touch()
        return hyperedge

    def assign_node_to_layer(self, node_id: str, layer_id: str):
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found.")
        if layer_id not in self.layers:
            self.layers[layer_id] = set()
            logger.info(f"Created new layer: {layer_id}")
        self.layers[layer_id].add(node_id)
        # Update node's metadata as well
        node = self.get_node(node_id)
        if node:
            node.metadata.layer_id = layer_id
            node.touch()
        self.touch()

    def get_statistics(self) -> GraphStatistics:
        """
        Returns a summary of the graph's statistics, including counts of nodes, edges, hyperedges, and layers.
        
        Returns:
            A GraphStatistics instance with the current counts for nodes, edges, hyperedges, and layers.
        """
        return GraphStatistics(
            node_count=len(self.nodes),
            edge_count=len(self.edges),
            hyperedge_count=len(self.hyperedges),
            layer_count=len(self.layers),
        )

    def get_neighbors(self, node_id: str) -> list[str]:
        """
        Returns a list of neighbor node IDs for the specified node.
        
        If the node does not exist in the graph, returns an empty list.
        """
        if node_id not in self.nx_graph:
            return []
        return list(self.nx_graph.neighbors(node_id))

    def get_predecessors(self, node_id: str) -> list[str]:
        """
        Returns a list of predecessor node IDs for the specified node.
        
        If the node does not exist in the graph, returns an empty list.
        """
        if node_id not in self.nx_graph:
            return []
        return list(self.nx_graph.predecessors(node_id))

    def get_successors(self, node_id: str) -> list[str]:
        """
        Returns a list of successor node IDs for the given node.
        
        If the node is not present in the graph, returns an empty list.
        """
        if node_id not in self.nx_graph:
            return []
        return list(self.nx_graph.successors(node_id))

    def to_serializable_dict(self) -> dict[str, Any]:
        """
        Serializes the graph into a dictionary suitable for API responses.
        
        The returned dictionary includes the graph's ID, lists of serialized nodes, edges, and hyperedges, layer assignments, metadata, statistics, and ISO-formatted timestamps. The internal NetworkX graph is excluded from the output.
        
        Returns:
            A dictionary representation of the graph for external consumption.
        """
        return {
            "id": self.id,
            "nodes": [
                node.model_dump(exclude_none=True) for node in self.nodes.values()
            ],
            "edges": [
                edge.model_dump(exclude_none=True) for edge in self.edges.values()
            ],
            "hyperedges": [
                h.model_dump(exclude_none=True) for h in self.hyperedges.values()
            ],
            "layers": {name: list(node_ids) for name, node_ids in self.layers.items()},
            "graph_metadata": self.graph_metadata,
            "statistics": self.get_statistics().model_dump(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    # In Pydantic v2, model_rebuild is used if you dynamically add fields to models,
    # but for managing the graph structure, manual updates to nx_graph are fine.
    # We need to ensure nx_graph is not directly part of serialization if it becomes too complex.
    # The `exclude=True` for nx_graph handles this for default Pydantic serialization.

    class Config:
        arbitrary_types_allowed = True  # For NetworkX graph object
