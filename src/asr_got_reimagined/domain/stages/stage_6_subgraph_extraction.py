from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field  # For defining subgraph criteria structure

from src.asr_got_reimagined.config import Settings
from src.asr_got_reimagined.domain.models.common_types import GoTProcessorSessionData
from src.asr_got_reimagined.domain.models.graph_elements import Node, NodeType
from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph

from .base_stage import BaseStage, StageOutput


# Pydantic model for defining a single subgraph extraction strategy
class SubgraphCriterion(BaseModel):
    name: str  # e.g., "high_confidence_hypotheses", "main_causal_chain"
    description: str
    # Filters - all conditions must be met for a node to be included initially
    min_avg_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)  # P1.5
    min_impact_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)  # P1.28
    node_types: Optional[list[NodeType]] = None  # P1.6
    include_disciplinary_tags: Optional[list[str]] = None  # P1.8 (any of these)
    exclude_disciplinary_tags: Optional[list[str]] = None
    layer_ids: Optional[list[str]] = None  # P1.23 (any of these layers)
    is_knowledge_gap: Optional[bool] = None  # P1.15
    # temporal_recency_days: Optional[int] = None # P1.18 (e.g., created in last X days) - complex to implement here fully
    # edge_pattern_to_match: Optional[Dict[str, Any]] = None # P1.10, P1.24, P1.25 - very complex

    # Post-selection expansion
    include_neighbors_depth: int = Field(
        default=0, ge=0
    )  # How many levels of neighbors to include


class ExtractedSubgraph(BaseModel):
    name: str
    description: str
    node_ids: list[str]
    # We might store the actual NetworkX subgraph later, or just node IDs for composition
    # For now, just node_ids to keep it simple for context passing.
    # subgraph_nx: Optional[Any] = None # Could hold nx.Graph
    metrics: dict[str, Any] = Field(default_factory=dict)


