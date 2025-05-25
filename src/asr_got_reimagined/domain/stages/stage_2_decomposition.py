from typing import Any

from loguru import logger  # type: ignore

from src.asr_got_reimagined.config import Settings
from src.asr_got_reimagined.domain.models.common import (
    ConfidenceVector,
    EpistemicStatus,
)
from src.asr_got_reimagined.domain.models.common_types import GoTProcessorSessionData
from src.asr_got_reimagined.domain.models.graph_elements import (
    Edge,
    EdgeMetadata,
    EdgeType,
    Node,
    NodeMetadata,
    NodeType,
)
from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph

from .base_stage import BaseStage, StageOutput  # Ensure StageOutput is imported


class DecompositionStage(BaseStage):
    stage_name: str = "DecompositionStage"

    def __init__(self, settings: Settings):
        """
        Initializes the DecompositionStage with default decomposition dimensions and confidence values from settings.
        
        Args:
            settings: Configuration settings containing default parameters for decomposition.
        """
        super().__init__(settings)
        # P1.2: Get default dimensions from settings.yaml
        self.default_dimensions_config = (
            self.default_params.default_decomposition_dimensions
        )
        self.dimension_confidence_values = (
            self.default_params.dimension_confidence
        )  # C_dim from P1.2

    async def execute(
        self, graph: ASRGoTGraph, current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        """
        Performs the decomposition stage by creating dimension nodes and edges linked to a root node in the graph.
        
        Retrieves the root node and initial disciplinary tags from the session context. Uses either custom or default decomposition dimensions to generate new dimension nodes, each linked to the root node with a decomposition edge. Updates the graph with these nodes and edges, and returns a summary, metrics, and context update. If the root node is missing or not found, returns a failure output with an error message.
        
        Args:
            graph: The graph to which decomposition dimension nodes and edges will be added.
            current_session_data: Session data containing accumulated context and operational parameters.
        
        Returns:
            A StageOutput containing a summary of the decomposition, metrics on nodes and edges created, and a context update with the IDs of created dimension nodes.
        """
        self._log_start(
            current_session_data.session_id
        )  # Import InitializationStage here to access its stage_name
        from .stage_1_initialization import InitializationStage

        # Retrieve root_node_id and initial_disciplinary_tags from the accumulated context
        # GoTProcessor now stores the dictionary from next_stage_context_update directly.
        initialization_data_from_context = current_session_data.accumulated_context.get(
            InitializationStage.stage_name, {}
        )

        root_node_id = initialization_data_from_context.get("root_node_id")
        # Use initial tags for dimensions, or allow override by operational_params
        default_disciplinary_tags = set(
            initialization_data_from_context.get(
                "initial_disciplinary_tags",
                self.default_params.default_disciplinary_tags,
            )
        )

        if not root_node_id or not graph.get_node(root_node_id):
            logger.error(
                "Root node ID not found in session context or graph. Cannot proceed with decomposition."
            )
            # This indicates a failure in a previous stage or incorrect context passing.
            # It might be better to raise an exception or return an error state.
            return StageOutput(
                summary="Decomposition failed: Root node not found.",
                metrics={"dimensions_created": 0},
                next_stage_context_update={
                    self.stage_name: {
                        "error": "Root node missing",
                        "dimension_node_ids": [],
                    }
                },
            )

        # Get custom dimensions from operational parameters, or use defaults from config (P1.2)
        operational_params = current_session_data.accumulated_context.get(
            "operational_params", {}
        )
        custom_dimensions_input = operational_params.get("decomposition_dimensions")

        if custom_dimensions_input and isinstance(custom_dimensions_input, list):
            # For simplicity, we'll assume it's correctly formatted if provided.            # In a robust system, Pydantic models would validate this input too.
            dimensions_to_create: list[dict[str, Any]] = custom_dimensions_input
            logger.info(
                "Using custom decomposition dimensions provided in operational parameters."
            )
        else:
            # Convert Pydantic models from settings to simple dicts for processing if needed,
            # or directly use their attributes.
            dimensions_to_create = [
                {"label": dim.label, "description": dim.description}
                for dim in self.default_dimensions_config
            ]
            logger.info("Using default decomposition dimensions from configuration.")

        dimension_node_ids: list[str] = []
        nodes_created_count = 0
        edges_created_count = 0

        root_node = graph.get_node(root_node_id)
        root_node_layer = (
            root_node.metadata.layer_id
            if root_node
            else self.default_params.initial_layer
        )

        for i, dim_data in enumerate(dimensions_to_create):
            dim_label = dim_data.get("label", f"Dimension {i + 1}")
            dim_description = dim_data.get("description", f"Details for {dim_label}")
            dim_id = f"dim_{root_node_id}_{i + 1}"  # Ensure unique ID related to the root            # P1.2: Initial confidence C_dim
            dim_confidence = ConfidenceVector.from_list(
                self.dimension_confidence_values
            )

            # P1.12 schema for dimension nodes
            dim_metadata = NodeMetadata(
                description=dim_description,
                source_description="Enhanced GoT Decomposition Dimensions (P1.2)",
                epistemic_status=EpistemicStatus.ASSUMPTION,  # Dimensions are initially assumptions/framings
                disciplinary_tags=default_disciplinary_tags,  # Inherit or specify
                layer_id=operational_params.get(
                    "dimension_layer", root_node_layer
                ),  # P1.12, P1.23
                impact_score=0.7,  # Dimensions are generally important for framing
            )

            dimension_node = Node(
                id=dim_id,
                label=dim_label,
                type=NodeType.DECOMPOSITION_DIMENSION,  # P1.2
                confidence=dim_confidence,
                metadata=dim_metadata,
            )
            graph.add_node(dimension_node)
            dimension_node_ids.append(dimension_node.id)
            nodes_created_count += 1

            # P1.2: Connect dimension node n_i to n_0 (root_node)
            edge_id = f"edge_{root_node_id}_{dim_id}"
            edge_metadata = EdgeMetadata(
                description=f"'{dim_label}' is a decomposition dimension of the main task."
            )

            decomposition_edge = Edge(
                id=edge_id,
                source_id=root_node_id,
                target_id=dim_id,
                type=EdgeType.DECOMPOSITION_OF,  # Custom type to signify this structural link
                confidence=0.95,  # High confidence in the structural decomposition link
                metadata=edge_metadata,
            )
            graph.add_edge(decomposition_edge)
            edges_created_count += 1
            logger.debug(
                f"Created dimension node '{dim_label}' (ID: {dim_id}) and linked to root node {root_node_id}."
            )

        # Build the summary of dimension labels for the output
        dimension_labels: list[str] = []
        for nid in dimension_node_ids:
            node = graph.get_node(nid)
            if node:
                dimension_labels.append(node.label)

        summary = f"Task decomposed into {len(dimension_node_ids)} dimensions: {', '.join(dimension_labels)}."

        metrics = {
            "dimensions_created": nodes_created_count,
            "decomposition_edges_created": edges_created_count,
            "dimension_count": len(dimension_node_ids),
        }
        context_update = {"dimension_node_ids": dimension_node_ids}

        output = StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
        self._log_end(current_session_data.session_id, output)
        return output
