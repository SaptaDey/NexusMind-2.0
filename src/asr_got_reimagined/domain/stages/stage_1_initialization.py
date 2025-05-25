from loguru import logger

from src.asr_got_reimagined.config import Settings
from src.asr_got_reimagined.domain.models.common import (
    ConfidenceVector,
    EpistemicStatus,
)
from src.asr_got_reimagined.domain.models.common_types import GoTProcessorSessionData
from src.asr_got_reimagined.domain.models.graph_elements import (
    Node,
    NodeMetadata,
    NodeType,
)
from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph

from .base_stage import BaseStage, StageOutput


class InitializationStage(BaseStage):
    stage_name: str = "InitializationStage"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        # P1.1: Graph Initialization Defaults
        self.root_node_label = "Task Understanding"  # P1.1 value
        # P1.1 value (C0 from P1.5, high initial belief)
        self.initial_confidence_values = self.default_params.initial_confidence
        # P1.12 schema is handled by NodeMetadata model
        self.initial_layer = self.default_params.initial_layer  # P1.1, from settings

    async def execute(
        self, graph: ASRGoTGraph, current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        self._log_start(current_session_data.session_id)

        initial_query = current_session_data.query
        operational_params = current_session_data.accumulated_context.get(
            "operational_params", {}
        )

        # Validate initial query
        if not initial_query or not isinstance(initial_query, str):
            error_message = "Invalid initial query. It must be a non-empty string."
            logger.error(error_message)
            return StageOutput(
                summary=error_message,
                metrics={"nodes_created": 0},
                next_stage_context_update={self.stage_name: {"error": error_message}},
            )

        # Create root node (n0) based on P1.1
        root_node_id = "n0"  # Standard ID for the root node

        # Extract initial disciplinary tags from operational parameters or query (simplified for now)
        # P1.1 refers to P1.12 schema which includes disciplinary_tags.
        # The actual extraction logic for tags can be more sophisticated.
        # For now, let's use a default or allow override from operational_params.
        default_disciplines_from_config = (
            self.settings.asr_got.default_parameters.default_disciplinary_tags
        )
        initial_disciplinary_tags = set(
            operational_params.get(
                "initial_disciplinary_tags", default_disciplines_from_config
            )
        )

        # Create NodeMetadata instance (P1.12 compliance)
        root_metadata = NodeMetadata(
            description=f"Initial understanding of the task based on the query: '{initial_query}'.",
            query_context=initial_query,  # P1.6 Verbatim query in metadata
            source_description="Core GoT Protocol Definition (P1.1), User Query",  # P1.1 source_description
            epistemic_status=EpistemicStatus.ASSUMPTION,  # Initial state is an assumption of understanding
            disciplinary_tags=initial_disciplinary_tags,
            layer_id=operational_params.get(
                "initial_layer", self.initial_layer
            ),  # P1.12, P1.23
            impact_score=0.9,  # Root node is initially considered high impact
            # Other P1.12 fields like falsification_criteria, bias_flags will be added by later stages
            # or are not applicable to the root task_understanding node itself.
        )

        root_node = Node(
            id=root_node_id,
            label=self.root_node_label,  # P1.1
            type=NodeType.ROOT,  # Or NodeType.TASK_UNDERSTANDING
            confidence=ConfidenceVector.from_list(
                self.initial_confidence_values
            ),  # P1.1, P1.5
            metadata=root_metadata,
        )

        try:
            graph.add_node(root_node)
            logger.info(
                f"Root node '{root_node.label}' (ID: {root_node.id}) created and added to graph."
            )
        except Exception as e:
            error_message = f"Failed to add root node to graph: {e}"
            logger.error(error_message)
            return StageOutput(
                summary=error_message,
                metrics={"nodes_created": 0},
                next_stage_context_update={self.stage_name: {"error": error_message}},
            )

        # Setup multi-layer structure if defined globally in settings (P1.23)
        # The ASRGoTGraph model's assign_node_to_layer handles adding the node to a layer set.
        # Global layer definitions might be in settings.asr_got.layers
        for layer_id, _ in self.settings.asr_got.layers.items():
            if (
                layer_id not in graph.layers
            ):  # Initialize layer sets in the graph if not present
                graph.layers[layer_id] = set()
                logger.debug(
                    f"Ensured layer '{layer_id}' exists in graph from global definitions."
                )

        # Update session data with the root node ID and other relevant info from this stage
        context_update = {
            "root_node_id": root_node.id,
            "initial_disciplinary_tags": list(
                initial_disciplinary_tags
            ),  # Pass as list for JSON compatibility
        }

        summary = f"Graph initialized with root node '{root_node.label}' (ID: {root_node.id}) based on the query. Initial confidence set."
        metrics = {
            "nodes_created": 1,
            "initial_confidence_avg": root_node.confidence.average_confidence,
            "layer_count_initialized": len(graph.layers),
        }

        output = StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
        self._log_end(current_session_data.session_id, output)
        return output
