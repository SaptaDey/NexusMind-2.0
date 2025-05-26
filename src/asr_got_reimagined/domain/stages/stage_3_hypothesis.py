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
# from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph # No longer used
from src.asr_got_reimagined.domain.services.neo4j_utils import execute_query, Neo4jError # Import Neo4j utils

import json # For property preparation
from datetime import datetime # For property preparation
from enum import Enum # For property preparation
from typing import Dict, List, Set # For type hints

from .base_stage import BaseStage, StageOutput

# Import names of previous stages to access their output keys in accumulated_context
from .stage_2_decomposition import DecompositionStage


class HypothesisStage(BaseStage):
    stage_name: str = "HypothesisStage"

    def __init__(self, settings: Settings):
        """
        Initializes the HypothesisStage with configuration parameters for hypothesis generation.
        
        Sets up minimum and maximum hypotheses per dimension, confidence values, default disciplinary tags, and default plan types based on provided settings.
        """
        super().__init__(settings)
        self.k_min_hypotheses = self.default_params.hypotheses_per_dimension.min_hypotheses
        self.k_max_hypotheses = self.default_params.hypotheses_per_dimension.max_hypotheses
        self.hypothesis_confidence_values = self.default_params.hypothesis_confidence
        self.default_disciplinary_tags_config = self.default_params.default_disciplinary_tags
        self.default_plan_types_config = self.default_params.default_plan_types

    def _prepare_node_properties_for_neo4j(self, node_pydantic: Node) -> Dict[str, Any]:
        """
        Converts a Pydantic Node model into a flat dictionary of properties suitable for Neo4j storage.
        
        Serializes confidence fields and metadata, handling special types such as datetime, Enum, lists, sets, and nested Pydantic models. Non-serializable metadata fields are converted to strings as a fallback. Properties with None values are excluded from the result.
        """
        if node_pydantic is None: return {}
        props = {"id": node_pydantic.id, "label": node_pydantic.label}
        if node_pydantic.confidence:
            for cv_field, cv_val in node_pydantic.confidence.model_dump().items():
                if cv_val is not None: props[f"confidence_{cv_field}"] = cv_val
        if node_pydantic.metadata:
            for meta_field, meta_val in node_pydantic.metadata.model_dump().items():
                if meta_val is None: continue
                if isinstance(meta_val, datetime): props[f"metadata_{meta_field}"] = meta_val.isoformat()
                elif isinstance(meta_val, Enum): props[f"metadata_{meta_field}"] = meta_val.value
                elif isinstance(meta_val, (list, set)):
                    if all(isinstance(item, (str, int, float, bool)) for item in meta_val):
                        props[f"metadata_{meta_field}"] = list(meta_val)
                    else:
                        try:
                            items_as_dicts = [item.model_dump() if hasattr(item, 'model_dump') else item for item in meta_val]
                            props[f"metadata_{meta_field}_json"] = json.dumps(items_as_dicts)
                        except TypeError as e:
                            logger.warning(f"Could not serialize list/set metadata field {meta_field} to JSON: {e}")
                            props[f"metadata_{meta_field}_str"] = str(meta_val)
                elif hasattr(meta_val, 'model_dump'): # Handles Plan, FalsificationCriteria, BiasFlag if they are direct fields
                    try: props[f"metadata_{meta_field}_json"] = json.dumps(meta_val.model_dump())
                    except TypeError as e:
                        logger.warning(f"Could not serialize Pydantic metadata field {meta_field} to JSON: {e}")
                        props[f"metadata_{meta_field}_str"] = str(meta_val)
                else: props[f"metadata_{meta_field}"] = meta_val
        return {k: v for k, v in props.items() if v is not None}

    def _prepare_edge_properties_for_neo4j(self, edge_pydantic: Edge) -> Dict[str, Any]:
        """
        Converts an Edge Pydantic model into a flat dictionary of properties suitable for Neo4j storage.
        
        Serializes edge ID, confidence (if present), and metadata fields, handling special types such as datetime, Enum, lists, sets, dictionaries, and nested Pydantic models. Metadata fields are prefixed and serialized as JSON or string as needed. Properties with None values are excluded from the result.
        
        Returns:
            A dictionary of edge properties formatted for Neo4j.
        """
        if edge_pydantic is None: return {}
        props = {"id": edge_pydantic.id}
        if hasattr(edge_pydantic, 'confidence') and edge_pydantic.confidence is not None:
             props["confidence"] = edge_pydantic.confidence
        if edge_pydantic.metadata:
            for meta_field, meta_val in edge_pydantic.metadata.model_dump().items():
                if meta_val is None: continue
                if isinstance(meta_val, datetime): props[f"metadata_{meta_field}"] = meta_val.isoformat()
                elif isinstance(meta_val, Enum): props[f"metadata_{meta_field}"] = meta_val.value
                elif isinstance(meta_val, (list,set,dict)) or hasattr(meta_val, 'model_dump'):
                    try: props[f"metadata_{meta_field}_json"] = json.dumps(meta_val.model_dump() if hasattr(meta_val, 'model_dump') else meta_val)
                    except TypeError: props[f"metadata_{meta_field}_str"] = str(meta_val)
                else: props[f"metadata_{meta_field}"] = meta_val
        return {k: v for k, v in props.items() if v is not None}

    async def _generate_hypothesis_content(
        self, dimension_label: str, dimension_tags: Set[str], hypo_index: int, initial_query: str
    ) -> dict[str, Any]:
        """
        Generates randomized metadata for a single hypothesis related to a given dimension.
        
        Args:
            dimension_label: The label of the dimension node this hypothesis is based on.
            dimension_tags: Disciplinary tags associated with the dimension node.
            hypo_index: The index of the hypothesis for this dimension.
            initial_query: The original query string that prompted hypothesis generation.
        
        Returns:
            A dictionary containing hypothesis metadata, including a descriptive label, plan, falsification criteria, optional bias flags, impact score, and disciplinary tags.
        """
        base_hypothesis_text = f"Hypothesis {hypo_index + 1} regarding '{dimension_label}' for query '{initial_query[:30]}...'"
        plan_type = random.choice(self.default_plan_types_config)
        plan_pydantic = Plan(
            type=plan_type, description=f"Plan to evaluate '{base_hypothesis_text}' via {plan_type}.",
            estimated_cost=random.uniform(0.2, 0.8), estimated_duration=random.uniform(1.0, 5.0),
            required_resources=[random.choice(["dataset_X", "computational_cluster", "expert_A"])]
        )
        fals_conditions = [f"Observe contradictory evidence from {plan_type}", f"Find statistical insignificance in {random.choice(['key_metric_A', 'key_metric_B'])}"]
        falsifiability_pydantic = FalsificationCriteria(
            description=f"This hypothesis could be falsified if {fals_conditions[0].lower()} or if {fals_conditions[1].lower()}.",
            testable_conditions=fals_conditions
        )
        bias_flags_list = []
        if random.random() < 0.15:
            bias_type = random.choice(["Confirmation Bias", "Availability Heuristic", "Anchoring Bias"])
            bias_flags_list.append(BiasFlag(
                bias_type=bias_type, description=f"Potential {bias_type} in formulating or prioritizing this hypothesis.",
                assessment_stage_id=self.stage_name, severity=random.choice(["low", "medium"])
            ))
        impact_score_float = random.uniform(0.2, 0.9)
        num_tags = random.randint(1, min(2, len(self.default_disciplinary_tags_config)))
        hypo_disciplinary_tags = set(random.sample(self.default_disciplinary_tags_config, num_tags))
        hypo_disciplinary_tags.update(dimension_tags) # Add dimension's tags

        return {
            "label": base_hypothesis_text, "plan": plan_pydantic,
            "falsification_criteria": falsifiability_pydantic, "bias_flags": bias_flags_list,
            "impact_score": impact_score_float, "disciplinary_tags": list(hypo_disciplinary_tags),
        }

    async def execute(
        self, current_session_data: GoTProcessorSessionData # graph: ASRGoTGraph removed
    ) -> StageOutput:
        """
        Executes the hypothesis generation stage by creating hypothesis nodes and their relationships in Neo4j for each dimension node identified in the previous decomposition stage.
        
        For each dimension node, generates a random number of hypotheses within configured bounds, creates corresponding hypothesis nodes with metadata, and establishes GENERATES_HYPOTHESIS relationships from the dimension to each hypothesis in the Neo4j database. Handles missing dimensions and Neo4j errors gracefully, logging issues and skipping problematic entries.
        
        Returns:
            StageOutput: Contains a summary, metrics on created nodes and relationships, and an updated context with all created hypothesis node IDs.
        """
        self._log_start(current_session_data.session_id)

        decomposition_data = current_session_data.accumulated_context.get(DecompositionStage.stage_name, {})
        dimension_node_ids: List[str] = decomposition_data.get("dimension_node_ids", [])
        initial_query = current_session_data.query # Needed for hypothesis content generation
        operational_params = current_session_data.accumulated_context.get("operational_params", {})

        if not dimension_node_ids:
            logger.warning("No dimension node IDs found. Skipping hypothesis generation.")
            return StageOutput(summary="Hypothesis generation skipped: No dimensions.",
                               metrics={"hypotheses_created_in_neo4j": 0, "relationships_created_in_neo4j": 0},
                               next_stage_context_update={self.stage_name: {"error": "No dimensions found", "hypothesis_node_ids": []}})

        all_hypothesis_node_ids_created: List[str] = []
        nodes_created_count = 0
        edges_created_count = 0

        k_min = operational_params.get("hypotheses_per_dimension_min", self.k_min_hypotheses)
        k_max = operational_params.get("hypotheses_per_dimension_max", self.k_max_hypotheses)
        
        for dim_id in dimension_node_ids:
            try:
                # Fetch dimension node properties from Neo4j
                fetch_dim_query = "MATCH (d:Node {id: $dimension_id}) RETURN properties(d) as props, labels(d) as labels"
                dim_records = execute_query(fetch_dim_query, {"dimension_id": dim_id}, tx_type="read")
                if not dim_records or not dim_records[0].get("props"):
                    logger.warning(f"Dimension node {dim_id} not found in Neo4j. Skipping.")
                    continue
                
                dim_props = dim_records[0]["props"]
                # dim_labels = dim_records[0]["labels"] # Not directly used for now, but fetched
                
                # Extract necessary info for hypothesis generation
                dimension_label_for_hypo = dim_props.get("label", "Unknown Dimension")
                dimension_tags_for_hypo = set(dim_props.get("metadata_disciplinary_tags", []))
                dimension_layer_for_hypo = dim_props.get("metadata_layer_id", self.default_params.initial_layer)

                k_hypotheses_to_generate = random.randint(k_min, k_max)
                logger.debug(f"Generating {k_hypotheses_to_generate} hypotheses for dimension: '{dimension_label_for_hypo}' (ID: {dim_id})")

                for i in range(k_hypotheses_to_generate):
                    hypo_content = await self._generate_hypothesis_content(
                        dimension_label_for_hypo, dimension_tags_for_hypo, i, initial_query
                    )
                    hypo_id = f"hypo_{dim_id}_{i}" # Ensure unique ID format

                    hypo_metadata = NodeMetadata(
                        description=f"A hypothesis related to dimension: '{dimension_label_for_hypo}'.",
                        source_description="HypothesisStage (P1.3)",
                        epistemic_status=EpistemicStatus.HYPOTHESIS,
                        disciplinary_tags=list(hypo_content["disciplinary_tags"]),
                        falsification_criteria=hypo_content["falsification_criteria"],
                        bias_flags=hypo_content["bias_flags"],
                        impact_score=hypo_content["impact_score"],
                        plan=hypo_content["plan"],
                        layer_id=operational_params.get("hypothesis_layer", dimension_layer_for_hypo),
                    )
                    hypothesis_node_pydantic = Node(
                        id=hypo_id, label=hypo_content["label"], type=NodeType.HYPOTHESIS,
                        confidence=ConfidenceVector.from_list(self.hypothesis_confidence_values),
                        metadata=hypo_metadata
                    )
                    hyp_props_for_neo4j = self._prepare_node_properties_for_neo4j(hypothesis_node_pydantic)

                    create_hyp_node_query = """
                    MERGE (h:Node {id: $props.id}) SET h += $props
                    WITH h, $type_label AS typeLabel CALL apoc.create.addLabels(h, [typeLabel]) YIELD node
                    RETURN node.id AS hypothesis_id
                    """
                    params_hyp_node = {"props": hyp_props_for_neo4j, "type_label": NodeType.HYPOTHESIS.value}
                    result_hyp_node = execute_query(create_hyp_node_query, params_hyp_node, tx_type='write')

                    if not result_hyp_node or not result_hyp_node[0].get("hypothesis_id"):
                        logger.error(f"Failed to create hypothesis node {hypo_id} in Neo4j.")
                        continue
                    
                    created_hypothesis_id = result_hyp_node[0]["hypothesis_id"]
                    all_hypothesis_node_ids_created.append(created_hypothesis_id)
                    nodes_created_count += 1

                    # Create relationship: (Dimension)-[:GENERATES_HYPOTHESIS]->(Hypothesis)
                    edge_id = f"edge_{dim_id}_genhyp_{created_hypothesis_id}"
                    edge_pydantic = Edge(
                        id=edge_id, source_id=dim_id, target_id=created_hypothesis_id,
                        type=EdgeType.GENERATES_HYPOTHESIS, confidence=0.9,
                        metadata=EdgeMetadata(description=f"Hypothesis '{hypo_content['label']}' generated for dimension '{dimension_label_for_hypo}'.")
                    )
                    edge_props_for_neo4j = self._prepare_edge_properties_for_neo4j(edge_pydantic)
                    
                    create_rel_query = """
                    MATCH (dim:Node {id: $dimension_id})
                    MATCH (hyp:Node {id: $hypothesis_id})
                    MERGE (dim)-[r:GENERATES_HYPOTHESIS {id: $props.id}]->(hyp)
                    SET r += $props
                    RETURN r.id as rel_id
                    """
                    params_rel = {"dimension_id": dim_id, "hypothesis_id": created_hypothesis_id, "props": edge_props_for_neo4j}
                    result_rel = execute_query(create_rel_query, params_rel, tx_type='write')

                    if result_rel and result_rel[0].get("rel_id"):
                        edges_created_count += 1
                    else:
                        logger.error(f"Failed to create GENERATES_HYPOTHESIS relationship for {dim_id} to {created_hypothesis_id}.")

            except Neo4jError as e:
                logger.error(f"Neo4j error processing dimension {dim_id}: {e}. Skipping.")
            except Exception as e: # Catch other unexpected errors for a specific dimension
                logger.error(f"Unexpected error processing dimension {dim_id}: {e}. Skipping.")


        summary = f"Generated {nodes_created_count} hypotheses in Neo4j across {len(dimension_node_ids)} dimensions."
        metrics = {
            "hypotheses_created_in_neo4j": nodes_created_count,
            "relationships_created_in_neo4j": edges_created_count,
            "avg_hypotheses_per_dimension": nodes_created_count / len(dimension_node_ids) if dimension_node_ids else 0,
        }
        context_update = {"hypothesis_node_ids": all_hypothesis_node_ids_created}

        return StageOutput(summary=summary, metrics=metrics, next_stage_context_update={self.stage_name: context_update})
