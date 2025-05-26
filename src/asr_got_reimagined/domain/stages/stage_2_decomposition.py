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
# from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph # No longer used
from src.asr_got_reimagined.domain.services.neo4j_utils import execute_query, Neo4jError
from .stage_1_initialization import InitializationStage # For context key

import json # For property preparation
from datetime import datetime # For property preparation
from enum import Enum # For property preparation
from typing import Dict, List, Set # For type hints


class DecompositionStage(BaseStage):
    stage_name: str = "DecompositionStage"

    def __init__(self, settings: Settings):
        """
        Initializes the DecompositionStage with default dimension configurations and confidence values.
        
        Args:
            settings: The application settings containing configuration parameters.
        """
        super().__init__(settings)
        self.default_dimensions_config = (
            self.default_params.default_decomposition_dimensions
        )
        self.dimension_confidence_values = (
            self.default_params.dimension_confidence
        )

    def _prepare_node_properties_for_neo4j(self, node_pydantic: Node) -> Dict[str, Any]:
        """
        Converts a Node Pydantic model into a flat dictionary of properties for Neo4j.
        
        Serializes confidence and metadata fields, handling datetimes, enums, lists, sets, and nested Pydantic models. Metadata fields that cannot be serialized to JSON are stored as strings. Properties with None values are excluded from the result.
        
        Returns:
            A dictionary of Neo4j-compatible node properties.
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
                elif hasattr(meta_val, 'model_dump'):
                    try: props[f"metadata_{meta_field}_json"] = json.dumps(meta_val.model_dump())
                    except TypeError as e:
                        logger.warning(f"Could not serialize Pydantic metadata field {meta_field} to JSON: {e}")
                        props[f"metadata_{meta_field}_str"] = str(meta_val)
                else: props[f"metadata_{meta_field}"] = meta_val
        return {k: v for k, v in props.items() if v is not None}

    def _prepare_edge_properties_for_neo4j(self, edge_pydantic: Edge) -> Dict[str, Any]:
        """
        Converts an Edge Pydantic model into a flat dictionary of properties for Neo4j.
        
        Serializes edge metadata fields, handling datetimes (as ISO strings), enums (as values), and complex types (as JSON or string). Excludes properties with None values.
        
        Returns:
            A dictionary of edge properties suitable for Neo4j relationship creation.
        """
        if edge_pydantic is None: return {}
        props = {"id": edge_pydantic.id} # Type is handled by relationship type in query
        # Add confidence if it exists and is not None
        if hasattr(edge_pydantic, 'confidence') and edge_pydantic.confidence is not None:
             props["confidence"] = edge_pydantic.confidence # Assuming confidence is a simple float for edges
        
        if edge_pydantic.metadata:
            for meta_field, meta_val in edge_pydantic.metadata.model_dump().items():
                if meta_val is None: continue
                if isinstance(meta_val, datetime): props[f"metadata_{meta_field}"] = meta_val.isoformat()
                elif isinstance(meta_val, Enum): props[f"metadata_{meta_field}"] = meta_val.value
                # Simplified: assume edge metadata fields are simple or JSON serializable strings
                elif isinstance(meta_val, (list,set,dict)) or hasattr(meta_val, 'model_dump'):
                    try: props[f"metadata_{meta_field}_json"] = json.dumps(meta_val.model_dump() if hasattr(meta_val, 'model_dump') else meta_val)
                    except TypeError: props[f"metadata_{meta_field}_str"] = str(meta_val)
                else: props[f"metadata_{meta_field}"] = meta_val
        return {k: v for k, v in props.items() if v is not None}


    def _get_conceptual_dimensions(
        self, 
        root_node_query_context: Optional[str], 
        custom_dimensions_input: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Selects the list of conceptual dimensions to create, using custom input if provided and valid, or falling back to default configuration.
        
        Args:
            root_node_query_context: Optional context string from the root node, currently unused.
            custom_dimensions_input: Optional list of custom dimension definitions, each as a dict with 'label' and 'description'.
        
        Returns:
            A list of dictionaries, each representing a dimension with 'label' and 'description' keys.
        """
        if custom_dimensions_input and isinstance(custom_dimensions_input, list):
            logger.info("Using custom decomposition dimensions provided in operational parameters.")
            # Basic validation: ensure items are dicts with 'label' and 'description'
            return [
                dim for dim in custom_dimensions_input 
                if isinstance(dim, dict) and "label" in dim and "description" in dim
            ]
        else:
            logger.info("Using default decomposition dimensions from configuration.")
            # Adapt default dimensions, possibly incorporating root_node_query_context
            # For now, directly using configured defaults.
            return [
                {"label": dim.label, "description": dim.description}
                for dim in self.default_dimensions_config
            ]

    async def execute(
        self, current_session_data: GoTProcessorSessionData # graph: ASRGoTGraph removed
    ) -> StageOutput:
        """
        Executes the decomposition stage by creating conceptual dimension nodes and linking them to the root node in Neo4j.
        
        This method retrieves the root node from the session context, determines the set of conceptual dimensions (either from operational parameters or default configuration), and for each dimension:
        - Creates or merges a corresponding dimension node in Neo4j with appropriate metadata.
        - Establishes a `DECOMPOSITION_OF` relationship from the dimension node to the root node.
        
        Handles error conditions such as missing root node, Neo4j query failures, and serialization issues. Updates the session context with the IDs of created dimension nodes and returns a summary of the operation, including metrics for nodes and relationships created.
        
        Args:
            current_session_data: The session data containing accumulated context and operational parameters.
        
        Returns:
            A StageOutput object summarizing the decomposition results, metrics, and context updates.
        """
        self._log_start(current_session_data.session_id)

        initialization_data = current_session_data.accumulated_context.get(
            InitializationStage.stage_name, {}
        )
        root_node_id = initialization_data.get("root_node_id")
        # Ensure disciplinary_tags is a list of strings
        initial_disciplinary_tags: Set[str] = set(initialization_data.get("initial_disciplinary_tags", []))


        if not root_node_id:
            err_msg = "Root node ID not found in session context. Cannot proceed."
            logger.error(err_msg)
            return StageOutput(summary=err_msg, metrics={"dimensions_created_in_neo4j": 0, "relationships_created_in_neo4j": 0},
                               next_stage_context_update={self.stage_name: {"error": err_msg, "dimension_node_ids": []}})
        
        # Fetch root node's query context or label for decomposition input
        root_node_info: Optional[Dict[str, Any]] = None
        try:
            query = "MATCH (n:Node {id: $root_node_id}) RETURN properties(n) AS props"
            results = execute_query(query, {"root_node_id": root_node_id}, tx_type="read")
            if results and results[0].get("props"):
                root_node_info = results[0]["props"]
            else:
                err_msg = f"Root node {root_node_id} not found in Neo4j."
                logger.error(err_msg)
                return StageOutput(summary=err_msg, metrics={"dimensions_created_in_neo4j": 0, "relationships_created_in_neo4j": 0},
                                   next_stage_context_update={self.stage_name: {"error": err_msg, "dimension_node_ids": []}})
        except Neo4jError as e:
            err_msg = f"Neo4j error fetching root node {root_node_id}: {e}"
            logger.error(err_msg)
            return StageOutput(summary=err_msg, metrics={"dimensions_created_in_neo4j": 0, "relationships_created_in_neo4j": 0},
                               next_stage_context_update={self.stage_name: {"error": err_msg, "dimension_node_ids": []}})

        # Use metadata_query_context if available, else label, else a default string
        decomposition_input_text = root_node_info.get("metadata_query_context") or root_node_info.get("label", "Root Task")
        root_node_layer_str = root_node_info.get("metadata_layer_id", self.default_params.initial_layer)


        operational_params = current_session_data.accumulated_context.get("operational_params", {})
        custom_dimensions_input = operational_params.get("decomposition_dimensions")
        
        dimensions_to_create_conceptual = self._get_conceptual_dimensions(decomposition_input_text, custom_dimensions_input)

        dimension_node_ids_created: List[str] = []
        nodes_created_count = 0
        edges_created_count = 0
        dimension_labels_created: List[str] = []

        for i, dim_data in enumerate(dimensions_to_create_conceptual):
            dim_label = dim_data.get("label", f"Dimension {i + 1}")
            dim_description = dim_data.get("description", f"Details for {dim_label}")
            dim_id = f"dim_{root_node_id}_{i}" # Ensure unique ID

            dim_metadata = NodeMetadata(
                description=dim_description,
                source_description="DecompositionStage (P1.2)",
                epistemic_status=EpistemicStatus.ASSUMPTION,
                disciplinary_tags=list(initial_disciplinary_tags), # Inherit tags
                layer_id=operational_params.get("dimension_layer", root_node_layer_str),
                impact_score=0.7,
            )
            dimension_node_pydantic = Node(
                id=dim_id, label=dim_label, type=NodeType.DECOMPOSITION_DIMENSION,
                confidence=ConfidenceVector.from_list(self.dimension_confidence_values),
                metadata=dim_metadata
            )
            node_props_for_neo4j = self._prepare_node_properties_for_neo4j(dimension_node_pydantic)

            try:
                create_dim_node_query = """
                MERGE (d:Node {id: $props.id}) SET d += $props
                WITH d, $type_label AS typeLabel CALL apoc.create.addLabels(d, [typeLabel]) YIELD node
                RETURN node.id AS dimension_id
                """
                params_node = {"props": node_props_for_neo4j, "type_label": NodeType.DECOMPOSITION_DIMENSION.value}
                result_node = execute_query(create_dim_node_query, params_node, tx_type='write')
                
                if not result_node or not result_node[0].get("dimension_id"):
                    logger.error(f"Failed to create or retrieve dimension node {dim_id} in Neo4j.")
                    continue
                
                created_dimension_id = result_node[0]["dimension_id"]
                dimension_node_ids_created.append(created_dimension_id)
                dimension_labels_created.append(dim_label)
                nodes_created_count += 1

                # Create relationship: (Dimension)-[:DECOMPOSITION_OF]->(Root)
                edge_id = f"edge_{created_dimension_id}_decompof_{root_node_id}"
                edge_pydantic = Edge(
                    id=edge_id, source_id=created_dimension_id, target_id=root_node_id,
                    type=EdgeType.DECOMPOSITION_OF, confidence=0.95, # High confidence for structural link
                    metadata=EdgeMetadata(description=f"'{dim_label}' is a decomposition of '{decomposition_input_text[:30]}...'")
                )
                edge_props_for_neo4j = self._prepare_edge_properties_for_neo4j(edge_pydantic)

                create_rel_query = """
                MATCH (dim_node:Node {id: $dim_id})
                MATCH (root_node:Node {id: $root_id})
                MERGE (dim_node)-[r:DECOMPOSITION_OF {id: $props.id}]->(root_node)
                SET r += $props
                RETURN r.id as rel_id
                """
                # Note: EdgeType.DECOMPOSITION_OF.value is used as label, not in props directly for type
                params_rel = {"dim_id": created_dimension_id, "root_id": root_node_id, "props": edge_props_for_neo4j}
                result_rel = execute_query(create_rel_query, params_rel, tx_type='write')

                if result_rel and result_rel[0].get("rel_id"):
                    edges_created_count += 1
                    logger.debug(f"Created dimension node '{dim_label}' (ID: {created_dimension_id}) and linked to root node {root_node_id}.")
                else:
                    logger.error(f"Failed to create DECOMPOSITION_OF relationship for dimension {created_dimension_id} to root {root_node_id}.")

            except Neo4jError as e:
                logger.error(f"Neo4j error creating dimension '{dim_label}' or its relationship: {e}")
            except Exception as e:
                logger.error(f"Unexpected error creating dimension '{dim_label}': {e}")


        summary = f"Task decomposed into {nodes_created_count} dimensions in Neo4j: {', '.join(dimension_labels_created)}."
        metrics = {
            "dimensions_created_in_neo4j": nodes_created_count,
            "relationships_created_in_neo4j": edges_created_count,
        }
        context_update = {"dimension_node_ids": dimension_node_ids_created}

        output = StageOutput(
            summary=summary, metrics=metrics,
            next_stage_context_update={self.stage_name: context_update}
        )
        self._log_end(current_session_data.session_id, output)
        return output
