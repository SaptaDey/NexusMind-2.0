import random
from typing import Any

from loguru import logger

from src.asr_got_reimagined.config import Settings
from src.asr_got_reimagined.domain.models.common import (
    ConfidenceVector,
    EpistemicStatus,
)
from src.asr_got_reimagined.domain.models.common_types import GoTProcessorSessionData
from src.asr_got_reimagined.domain.models.graph_elements import (
    BiasFlag,
    Edge,
    EdgeMetadata,
    EdgeType,
    FalsificationCriteria,
    Node,
    NodeMetadata,
    NodeType,
    Plan,
)
from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph

from .base_stage import BaseStage, StageOutput

# Import names of previous stages to access their output keys in accumulated_context
from .stage_2_decomposition import DecompositionStage


class HypothesisStage(BaseStage):
    stage_name: str = "HypothesisStage"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        # P1.3: Hypothesis Generation Parameters
        self.k_min_hypotheses = (
            self.default_params.hypotheses_per_dimension.min_hypotheses
        )
        self.k_max_hypotheses = (
            self.default_params.hypotheses_per_dimension.max_hypotheses
        )
        self.hypothesis_confidence_values = (
            self.default_params.hypothesis_confidence
        )  # C_hypo
        self.default_disciplinary_tags_config = (
            self.default_params.default_disciplinary_tags
        )
        self.default_plan_types_config = self.default_params.default_plan_types

    async def _generate_hypothesis_content(
        self, dimension_node: Node, hypo_index: int, initial_query: str
    ) -> dict[str, Any]:
        """
        Generates a dictionary containing the content for a single hypothesis based on a dimension node and an initial query.
        
        The generated content includes a hypothesis label, an evaluation plan, falsification criteria, optional bias flags, an estimated impact score, and a set of disciplinary tags. The values are randomly selected or constructed to simulate hypothesis generation for testing or prototyping purposes.
        
        Args:
            dimension_node: The node representing the dimension for which the hypothesis is generated.
            hypo_index: The index of the hypothesis among those generated for this dimension.
            initial_query: The original query string that prompted hypothesis generation.
        
        Returns:
            A dictionary with keys: 'label', 'plan', 'falsification_criteria', 'bias_flags', 'impact_score', and 'disciplinary_tags', representing the generated hypothesis content.
        """
        # Placeholder content generation
        dim_label = dimension_node.label
        base_hypothesis_text = f"Hypothesis {hypo_index + 1} regarding '{dim_label}' for query '{initial_query[:30]}...'"

        # P1.3: Require explicit plan
        plan_type = random.choice(self.default_plan_types_config)
        plan = Plan(
            type=plan_type,
            description=f"Plan to evaluate '{base_hypothesis_text}' via {plan_type}.",
            estimated_cost=random.uniform(0.2, 0.8),
            estimated_duration=random.uniform(
                1.0, 5.0
            ),  # e.g., in abstract time units or days
            required_resources=[
                random.choice(["dataset_X", "computational_cluster", "expert_A"])
            ],
        )

        # P1.16: Falsifiability criteria
        fals_conditions = [
            f"Observe contradictory evidence from {plan_type}",
            f"Find statistical insignificance in {random.choice(['key_metric_A', 'key_metric_B'])}",
        ]
        falsifiability = FalsificationCriteria(
            description=f"This hypothesis could be falsified if {fals_conditions[0].lower()} or if {fals_conditions[1].lower()}.",
            testable_conditions=fals_conditions,
        )

        # P1.17: Initial bias risk assessment (simplified)
        bias_flags = []
        if random.random() < 0.15:  # 15% chance of an initial bias flag
            bias_type = random.choice(
                ["Confirmation Bias", "Availability Heuristic", "Anchoring Bias"]
            )
            bias_flags.append(
                BiasFlag(
                    bias_type=bias_type,
                    description=f"Potential {bias_type} in formulating or prioritizing this hypothesis.",
                    assessment_stage_id=self.stage_name,
                    severity=random.choice(["low", "medium"]),
                )
            )

        # P1.28: Potential impact estimate
        impact_score = random.uniform(
            0.2, 0.9
        )  # Use the raw float value for ImpactScore type

        # P1.8: Tag with disciplinary provenance (simplified selection)
        num_tags = random.randint(1, min(2, len(self.default_disciplinary_tags_config)))
        disciplinary_tags = set(
            random.sample(self.default_disciplinary_tags_config, num_tags)
        )
        # Add dimension's tags if any, to ensure relevance
        disciplinary_tags.update(dimension_node.metadata.disciplinary_tags)

        return {
            "label": base_hypothesis_text,
            "plan": plan,
            "falsification_criteria": falsifiability,
            "bias_flags": bias_flags,
            "impact_score": impact_score,
            "disciplinary_tags": disciplinary_tags,
        }

    async def execute(
        self, graph: ASRGoTGraph, current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        """
        Asynchronously generates hypothesis nodes for each dimension node in the graph and links them.
        
        For each dimension node identified from the previous decomposition stage, this method creates a configurable number of hypothesis nodes with associated metadata, including plans, falsification criteria, bias flags, impact scores, and disciplinary tags. Each hypothesis node is added to the graph and connected to its parent dimension node with an edge. The method returns a StageOutput summarizing the number of hypotheses generated, metrics, and context updates for downstream processing.
        
        Returns:
            StageOutput: Contains a summary, metrics, and context update with generated hypothesis node IDs.
        """
        self._log_start(current_session_data.session_id)

        # GoTProcessor now stores the dictionary from next_stage_context_update directly.
        decomposition_data_from_context = current_session_data.accumulated_context.get(
            DecompositionStage.stage_name, {}
        )
        dimension_node_ids: list[str] = decomposition_data_from_context.get(
            "dimension_node_ids", []
        )
        initial_query = current_session_data.query
        operational_params = current_session_data.accumulated_context.get(
            "operational_params", {}
        )

        if not dimension_node_ids:
            logger.warning(
                "No dimension node IDs found from DecompositionStage. Cannot generate hypotheses."
            )
            return StageOutput(
                summary="Hypothesis generation skipped: No dimensions available.",
                metrics={"hypotheses_generated_total": 0},
                next_stage_context_update={
                    self.stage_name: {
                        "error": "No dimensions found",
                        "hypothesis_node_ids": [],
                    }
                },
            )

        all_hypothesis_node_ids: list[str] = []
        nodes_created_count = 0
        edges_created_count = 0

        # P1.3: Generate k hypotheses per dimension node (k is configurable)
        # Allow override from operational_params, else use config range
        k_min = operational_params.get(
            "hypotheses_per_dimension_min", self.k_min_hypotheses
        )
        k_max = operational_params.get(
            "hypotheses_per_dimension_max", self.k_max_hypotheses
        )
        k_hypotheses_to_generate = random.randint(k_min, k_max)

        for dim_id in dimension_node_ids:
            dimension_node = graph.get_node(dim_id)
            if not dimension_node:
                logger.warning(
                    f"Dimension node with ID {dim_id} not found in graph. Skipping hypothesis generation for it."
                )
                continue

            logger.debug(
                f"Generating {k_hypotheses_to_generate} hypotheses for dimension: '{dimension_node.label}' (ID: {dim_id})"
            )

            hypotheses_for_dim_count = 0
            for i in range(k_hypotheses_to_generate):
                hypo_content = await self._generate_hypothesis_content(
                    dimension_node, i, initial_query
                )
                hypo_id = f"hypo_{dim_id}_{i + 1}"

                # P1.3: Initial confidence C_hypo
                hypo_confidence = ConfidenceVector.from_list(
                    self.hypothesis_confidence_values
                )

                # P1.12 schema for hypothesis nodes
                hypo_metadata = NodeMetadata(
                    description=f"A potential hypothesis related to the dimension: '{dimension_node.label}'.",
                    source_description="Enhanced GoT Hypothesis Generation Rules (P1.3)",
                    epistemic_status=EpistemicStatus.HYPOTHESIS,
                    # P1.8: disciplinary_tags from hypo_content
                    disciplinary_tags=hypo_content["disciplinary_tags"],
                    # P1.16: falsification_criteria from hypo_content
                    falsification_criteria=hypo_content["falsification_criteria"],
                    # P1.17: bias_flags from hypo_content
                    bias_flags=hypo_content["bias_flags"],
                    # P1.28: impact_score from hypo_content
                    impact_score=hypo_content["impact_score"],
                    # P1.3: plan from hypo_content
                    plan=hypo_content["plan"],
                    layer_id=operational_params.get(
                        "hypothesis_layer", dimension_node.metadata.layer_id
                    ),  # Inherit or specify
                )

                hypothesis_node = Node(
                    id=hypo_id,
                    label=hypo_content["label"],  # P1.3 (generated content)
                    type=NodeType.HYPOTHESIS,  # P1.3
                    confidence=hypo_confidence,
                    metadata=hypo_metadata,
                )
                graph.add_node(hypothesis_node)
                all_hypothesis_node_ids.append(hypothesis_node.id)
                nodes_created_count += 1
                hypotheses_for_dim_count += 1

                # Connect hypothesis node to its parent dimension node
                edge_id = f"{dim_id}_to_{hypo_id}"
                hypothesis_edge = Edge(
                    id=edge_id,
                    source_id=dim_id,
                    target_id=hypo_id,
                    type=EdgeType.GENERATES_HYPOTHESIS,  # Custom type
                    confidence=0.9,  # Confidence in the link, not the hypothesis itself
                    metadata=EdgeMetadata(
                        description=f"Hypothesis '{hypothesis_node.label}' generated for dimension '{dimension_node.label}'."
                    ),
                )
                graph.add_edge(hypothesis_edge)
                edges_created_count += 1
            logger.debug(
                f"Generated {hypotheses_for_dim_count} hypotheses for dimension '{dimension_node.label}'."
            )

        summary = f"Generated a total of {nodes_created_count} hypotheses across {len(dimension_node_ids)} dimensions."
        metrics = {
            "hypotheses_generated_total": nodes_created_count,
            "hypothesis_edges_created": edges_created_count,
            "avg_hypotheses_per_dimension": nodes_created_count
            / len(dimension_node_ids)
            if dimension_node_ids
            else 0,
        }
        context_update = {"hypothesis_node_ids": all_hypothesis_node_ids}

        output = StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
        self._log_end(current_session_data.session_id, output)
        return output