class SubgraphExtractionStage(BaseStage):
    stage_name: str = "SubgraphExtractionStage"

    def __init__(self, settings: Settings):
        """
        Initializes the subgraph extraction stage with default extraction criteria.
        
        Defines a set of default subgraph extraction strategies, each specifying filters such as minimum confidence, impact score, node types, and neighbor inclusion depth. These defaults guide how subgraphs are identified and extracted from the input graph.
        """
        super().__init__(settings)
        # P1.6: Subgraph extraction criteria can be complex and data-driven.
        # For now, define some default strategies. These could also come from config or operational_params.
        self.default_extraction_criteria: list[SubgraphCriterion] = [
            SubgraphCriterion(
                name="high_confidence_core",
                description="Nodes with high average confidence and impact, focusing on hypotheses and evidence.",
                min_avg_confidence=self.default_params.subgraph_min_confidence_threshold,  # from settings.yaml
                min_impact_score=self.default_params.subgraph_min_impact_threshold,  # from settings.yaml
                node_types=[
                    NodeType.HYPOTHESIS,
                    NodeType.EVIDENCE,
                    NodeType.INTERDISCIPLINARY_BRIDGE,
                ],
                include_neighbors_depth=1,  # Include immediate neighbors
            ),
            SubgraphCriterion(
                name="key_hypotheses_and_support",
                description="Key hypotheses and their direct supporting/contradicting evidence.",
                node_types=[NodeType.HYPOTHESIS],
                min_avg_confidence=0.5,  # Moderately confident hypotheses
                min_impact_score=0.5,
                include_neighbors_depth=1,  # Get evidence linked to these hypotheses
            ),
            SubgraphCriterion(
                name="knowledge_gaps_focus",  # P1.15
                description="Subgraph highlighting identified knowledge gaps and related questions.",
                is_knowledge_gap=True,
                node_types=[NodeType.PLACEHOLDER_GAP, NodeType.RESEARCH_QUESTION],
                include_neighbors_depth=1,
            ),
            # Add more criteria: e.g., discipline-specific, layer-specific, causal chains
        ]

    def _node_matches_criteria(self, node: Node, criterion: SubgraphCriterion) -> bool:
        """
        Determines whether a node satisfies all conditions specified in a subgraph extraction criterion.
        
        Returns:
            True if the node meets every filter in the criterion; otherwise, False.
        """
        if (
            criterion.min_avg_confidence is not None
            and node.confidence.average_confidence < criterion.min_avg_confidence
        ):
            return False
        if (
            criterion.min_impact_score is not None
            and (node.metadata.impact_score or 0.0) < criterion.min_impact_score
        ):
            return False
        if criterion.node_types and node.type not in criterion.node_types:
            return False
        if criterion.layer_ids and (
            node.metadata.layer_id is None
            or node.metadata.layer_id not in criterion.layer_ids
        ):
            return False
        if (
            criterion.is_knowledge_gap is not None
            and node.metadata.is_knowledge_gap != criterion.is_knowledge_gap
        ):
            return False

        if (
            criterion.include_disciplinary_tags
            and not node.metadata.disciplinary_tags.intersection(
                set(criterion.include_disciplinary_tags)
            )
        ):
            return False
        if (
            criterion.exclude_disciplinary_tags
            and node.metadata.disciplinary_tags.intersection(
                set(criterion.exclude_disciplinary_tags)
            )
        ):
            return False

        # Placeholder for temporal_recency_days (P1.18)
        # if criterion.temporal_recency_days is not None:
        #     age_days = (datetime.datetime.now(datetime.timezone.utc) - node.created_at.replace(tzinfo=datetime.timezone.utc)).days
        #     if age_days > criterion.temporal_recency_days:
        #         return False
        return True

    async def _extract_single_subgraph(
        self, graph: ASRGoTGraph, criterion: SubgraphCriterion
    ) -> ExtractedSubgraph:
        """
        Extracts a subgraph from the graph based on a single extraction criterion.
        
        The method identifies seed nodes matching the provided criterion, then expands the subgraph by including neighbors up to the specified depth. Both outgoing and incoming neighbors are considered during expansion. Returns an `ExtractedSubgraph` containing the selected node IDs and summary metrics.
        """
        seed_node_ids: set[str] = set()
        for node_id, node_obj in graph.nodes.items():
            if self._node_matches_criteria(node_obj, criterion):
                seed_node_ids.add(node_id)

        final_subgraph_node_ids: set[str] = set(seed_node_ids)

        # Expand to include neighbors if depth > 0
        current_frontier = set(seed_node_ids)
        for _ in range(criterion.include_neighbors_depth):
            next_frontier: set[str] = set()
            if not current_frontier:
                break
            for node_id in current_frontier:  # Use graph.nx_graph for neighbor finding
                if graph.nx_graph.has_node(node_id):
                    for neighbor_id in graph.nx_graph.neighbors(node_id):  # Outgoing
                        if neighbor_id not in final_subgraph_node_ids:
                            next_frontier.add(neighbor_id)
                            final_subgraph_node_ids.add(neighbor_id)
                    for predecessor_id in graph.nx_graph.predecessors(
                        node_id
                    ):  # Incoming
                        if predecessor_id not in final_subgraph_node_ids:
                            next_frontier.add(predecessor_id)
                            final_subgraph_node_ids.add(predecessor_id)
            current_frontier = next_frontier

        # Induce subgraph in NetworkX to get edges, or manually collect edges
        # For now, we just return node IDs. The Composition stage can use these.
        num_nodes = len(
            final_subgraph_node_ids
        )  # Could calculate num_edges if we induce the subgraph here
        # induced_nx_subgraph = graph.nx_graph.subgraph(final_subgraph_node_ids)
        # num_edges = induced_nx_subgraph.number_of_edges()

        logger.info(f"Extracted subgraph '{criterion.name}' with {num_nodes} nodes.")
        return ExtractedSubgraph(
            name=criterion.name,
            description=criterion.description,
            node_ids=list(final_subgraph_node_ids),
            metrics={"node_count": num_nodes, "seed_node_count": len(seed_node_ids)},
        )

    async def execute(
        self, graph: ASRGoTGraph, current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        """
        Executes the subgraph extraction stage, generating subgraphs based on defined or custom criteria.
        
        This method processes the input graph using either default or custom extraction criteria, extracting subgraphs that match each criterion. It aggregates extraction results, computes summary metrics, and prepares context updates for downstream pipeline stages.
        
        Args:
            graph: The input graph from which subgraphs are to be extracted.
            current_session_data: Session data containing context and operational parameters.
        
        Returns:
            A StageOutput containing a summary, extraction metrics, and context updates with serialized subgraph definitions.
        """
        self._log_start(current_session_data.session_id)

        # Allow operational parameters to override or add to default criteria
        operational_params = current_session_data.accumulated_context.get(
            "operational_params", {}
        )
        custom_criteria_input = operational_params.get("subgraph_extraction_criteria")

        criteria_to_use: list[SubgraphCriterion] = []
        if isinstance(custom_criteria_input, list):
            try:
                criteria_to_use = [
                    SubgraphCriterion(**c) for c in custom_criteria_input
                ]
                logger.info(
                    f"Using {len(criteria_to_use)} custom subgraph extraction criteria from operational parameters."
                )
            except Exception as e:
                logger.warning(
                    f"Failed to parse custom subgraph criteria: {e}. Using default criteria."
                )
                criteria_to_use = self.default_extraction_criteria
        else:
            criteria_to_use = self.default_extraction_criteria
            logger.info(
                f"Using {len(criteria_to_use)} default subgraph extraction criteria."
            )

        extracted_subgraphs_results: list[ExtractedSubgraph] = []
        for criterion in criteria_to_use:
            if graph.get_statistics().node_count == 0:  # No nodes to process
                logger.warning(
                    f"Skipping subgraph extraction criterion '{criterion.name}' as graph is empty."
                )
                continue
            try:
                subgraph_result = await self._extract_single_subgraph(graph, criterion)
                if subgraph_result.node_ids:  # Only add if non-empty
                    extracted_subgraphs_results.append(subgraph_result)
            except Exception as e:
                logger.error(
                    f"Error extracting subgraph for criterion '{criterion.name}': {e}"
                )
                continue

        summary = f"Subgraph extraction complete. Extracted {len(extracted_subgraphs_results)} subgraphs based on defined criteria."
        metrics = {
            "subgraphs_extracted_count": len(extracted_subgraphs_results),
            "total_criteria_evaluated": len(criteria_to_use),
        }
        for sg_res in extracted_subgraphs_results:
            metrics[f"subgraph_{sg_res.name}_node_count"] = sg_res.metrics.get(
                "node_count", 0
            )

        # The output for the next stage (Composition) will be the list of these extracted subgraphs (definitions/node lists)
        context_update = {
            "extracted_subgraphs_definitions": [
                sg.model_dump() for sg in extracted_subgraphs_results
            ]
        }

        output = StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
        self._log_end(current_session_data.session_id, output)
        return output
