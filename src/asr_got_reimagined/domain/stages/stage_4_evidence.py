import datetime
import random
from typing import Any, Optional

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
    Hyperedge,
    HyperedgeMetadata,
    InformationTheoreticMetrics,
    InterdisciplinaryInfo,
    Node,
    NodeMetadata,
    NodeType,
    StatisticalPower,
)
from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph
from src.asr_got_reimagined.domain.utils.math_helpers import (
    bayesian_update_confidence,
    calculate_information_gain,
)
from src.asr_got_reimagined.domain.utils.metadata_helpers import (
    calculate_semantic_similarity,
)

from .base_stage import BaseStage, StageOutput
from .stage_3_hypothesis import HypothesisStage  # To access hypothesis_node_ids


class EvidenceStage(BaseStage):
    stage_name: str = "EvidenceStage"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        # P1.4: Adaptive Evidence Integration Loop
        self.max_iterations = self.default_params.evidence_max_iterations
        # P1.8: IBN semantic similarity threshold
        self.ibn_similarity_threshold = (
            0.5  # Example, make configurable in settings.yaml
        )
        # P1.9: Hyperedge creation conditions (simplified)
        self.min_nodes_for_hyperedge_consideration = (
            2  # Min evidence nodes supporting one hypo
        )

    async def _select_hypothesis_to_evaluate(
        self, graph: ASRGoTGraph, hypothesis_node_ids: list[str]
    ) -> Optional[Node]:
        """
        Selects the next hypothesis for evidence gathering.
        P1.4: based on multi-dimensional confidence-to-cost ratio (P1.5) & potential impact (P1.28).
        Simplified: selects a hypothesis, perhaps one with high uncertainty or impact.
        """
        eligible_hypotheses: list[Node] = []
        for hypo_id in hypothesis_node_ids:
            hypo_node = graph.get_node(hypo_id)
            if hypo_node and hypo_node.type == NodeType.HYPOTHESIS:
                # TODO: Check if hypothesis already has "enough" evidence or is "resolved"
                eligible_hypotheses.append(hypo_node)

        if not eligible_hypotheses:
            return None

        # Simplified selection: prioritize by impact, then by uncertainty (e.g., variance in confidence vector)
        # A more complex scoring function would use confidence components, plan cost, etc.
        def score_hypothesis(h_node: Node):
            impact = h_node.metadata.impact_score or 0.1
            conf_variance = (
                sum([(c - 0.5) ** 2 for c in h_node.confidence.to_list()]) / 4.0
            )  # Measures deviation from neutral 0.5
            # Higher score for higher impact and higher variance (more uncertainty to resolve)
            return impact + conf_variance

        eligible_hypotheses.sort(key=score_hypothesis, reverse=True)
        selected_hypothesis = eligible_hypotheses[0]
        logger.debug(
            f"Selected hypothesis '{selected_hypothesis.label}' for evidence integration."
        )
        return selected_hypothesis

    async def _execute_hypothesis_plan(
        self,
        hypothesis_node: Node,
        # graph: ASRGoTGraph, # Marked as unused by Ruff
        # session_data: GoTProcessorSessionData, # Marked as unused by Ruff
    ) -> list[dict[str, Any]]:
        """
        Simulates executing the plan associated with a hypothesis to find/generate evidence.
        P1.4: executing plans...
        In a real system, this would involve calling external tools, databases, LLMs, or running simulations.
        """
        plan = hypothesis_node.metadata.plan
        logger.info(
            f"Executing plan type '{plan.type if plan else 'N/A'}' for hypothesis '{hypothesis_node.label}'."
        )

        # Placeholder: Generate 1-2 pieces of mock evidence
        num_evidence_pieces = random.randint(1, 2)
        generated_evidence_data: list[dict[str, Any]] = []

        for i in range(num_evidence_pieces):  # Simulate evidence properties
            supports_hypothesis = (
                random.random() > 0.25
            )  # 75% chance of supportive evidence
            evidence_strength = random.uniform(
                0.4, 0.9
            )  # CertaintyScore is Annotated[float]
            stat_power_val = random.uniform(0.5, 0.95)
            stat_power = StatisticalPower(
                value=stat_power_val, method_description="Simulated statistical power."
            )

            # P1.8: Disciplinary tags for evidence - can be same as hypo or different
            evidence_tags = set(
                random.sample(
                    self.default_params.default_disciplinary_tags,
                    random.randint(
                        1, len(self.default_params.default_disciplinary_tags)
                    ),
                )
            )
            if random.random() < 0.3:  # Chance to add a new, different tag
                evidence_tags.add(f"special_evidence_domain_{random.randint(1, 3)}")

            evidence_content = (
                f"Evidence piece {i + 1} {'supporting' if supports_hypothesis else 'contradicting'} "
                f"hypothesis '{hypothesis_node.label[:30]}...' (Strength: {evidence_strength:.2f})"
            )

            generated_evidence_data.append(
                {
                    "content": evidence_content,
                    "source_description": f"Simulated {plan.type if plan else 'unknown_plan_type'} execution",
                    "supports_hypothesis": supports_hypothesis,
                    "strength": evidence_strength,
                    "statistical_power": stat_power,  # P1.26
                    "disciplinary_tags": list(evidence_tags),  # P1.8
                    "temporal_data": {
                        "timestamp": datetime.datetime.now()
                    },  # P1.18, P1.25
                }
            )
        logger.debug(
            f"Generated {len(generated_evidence_data)} pieces of mock evidence for hypothesis '{hypothesis_node.label}'."
        )
        return generated_evidence_data

    async def _create_evidence_node_and_link(
        self,
        graph: ASRGoTGraph,
        hypothesis_node: Node,
        evidence_data: dict[str, Any],
        iteration: int,
        evidence_index: int,
    ) -> Optional[Node]:
        """Creates an evidence node and links it to the hypothesis."""
        evidence_id = f"ev_{hypothesis_node.id}_{iteration}_{evidence_index}"
        # P1.10, P1.24, P1.25: Determine edge type (simplified)
        edge_type = (
            EdgeType.SUPPORTIVE
            if evidence_data["supports_hypothesis"]
            else EdgeType.CONTRADICTORY
        )
        # More sophisticated edge typing would analyze content and context.

        # P1.12 for evidence nodes
        evidence_metadata = NodeMetadata(
            description=evidence_data["content"],
            source_description=evidence_data["source_description"],
            epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED
            if evidence_data["supports_hypothesis"]
            else EpistemicStatus.EVIDENCE_CONTRADICTED,
            disciplinary_tags=set(evidence_data["disciplinary_tags"]),
            statistical_power=evidence_data["statistical_power"],  # P1.26
            impact_score=evidence_data["strength"]
            * (
                evidence_data["statistical_power"].value
                if evidence_data["statistical_power"]
                else 0.5
            ),  # Simplified impact
            layer_id=hypothesis_node.metadata.layer_id,  # Default to hypo layer
        )
        # Evidence confidence usually reflects its reliability/strength
        # For simplicity, let's use strength for the empirical component
        evidence_confidence_vec = ConfidenceVector(
            empirical_support=evidence_data["strength"],  # Primary aspect
            methodological_rigor=evidence_data.get(
                "methodological_rigor", evidence_data["strength"] * 0.8
            ),  # Assume some rigor
            theoretical_basis=0.5,  # Evidence itself doesn't have theoretical basis, but its interpretation might
            consensus_alignment=0.5,  # Evidence itself doesn't have consensus, its interpretation might
        )

        evidence_node = Node(
            id=evidence_id,
            label=f"Evidence {evidence_index + 1} for H: {hypothesis_node.label[:20]}...",
            type=NodeType.EVIDENCE,
            confidence=evidence_confidence_vec,
            metadata=evidence_metadata,
        )
        graph.add_node(evidence_node)

        # P1.10: Link evidence E_r to hypothesis h*
        edge_to_hypo_id = f"edge_ev_{evidence_node.id}_{hypothesis_node.id}"
        edge_metadata = EdgeMetadata(
            description=f"Evidence '{evidence_node.label[:20]}...' {'supports' if evidence_data['supports_hypothesis'] else 'contradicts'} hypothesis."
        )

        edge_to_hypo = Edge(
            id=edge_to_hypo_id,
            source_id=evidence_node.id,
            target_id=hypothesis_node.id,
            type=edge_type,
            confidence=evidence_data[
                "strength"
            ],  # Edge confidence reflects evidence strength
            metadata=edge_metadata,
        )
        graph.add_edge(edge_to_hypo)
        logger.debug(
            f"Created evidence node {evidence_node.id} and linked to hypothesis {hypothesis_node.id} with type {edge_type.value}."
        )
        return evidence_node

    async def _try_create_interdisciplinary_bridge_node(
        self, graph: ASRGoTGraph, evidence_node: Node, hypothesis_node: Node
    ) -> Optional[str]:
        """P1.8: Create Interdisciplinary Bridge Node (IBN)"""
        hypo_tags = hypothesis_node.metadata.disciplinary_tags
        ev_tags = evidence_node.metadata.disciplinary_tags

        if not hypo_tags or not ev_tags:
            return None  # Need tags on both
        if hypo_tags.intersection(ev_tags):
            return None  # Disciplines overlap, no bridge needed by this rule

        # Check semantic similarity (P1.8) - simplified
        # In a real system, use NLP models on node labels/descriptions.
        similarity = calculate_semantic_similarity(
            hypothesis_node.label, evidence_node.label
        )
        if similarity < self.ibn_similarity_threshold:
            logger.debug(
                f"IBN not created between {evidence_node.id} and {hypothesis_node.id}: similarity {similarity:.2f} < {self.ibn_similarity_threshold}"
            )
            return None

        ibn_id = f"ibn_{evidence_node.id}_{hypothesis_node.id}"
        ibn_label = (
            f"IBN: {evidence_node.label[:20]}... <=> {hypothesis_node.label[:20]}..."
        )
        combined_tags = hypo_tags.union(ev_tags)

        ibn_metadata = NodeMetadata(
            description=f"Interdisciplinary bridge connecting concepts from domains {hypo_tags} and {ev_tags}.",
            source_description="Methodology for IBNs (P1.8)",
            epistemic_status=EpistemicStatus.INFERRED,
            disciplinary_tags=combined_tags,
            interdisciplinary_info=InterdisciplinaryInfo(
                source_disciplines=hypo_tags,
                target_disciplines=ev_tags,
                bridging_concept=f"Connection between '{evidence_node.label[:20]}...' and '{hypothesis_node.label[:20]}...'",
            ),
            impact_score=0.6,  # IBNs are often moderately impactful
            layer_id=evidence_node.metadata.layer_id,  # Or a dedicated "integration" layer
        )
        ibn_confidence = ConfidenceVector(  # Initial confidence for IBN
            empirical_support=similarity,  # Based on semantic similarity for now
            theoretical_basis=0.4,
            methodological_rigor=0.5,
            consensus_alignment=0.3,
        )

        ibn_node = Node(
            id=ibn_id,
            label=ibn_label,
            type=NodeType.INTERDISCIPLINARY_BRIDGE,
            confidence=ibn_confidence,
            metadata=ibn_metadata,
        )
        graph.add_node(ibn_node)

        # Link IBN to both evidence and hypothesis
        graph.add_edge(
            Edge(
                source_id=evidence_node.id,
                target_id=ibn_id,
                type=EdgeType.IBN_SOURCE_LINK,
                confidence=0.8,
            )
        )
        graph.add_edge(
            Edge(
                source_id=ibn_node.id,
                target_id=hypothesis_node.id,
                type=EdgeType.IBN_TARGET_LINK,
                confidence=0.8,
            )
        )
        logger.info(
            f"Created Interdisciplinary Bridge Node {ibn_id} between {evidence_node.id} and {hypothesis_node.id}."
        )
        return ibn_id

    async def _try_create_hyperedges(
        self,
        graph: ASRGoTGraph,
        hypothesis_node: Node,
        related_evidence_nodes: list[Node],
    ) -> list[str]:
        """P1.9: Create Hyperedges"""
        created_hyperedge_ids: list[str] = []
        # Simplified: If multiple pieces of evidence (e.g., >=2) jointly support/contradict a hypothesis non-additively.
        # True non-additivity is hard to detect without deeper semantic understanding.
        # Placeholder: if >= N evidences support a hypothesis, consider a hyperedge.
        if len(related_evidence_nodes) >= self.min_nodes_for_hyperedge_consideration:
            # Check if they point "in the same direction" for this simple version
            support_count = sum(
                1
                for en in related_evidence_nodes
                if graph.edges.get(f"edge_ev_{en.id}_{hypothesis_node.id}")
                and graph.edges[f"edge_ev_{en.id}_{hypothesis_node.id}"].type
                == EdgeType.SUPPORTIVE
            )

            if support_count == len(related_evidence_nodes) or (
                len(related_evidence_nodes) - support_count
            ) == len(related_evidence_nodes):
                # All supportive or all contradictory (simplified joint effect)
                hyperedge_node_ids = {hypothesis_node.id} | {
                    en.id for en in related_evidence_nodes
                }
                hyperedge_id = (
                    f"hyper_{hypothesis_node.id}_{random.randint(1000, 9999)}"
                )

                # P1.9: Assign confidence vector C and relationship descriptor to E_h
                # Confidence could be an aggregation or a new assessment.
                # For simplicity, average the hypothesis and evidence confidences' empirical parts.
                avg_emp_support = (
                    hypothesis_node.confidence.empirical_support
                    + sum(
                        en.confidence.empirical_support for en in related_evidence_nodes
                    )
                ) / (1 + len(related_evidence_nodes))
                hyper_confidence = ConfidenceVector(
                    empirical_support=avg_emp_support,
                    theoretical_basis=0.4,
                    methodological_rigor=0.5,
                    consensus_alignment=0.4,
                )

                hyperedge_metadata = HyperedgeMetadata(
                    description=f"Joint influence of multiple evidence on hypothesis '{hypothesis_node.label[:20]}...'",
                    relationship_descriptor="Joint Support/Contradiction (Simulated)",
                    layer_id=hypothesis_node.metadata.layer_id,
                )
                hyperedge = Hyperedge(
                    id=hyperedge_id,
                    node_ids=hyperedge_node_ids,
                    confidence_vector=hyper_confidence,
                    metadata=hyperedge_metadata,
                )
                graph.add_hyperedge(hyperedge)
                created_hyperedge_ids.append(hyperedge_id)
                logger.info(
                    f"Created Hyperedge {hyperedge_id} for hypothesis {hypothesis_node.id} and {len(related_evidence_nodes)} evidence nodes."
                )
        return created_hyperedge_ids

    async def _apply_temporal_decay_and_patterns(
        self,
    ):  # graph: ASRGoTGraph removed (unused)
        """P1.18: Apply temporal decay. P1.25: Detect temporal patterns."""
        # Placeholder for temporal decay logic
        # Iterate through evidence nodes, check timestamps, potentially reduce impact/confidence of older evidence.
        # Placeholder for temporal pattern detection
        # Analyze sequences of evidence, timestamps on edges, etc.
        logger.debug(
            "Temporal decay and pattern detection (P1.18, P1.25) - placeholder, no action taken."
        )
        pass

    async def _adapt_graph_topology(self):  # graph: ASRGoTGraph removed (unused)
        """P1.22: Dynamically adapt graph topology."""
        # Placeholder for more complex topology adaptations like community detection,
        # creating summary nodes for dense clusters, etc.
        logger.debug(
            "Dynamic graph topology adaptation (P1.22) - placeholder, no action taken."
        )
        pass

    async def execute(
        self, graph: ASRGoTGraph, current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        self._log_start(current_session_data.session_id)
        # GoTProcessor now stores the dictionary from next_stage_context_update directly.
        hypothesis_data_from_context = current_session_data.accumulated_context.get(
            HypothesisStage.stage_name, {}
        )
        hypothesis_node_ids: list[str] = hypothesis_data_from_context.get(
            "hypothesis_node_ids", []
        )

        if not hypothesis_node_ids:
            logger.warning(
                "No hypothesis node IDs found from HypothesisStage. Cannot integrate evidence."
            )
            return StageOutput(
                summary="Evidence integration skipped: No hypotheses available.",
                metrics={"evidence_nodes_created": 0, "hypotheses_updated": 0},
                next_stage_context_update={
                    self.stage_name: {"error": "No hypotheses found"}
                },
            )

        evidence_nodes_created_total = 0
        hypotheses_confidence_updated_total = 0
        ibns_created_total = 0
        hyperedges_created_total = 0
        iteration = -1  # Default value in case no iterations are run

        processed_hypotheses_this_stage: set[str] = (
            set()
        )  # Track to avoid re-processing in one stage run

        # P1.4: Iterative loop
        for iteration in range(self.max_iterations):
            logger.info(
                f"Evidence integration iteration {iteration + 1}/{self.max_iterations}"
            )

            # P1.4: Select hypothesis h* (simplified selection)
            hypothesis_to_evaluate = await self._select_hypothesis_to_evaluate(
                graph,
                [
                    hid
                    for hid in hypothesis_node_ids
                    if hid not in processed_hypotheses_this_stage
                ],
            )
            if not hypothesis_to_evaluate:
                logger.info(
                    "No more eligible hypotheses to evaluate in this iteration or stage."
                )
                break

            processed_hypotheses_this_stage.add(hypothesis_to_evaluate.id)

            # P1.4: Execute plan for h*
            # This returns a list of dicts, each representing a piece of found evidence data
            found_evidence_data_list = await self._execute_hypothesis_plan(
                hypothesis_to_evaluate
            )
            if not found_evidence_data_list:
                logger.debug(
                    f"No new evidence found for hypothesis '{hypothesis_to_evaluate.label}'."
                )
                continue

            related_evidence_nodes_for_current_hypo: list[Node] = []

            for ev_idx, ev_data in enumerate(found_evidence_data_list):
                # P1.4: Create evidence nodes E_r and link to h* (P1.10, P1.24, P1.25 for edge types)
                evidence_node = await self._create_evidence_node_and_link(
                    graph, hypothesis_to_evaluate, ev_data, iteration, ev_idx
                )
                if not evidence_node:
                    continue
                evidence_nodes_created_total += 1
                related_evidence_nodes_for_current_hypo.append(evidence_node)

                # P1.4: Update h*.confidence vector C via Bayesian methods (P1.14)
                # This uses evidence reliability (P1.26 power) and edge type
                prior_hypo_confidence = hypothesis_to_evaluate.confidence
                # Find the edge connecting this evidence to the hypothesis to get its type
                connecting_edge = graph.get_edge(
                    f"edge_ev_{evidence_node.id}_{hypothesis_to_evaluate.id}"
                )
                edge_type_for_update = connecting_edge.type if connecting_edge else None

                new_hypo_confidence = bayesian_update_confidence(
                    prior_confidence=prior_hypo_confidence,
                    evidence_strength=ev_data["strength"],
                    evidence_supports_hypothesis=ev_data["supports_hypothesis"],
                    statistical_power=ev_data["statistical_power"],  # P1.26
                    edge_type=edge_type_for_update,  # P1.10
                )
                hypothesis_to_evaluate.update_confidence(
                    new_hypo_confidence,
                    updated_by=self.stage_name,
                    reason=f"Evidence integration: {evidence_node.id}",
                )
                hypotheses_confidence_updated_total += 1

                # P1.4: Perform cross-node linking & IBN creation (P1.8)
                ibn_id = await self._try_create_interdisciplinary_bridge_node(
                    graph, evidence_node, hypothesis_to_evaluate
                )
                if ibn_id:
                    ibns_created_total += 1

                # P1.12: Update info_metrics for hypothesis node (P1.27)
                # Simplified information gain calculation example
                if hypothesis_to_evaluate.metadata.information_metrics is None:
                    hypothesis_to_evaluate.metadata.information_metrics = (
                        InformationTheoreticMetrics()
                    )
                hypothesis_to_evaluate.metadata.information_metrics.information_gain = (
                    calculate_information_gain(
                        prior_hypo_confidence.to_list(), new_hypo_confidence.to_list()
                    )
                )
                hypothesis_to_evaluate.touch()

            # P1.4: Use hyperedges (P1.9)
            # Consider creating hyperedges if multiple evidence nodes relate to the hypothesis
            new_hyper_ids = await self._try_create_hyperedges(
                graph, hypothesis_to_evaluate, related_evidence_nodes_for_current_hypo
            )
            hyperedges_created_total += len(new_hyper_ids)

        # P1.4 actions after loop (or potentially within, if dynamic):
        # Apply temporal decay (P1.18) & detect temporal patterns (P1.25)
        await self._apply_temporal_decay_and_patterns() # Removed graph
        # Dynamically adapt graph topology (P1.22)
        await self._adapt_graph_topology() # Removed graph

        summary = (
            f"Evidence integration completed over {iteration + 1 if self.max_iterations > 0 and hypothesis_node_ids else 0} iterations. "
            f"Created {evidence_nodes_created_total} evidence nodes. "
            f"Updated {hypotheses_confidence_updated_total} hypotheses. "
            f"Created {ibns_created_total} IBNs and {hyperedges_created_total} hyperedges."
        )
        metrics = {
            "iterations_completed": iteration + 1
            if self.max_iterations > 0 and hypothesis_node_ids
            else 0,
            "evidence_nodes_created": evidence_nodes_created_total,
            "hypotheses_confidence_updated": hypotheses_confidence_updated_total,
            "ibns_created": ibns_created_total,
            "hyperedges_created": hyperedges_created_total,
        }
        # No specific context update strictly needed for next stage unless defined
        # The graph itself has been modified, which is the primary output.
        context_update: dict[str, Any] = {
            "evidence_integration_completed": True,
            "evidence_nodes_added_count": evidence_nodes_created_total,
        }

        output = StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
        self._log_end(current_session_data.session_id, output)
        return output
