from typing import Optional # Added Optional
from loguru import logger

from src.asr_got_reimagined.config import Settings
from src.asr_got_reimagined.domain.models.common_types import GoTProcessorSessionData
from src.asr_got_reimagined.domain.models.graph_elements import (
    Edge,
    Node, # Keep for Pydantic type hints if creating any conceptual objects, though not for graph ops
    NodeType,
    # RevisionRecord, # Not directly applicable if nodes are deleted in Neo4j
)
# from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph # No longer used
from src.asr_got_reimagined.domain.services.neo4j_utils import execute_query, Neo4jError # Import Neo4j utils
# from src.asr_got_reimagined.domain.utils.metadata_helpers import calculate_semantic_similarity # Placeholder, hard to use directly in Neo4j

from .base_stage import BaseStage, StageOutput
from typing import List, Dict, Any, Set # For type hints


class PruningMergingStage(BaseStage):
    stage_name: str = "PruningMergingStage"

    def __init__(self, settings: Settings):
        """
        Initializes the PruningMergingStage with pruning and merging thresholds from settings.
        
        Configures thresholds for node and edge pruning, as well as semantic overlap for merging, using values provided in the settings object.
        """
        super().__init__(settings)
        # P1.5: Pruning and Merging thresholds from settings
        self.pruning_confidence_threshold = self.default_params.pruning_confidence_threshold
        self.pruning_impact_threshold = self.default_params.pruning_impact_threshold
        self.merging_semantic_overlap_threshold = self.default_params.merging_semantic_overlap_threshold
        # Example: Threshold for pruning low-confidence edges
        self.pruning_edge_confidence_threshold = self.default_params.get("pruning_edge_confidence_threshold", 0.2)


    async def _prune_low_confidence_impact_nodes_in_neo4j(self) -> int:
        """
        Prunes nodes from Neo4j whose minimum confidence component and impact score are below configured thresholds.
        
        Returns:
            The number of nodes pruned from the database.
        """
        # This query attempts to replicate the min_confidence_component logic.
        # It assumes confidence components are stored as properties like 'confidence_empirical_support', etc.
        # A more direct approach would be if an overall confidence or min_confidence was pre-calculated.
        # For this example, we'll check if ALL known confidence components are below the threshold.
        # This is a common simplification if min() over arbitrary properties isn't easy in Cypher.
        # Or, fetch candidates and apply min() in Python, then batch delete.
        # Let's try fetching and batch deleting for closer logic to original _should_prune_node
        
        fetch_query = """
        MATCH (n:Node)
        WHERE NOT n:ROOT AND NOT n:DECOMPOSITION_DIMENSION 
              AND (n.type = 'HYPOTHESIS' OR n.type = 'EVIDENCE' OR n.type = 'INTERDISCIPLINARY_BRIDGE') 
              // Add other prunable types if necessary
        RETURN n.id AS id,
               n.confidence_empirical_support AS conf_emp,
               n.confidence_theoretical_basis AS conf_theo,
               n.confidence_methodological_rigor AS conf_meth,
               n.confidence_consensus_alignment AS conf_cons,
               n.metadata_impact_score AS impact_score
        """
        nodes_to_prune_ids: List[str] = []
        try:
            candidate_nodes_data = execute_query(fetch_query, {}, tx_type="read")
            if not candidate_nodes_data:
                logger.info("No candidate nodes found for confidence/impact pruning.")
                return 0

            for record_data in candidate_nodes_data:
                node_id = record_data["id"]
                conf_values = [
                    record_data.get("conf_emp", 1.0), # Default to non-prune if component missing
                    record_data.get("conf_theo", 1.0),
                    record_data.get("conf_meth", 1.0),
                    record_data.get("conf_cons", 1.0)
                ]
                min_confidence_component = min(conf_values)
                impact_score = record_data.get("impact_score", 1.0) # Default to non-prune

                if (min_confidence_component < self.pruning_confidence_threshold and
                    impact_score < self.pruning_impact_threshold):
                    nodes_to_prune_ids.append(node_id)
                    logger.debug(f"Node ID: {node_id} marked for pruning. Min Conf: {min_confidence_component:.2f}, Impact: {impact_score:.2f}")

            if not nodes_to_prune_ids:
                logger.info("No nodes met the criteria for confidence/impact pruning after evaluation.")
                return 0

            # Batch delete
            delete_query = """
            UNWIND $node_ids AS node_id
            MATCH (n:Node {id: node_id})
            DETACH DELETE n
            """
            # The execute_query tool doesn't directly return row counts for DETACH DELETE.
            # We'll rely on the number of IDs we sent for deletion as the count.
            execute_query(delete_query, {"node_ids": nodes_to_prune_ids}, tx_type="write")
            logger.info(f"Pruned {len(nodes_to_prune_ids)} low-confidence/low-impact nodes from Neo4j.")
            return len(nodes_to_prune_ids)

        except Neo4jError as e:
            logger.error(f"Neo4j error during node pruning: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error during node pruning: {e}")
            return 0

    async def _prune_isolated_nodes_in_neo4j(self) -> int:
        """
        Removes isolated nodes (nodes with no relationships) from Neo4j, excluding those labeled as ROOT.
        
        Returns:
            The number of nodes that were pruned.
        """
        query = """
        MATCH (n:Node)
        WHERE NOT n:ROOT AND size((n)--()) = 0 
        DETACH DELETE n
        RETURN count(n) as pruned_count
        """
        try:
            result = execute_query(query, {}, tx_type="write")
            pruned_count = result[0]["pruned_count"] if result and result[0] else 0
            if pruned_count > 0:
                logger.info(f"Pruned {pruned_count} isolated nodes from Neo4j.")
            return pruned_count
        except Neo4jError as e:
            logger.error(f"Neo4j error during isolated node pruning: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error during isolated node pruning: {e}")
            return 0
            
    async def _prune_low_confidence_edges_in_neo4j(self) -> int:
        """
        Deletes edges from the Neo4j database whose confidence value is below the configured threshold.
        
        Returns:
            The number of edges that were pruned.
        """
        query = """
        MATCH ()-[r]->()
        WHERE r.confidence IS NOT NULL AND r.confidence < $threshold
        DELETE r
        RETURN count(r) as pruned_count
        """
        try:
            result = execute_query(query, {"threshold": self.pruning_edge_confidence_threshold}, tx_type="write")
            pruned_count = result[0]["pruned_count"] if result and result[0] else 0
            if pruned_count > 0:
                logger.info(f"Pruned {pruned_count} low-confidence edges from Neo4j.")
            return pruned_count
        except Neo4jError as e:
            logger.error(f"Neo4j error during low-confidence edge pruning: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error during low-confidence edge pruning: {e}")
            return 0

    async def _merge_nodes_in_neo4j(self) -> int:
        """
        Placeholder for node merging in Neo4j.
        
        Currently, this method does not perform any merging due to the complexity of implementing semantic similarity-based merging directly in Cypher. Returns zero to indicate no nodes were merged.
        """
        # The original merging logic is heavily reliant on Python-based semantic similarity
        # and complex Pydantic model interactions, which are difficult to translate directly
        # into efficient, generic Cypher queries without pre-calculated similarity scores
        # or a more defined, property-based merging strategy.
        
        # Example of a very simple merge (e.g., duplicate IDs if that were an issue, not semantic):
        # MATCH (n:Node)
        # WITH n.label AS label, n.type AS type, collect(n) AS nodes
        # WHERE size(nodes) > 1
        # CALL apoc.refactor.mergeNodes(nodes, {properties: "combine", mergeRels: true}) YIELD node
        # RETURN count(node) as merged_group_representative_count
        # This is NOT what the original code did and is just an example of APOC usage.

        logger.info("Node merging in Neo4j is currently a placeholder and not fully implemented due to complexity of semantic similarity in Cypher.")
        # For now, this will be a no-op.
        return 0


    async def execute(
        self, current_session_data: GoTProcessorSessionData # graph: ASRGoTGraph removed
    ) -> StageOutput:
        """
        Executes the pruning and merging stage on the Neo4j graph.
        
        This method orchestrates the removal of low-confidence or low-impact nodes, isolated nodes, and low-confidence edges from the Neo4j database. It also invokes a placeholder for node merging. After processing, it collects and returns metrics summarizing the number of elements pruned or merged, as well as the remaining node and edge counts.
        
        Args:
            current_session_data: The session data for the current processing run.
        
        Returns:
            A StageOutput object containing a summary, metrics, and context update for the stage.
        """
        self._log_start(current_session_data.session_id)

        total_nodes_pruned = 0
        total_edges_pruned = 0
        
        logger.info("Starting Neo4j node pruning phase (low confidence/impact)...")
        nodes_pruned_conf_impact = await self._prune_low_confidence_impact_nodes_in_neo4j()
        total_nodes_pruned += nodes_pruned_conf_impact

        logger.info("Starting Neo4j node pruning phase (isolated nodes)...")
        nodes_pruned_isolated = await self._prune_isolated_nodes_in_neo4j()
        total_nodes_pruned += nodes_pruned_isolated
        
        logger.info("Starting Neo4j edge pruning phase (low confidence)...")
        edges_pruned_conf = await self._prune_low_confidence_edges_in_neo4j()
        total_edges_pruned += edges_pruned_conf

        logger.info("Starting Neo4j node merging phase (currently placeholder)...")
        # Merging is complex; the direct Neo4j version is simplified/deferred.
        merged_count = await self._merge_nodes_in_neo4j() 

        # Fetch current node and edge counts from Neo4j for metrics
        nodes_remaining = 0
        edges_remaining = 0
        try:
            count_query = "MATCH (n:Node) RETURN count(n) AS node_count; MATCH ()-[r]->() RETURN count(r) AS edge_count;"
            # This specific tool might only execute one query or handle multi-statement differently.
            # For simplicity, let's assume we can get these counts, or make two calls.
            node_count_res = execute_query("MATCH (n:Node) RETURN count(n) AS node_count", {}, tx_type="read")
            if node_count_res : nodes_remaining = node_count_res[0]["node_count"]
            
            edge_count_res = execute_query("MATCH ()-[r]->() RETURN count(r) AS edge_count", {}, tx_type="read")
            if edge_count_res : edges_remaining = edge_count_res[0]["edge_count"]
            
        except Neo4jError as e:
            logger.error(f"Failed to get node/edge counts from Neo4j: {e}")


        summary = (f"Neo4j graph refinement completed. "
                   f"Total nodes pruned: {total_nodes_pruned}. "
                   f"Total edges pruned: {total_edges_pruned}. "
                   f"Nodes merged (pairs): {merged_count} (merging logic is simplified/placeholder).")
        metrics = {
            "nodes_pruned_in_neo4j": total_nodes_pruned,
            "edges_pruned_in_neo4j": total_edges_pruned,
            "nodes_merged_in_neo4j": merged_count,
            "nodes_remaining_in_neo4j": nodes_remaining,
            "edges_remaining_in_neo4j": edges_remaining,
        }
        context_update = {
            "pruning_merging_completed": True,
            "nodes_after_pruning_merging_in_neo4j": nodes_remaining,
        }

        return StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
