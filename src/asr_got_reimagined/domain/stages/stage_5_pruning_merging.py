from typing import Optional # Added Optional
from loguru import logger

from src.asr_got_reimagined.config import Settings
from src.asr_got_reimagined.domain.models.common_types import GoTProcessorSessionData
from src.asr_got_reimagined.domain.models.graph_elements import (
    Edge,
    Node,
    NodeType,
    RevisionRecord,
)
from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph
from src.asr_got_reimagined.domain.utils.metadata_helpers import (
    calculate_semantic_similarity,  # Using our placeholder
)

from .base_stage import BaseStage, StageOutput


class PruningMergingStage(BaseStage):
    stage_name: str = "PruningMergingStage"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        # P1.5: Pruning and Merging thresholds from settings
        self.pruning_confidence_threshold = (
            self.default_params.pruning_confidence_threshold
        )
        self.pruning_impact_threshold = self.default_params.pruning_impact_threshold
        self.merging_semantic_overlap_threshold = (
            self.default_params.merging_semantic_overlap_threshold
        )

    def _should_prune_node(self, node: Node) -> bool:
        """
        Determines if a node should be pruned based on P1.5.
        Pruning threshold: min(E[C]) < threshold & low impact (P1.28).
        Note: P1.5 says "min(E[C])", which means the minimum of the *expected values* of
        the confidence components if they were distributions.
        For our current ConfidenceVector (scalar components), we can interpret E[C] as C itself.
        So, min(C_components) < threshold.
        """
        # Avoid pruning essential structural nodes
        if node.type in [NodeType.ROOT, NodeType.DECOMPOSITION_DIMENSION]:
            return False

        # P1.5: Pruning threshold: min(C_components) < X
        min_confidence_component = min(node.confidence.to_list())

        # P1.5 also says "& low impact (P1.28)"
        impact_score = node.metadata.impact_score or 0.0  # Default to 0 if not set

        if (
            min_confidence_component < self.pruning_confidence_threshold
            and impact_score < self.pruning_impact_threshold
        ):
            logger.debug(
                f"Node '{node.label}' (ID: {node.id}) marked for pruning. Min Confidence: {min_confidence_component:.2f}, Impact: {impact_score:.2f}"
            )
            return True
        return False

    async def _prune_nodes(self, graph: ASRGoTGraph) -> int:
        """
        Removes nodes from the graph that meet pruning criteria for low confidence and low impact.
        
        Nodes are identified for pruning if they fall below configured thresholds for confidence and impact, as determined by `_should_prune_node`. For each pruned node, a revision record is appended to its metadata to document the action. Returns the total number of nodes pruned.
         
        Args:
            graph: The ASRGoTGraph instance from which nodes will be pruned.
        
        Returns:
            The number of nodes removed from the graph.
        """
        nodes_to_prune_ids: set[str] = set()
        for node_id, node_obj in list(
            graph.nodes.items()
        ):  # Iterate over a copy for safe removal
            if self._should_prune_node(node_obj):
                nodes_to_prune_ids.add(node_id)

        pruned_count = 0
        for node_id in nodes_to_prune_ids:
            # Removing a node from ASRGoTGraph should also handle NetworkX graph and related edges.
            # The current ASRGoTGraph.remove_node is basic. A more robust version would
            # properly remove associated edges from self.edges and self.hyperedges.
            removed_node = graph.remove_node(node_id)
            if removed_node:
                # Log the pruning in the graph's metadata or a dedicated audit log if needed
                removed_node.metadata.revision_history.append(
                    RevisionRecord(
                        user_or_process=self.stage_name,
                        action="pruned",
                        changes_made={"status": "removed"},
                        reason=f"Low confidence (min_comp < {self.pruning_confidence_threshold}) and low impact (< {self.pruning_impact_threshold}).",
                    )
                )
                # We don't re-add the node, but this shows how to record it if needed.
                # For now, graph.remove_node is sufficient.
                pruned_count += 1
        if pruned_count > 0:
            logger.info(f"Pruned {pruned_count} low-confidence/low-impact nodes.")
        return pruned_count

    async def _merge_nodes(self, graph: ASRGoTGraph) -> int:
        """
        Merges highly similar nodes in the graph based on semantic similarity.
        
        Compares pairs of nodes of the same type (HYPOTHESIS or EVIDENCE) and merges those whose semantic similarity exceeds the configured threshold. The merge process rewires all edges from the merged-away node to the kept node, combines metadata (including disciplinary tags and descriptions), updates confidence components to the maximum values from both nodes, and records a revision history entry. Nodes already merged in previous steps are skipped. Returns the number of node pairs merged.
         
        Returns:
            The number of node pairs that were merged.
        """
        # This is a complex operation. A simplified approach:
        # 1. Group nodes by type (hypotheses with hypotheses, evidence with evidence).
        # 2. Within each group, compare pairs for semantic overlap.
        # 3. If overlap > threshold, merge the "lesser" node into the "greater" node.
        #    "Lesser/greater" can be defined by confidence, impact, creation time, etc.
        # 4. Merging involves transferring edges, combining metadata, updating confidence.

        merged_nodes_count = 0
        potential_merge_pairs: list[
            tuple[str, str, float]
        ] = []  # (node1_id, node2_id, overlap_score)

        # Iterate over comparable nodes (e.g., hypotheses, evidence)
        # For simplicity, compare all nodes of the same type for now, excluding root/dimension
        comparable_node_types = [
            NodeType.HYPOTHESIS,
            NodeType.EVIDENCE,
        ]  # Extend as needed

        nodes_list = list(graph.nodes.values())  # Get a list of node objects

        for i in range(len(nodes_list)):
            node1 = nodes_list[i]
            if node1.type not in comparable_node_types:
                continue

            for j in range(i + 1, len(nodes_list)):
                node2 = nodes_list[j]
                if node2.type != node1.type:  # Only merge nodes of the same type
                    continue

                # P1.5: semantic_overlap (using placeholder)
                # For actual semantic overlap, use NLP techniques on node.label, node.metadata.description, etc.
                # Our calculate_semantic_similarity is a very basic placeholder.
                text1_to_compare = (
                    node1.label + " " + (node1.metadata.description or "")
                )
                text2_to_compare = (
                    node2.label + " " + (node2.metadata.description or "")
                )
                overlap_score = calculate_semantic_similarity(
                    text1_to_compare, text2_to_compare
                )

                if overlap_score >= self.merging_semantic_overlap_threshold:
                    potential_merge_pairs.append((node1.id, node2.id, overlap_score))
                    logger.debug(
                        f"Potential merge: {node1.id} and {node2.id} (Overlap: {overlap_score:.2f})"
                    )

        # Sort pairs by overlap score (descending) to merge strongest overlaps first
        potential_merge_pairs.sort(key=lambda x: x[2], reverse=True)

        merged_away_ids: set[str] = (
            set()
        )  # Keep track of nodes that have been merged into others

        for node1_id, node2_id, overlap_score in potential_merge_pairs:
            if node1_id in merged_away_ids or node2_id in merged_away_ids:
                continue  # One of the nodes has already been merged

            # Correctly get Optional nodes and then use them after None check
            current_node1: Optional[Node] = graph.get_node(node1_id)
            current_node2: Optional[Node] = graph.get_node(node2_id)

            if not current_node1 or not current_node2:
                continue
            
            # Now current_node1 and current_node2 are confirmed non-None (Node type)

            # Determine which node to keep (target) and which to merge away (source)
            # Simple rule: keep the one with higher average confidence, then higher impact.
            # More sophisticated rules could consider creation date, number of connections, etc.
            keep_node: Node 
            merge_away_node: Node
            keep_node, merge_away_node = (
                (current_node1, current_node2)
                if (
                    current_node1.confidence.average_confidence
                    > current_node2.confidence.average_confidence
                    or (
                        current_node1.confidence.average_confidence
                        == current_node2.confidence.average_confidence
                        and (current_node1.metadata.impact_score or 0)
                        >= (current_node2.metadata.impact_score or 0)
                    )
                )
                else (current_node2, current_node1)
            )

            logger.info(
                f"Merging node '{merge_away_node.label}' (ID: {merge_away_node.id}) into "
                f"'{keep_node.label}' (ID: {keep_node.id}). Overlap: {overlap_score:.2f}"
            )  # 1. Re-wire edges: Point edges from/to merge_away_node to keep_node
            # This requires iterating through graph.edges and graph.nx_graph
            # This is a complex step and needs careful handling in ASRGoTGraph for robust implementation.
            # For now, simplified in ASRGoTGraph.remove_node, but true merge needs more.

            # For each incoming edge to merge_away_node:
            for edge_id, edge_obj in list(graph.edges.items()):  # Iterate on copy
                if edge_obj.target_id == merge_away_node.id:
                    # Recreate edge pointing to keep_node if not already existing with same type
                    new_edge = Edge(
                        source_id=edge_obj.source_id,
                        target_id=keep_node.id,
                        type=edge_obj.type,
                        confidence=edge_obj.confidence,
                        metadata=edge_obj.metadata,
                    )
                    # Avoid duplicate edges of same type between same nodes unless MultiDiGraph logic handles it by ID
                    # Check if such an edge type already exists
                    exists = any(
                        e.source_id == new_edge.source_id
                        and e.target_id == new_edge.target_id
                        and e.type == new_edge.type
                        for e in graph.edges.values()
                    )
                    if not exists:
                        graph.add_edge(new_edge)
                    graph.remove_edge(edge_id)  # Remove old edge

            # For each outgoing edge from merge_away_node:
            for edge_id, edge_obj in list(graph.edges.items()):  # Iterate on copy
                if edge_obj.source_id == merge_away_node.id:
                    new_edge = Edge(
                        source_id=keep_node.id,
                        target_id=edge_obj.target_id,
                        type=edge_obj.type,
                        confidence=edge_obj.confidence,
                        metadata=edge_obj.metadata,
                    )
                    exists = any(
                        e.source_id == new_edge.source_id
                        and e.target_id == new_edge.target_id
                        and e.type == new_edge.type
                        for e in graph.edges.values()
                    )
                    if not exists:
                        graph.add_edge(new_edge)
                    graph.remove_edge(edge_id)

            # 2. Combine metadata (heuristic: append lists, take max for scores, etc.)
            # Example: combine disciplinary tags
            keep_node.metadata.disciplinary_tags.update(
                merge_away_node.metadata.disciplinary_tags
            )
            # Example: combine descriptions (simple append)
            if merge_away_node.metadata.description:
                keep_node.metadata.description = (
                    (keep_node.metadata.description or "")
                    + f"\nMerged content from {merge_away_node.id}: {merge_away_node.metadata.description}"
                )
            # Update confidence - e.g., weighted average or max, needs careful thought based on P1.14 principles
            # Take the maximum value for each confidence component

            # Calculate max values for each component
            new_emp = max(
                keep_node.confidence.empirical_support,
                merge_away_node.confidence.empirical_support,
            )
            new_coherence = max(
                keep_node.confidence.coherence,
                merge_away_node.confidence.coherence,
            )
            new_reliability = max(
                keep_node.confidence.reliability,
                merge_away_node.confidence.reliability,
            )
            new_robustness = max(
                keep_node.confidence.robustness,
                merge_away_node.confidence.robustness,
            )

            # Update the confidence attributes directly instead of creating a new object
            keep_node.confidence.empirical_support = new_emp
            keep_node.confidence.coherence = new_coherence
            keep_node.confidence.reliability = new_reliability
            keep_node.confidence.robustness = new_robustness

            keep_node.metadata.revision_history.append(
                RevisionRecord(
                    user_or_process=self.stage_name,
                    action="merged_node_into_this",
                    changes_made={
                        "merged_from_id": merge_away_node.id,
                        "overlap_score": overlap_score,
                    },
                    reason=f"High semantic overlap ({overlap_score:.2f}) with {merge_away_node.id}.",
                )
            )
            keep_node.touch()

            # 3. Remove merge_away_node
            graph.remove_node(merge_away_node.id)
            merged_away_ids.add(merge_away_node.id)
            merged_nodes_count += 1

        if merged_nodes_count > 0:
            logger.info(f"Merged {merged_nodes_count} pairs of similar nodes.")
        return merged_nodes_count

    async def execute(
        self, graph: ASRGoTGraph, current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        self._log_start(current_session_data.session_id)

        logger.info("Starting node pruning phase...")
        pruned_count = await self._prune_nodes(graph)

        logger.info("Starting node merging phase...")
        merged_count = await self._merge_nodes(graph)

        summary = f"Graph refinement completed. Pruned {pruned_count} nodes. Merged {merged_count} nodes (pairs)."
        metrics = {
            "nodes_pruned": pruned_count,
            "nodes_merged_away": merged_count,  # Each merge operation removes one node
            "nodes_remaining": graph.get_statistics().node_count,
            "edges_remaining": graph.get_statistics().edge_count,
        }
        # No specific context update for next stage, graph is modified in-place.
        context_update = {
            "pruning_merging_completed": True,
            "nodes_after_pruning_merging": graph.get_statistics().node_count,
        }

        output = StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
        self._log_end(current_session_data.session_id, output)
        return output
