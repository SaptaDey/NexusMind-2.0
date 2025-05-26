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
# from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph # No longer used
from src.asr_got_reimagined.domain.services.neo4j_utils import execute_query, Neo4jError # Import Neo4j utils
from src.asr_got_reimagined.domain.utils.math_helpers import ( # Ensure these are still relevant
    bayesian_update_confidence, # This will be used
    calculate_information_gain, # This will be used
)
from src.asr_got_reimagined.domain.utils.metadata_helpers import (
    calculate_semantic_similarity, # This will be used
)

from .base_stage import BaseStage, StageOutput
from .stage_3_hypothesis import HypothesisStage  # To access hypothesis_node_ids

import json # For property preparation
from datetime import datetime as dt # Alias dt for datetime.datetime
from enum import Enum # For property preparation
from typing import Dict, List, Set, Tuple # For type hints


class EvidenceStage(BaseStage):
    stage_name: str = "EvidenceStage"

    def __init__(self, settings: Settings):
        """
        Initializes the EvidenceStage with configuration parameters for evidence integration.
        
        Args:
            settings: Configuration settings containing parameters for evidence processing, such as maximum iterations, IBN similarity threshold, and minimum nodes for hyperedge creation.
        """
        super().__init__(settings)
        self.max_iterations = self.default_params.evidence_max_iterations
        self.ibn_similarity_threshold = self.default_params.get("ibn_similarity_threshold", 0.5) # Use .get for safety
        self.min_nodes_for_hyperedge_consideration = self.default_params.get("min_nodes_for_hyperedge", 2) # Use .get

    def _prepare_node_properties_for_neo4j(self, node_pydantic: Node) -> Dict[str, Any]:
        """
        Converts a Pydantic Node model into a flat dictionary of properties suitable for Neo4j storage.
        
        Serializes confidence and metadata fields, handling nested structures, dates, enums, lists, sets, and nested Pydantic models. Non-serializable fields are converted to strings if JSON serialization fails. Returns a dictionary containing only non-None values.
        """
        if node_pydantic is None: return {}
        props = {"id": node_pydantic.id, "label": node_pydantic.label}
        if node_pydantic.confidence:
            for cv_field, cv_val in node_pydantic.confidence.model_dump().items():
                if cv_val is not None: props[f"confidence_{cv_field}"] = cv_val
        if node_pydantic.metadata:
            for meta_field, meta_val in node_pydantic.metadata.model_dump().items():
                if meta_val is None: continue
                if isinstance(meta_val, dt): props[f"metadata_{meta_field}"] = meta_val.isoformat()
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
        Converts an Edge Pydantic model into a flat dictionary of properties suitable for Neo4j storage.
        
        Serializes confidence and metadata fields, handling dates, enums, lists, sets, dictionaries, and nested Pydantic models. Falls back to string representation if JSON serialization fails. Returns a dictionary containing only non-None values.
        """
        if edge_pydantic is None: return {}
        props = {"id": edge_pydantic.id}
        if hasattr(edge_pydantic, 'confidence') and edge_pydantic.confidence is not None:
             props["confidence"] = edge_pydantic.confidence
        if edge_pydantic.metadata:
            for meta_field, meta_val in edge_pydantic.metadata.model_dump().items():
                if meta_val is None: continue
                if isinstance(meta_val, dt): props[f"metadata_{meta_field}"] = meta_val.isoformat()
                elif isinstance(meta_val, Enum): props[f"metadata_{meta_field}"] = meta_val.value
                elif isinstance(meta_val, (list,set,dict)) or hasattr(meta_val, 'model_dump'):
                    try: props[f"metadata_{meta_field}_json"] = json.dumps(meta_val.model_dump() if hasattr(meta_val, 'model_dump') else meta_val)
                    except TypeError: props[f"metadata_{meta_field}_str"] = str(meta_val)
                else: props[f"metadata_{meta_field}"] = meta_val
        return {k: v for k, v in props.items() if v is not None}

    async def _select_hypothesis_to_evaluate_from_neo4j(
        self, hypothesis_node_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Selects the most suitable hypothesis node from Neo4j for evidence integration.
        
        Queries Neo4j for hypotheses matching the provided IDs, retrieves up to 10 candidates ordered by impact score and empirical confidence, and scores them locally based on impact and confidence variance. Returns the highest scoring hypothesis data dictionary, or None if no eligible hypothesis is found.
        """
        if not hypothesis_node_ids: return None
        
        query = """
        UNWIND $hypothesis_ids AS hypo_id
        MATCH (h:Node:HYPOTHESIS {id: hypo_id})
        RETURN 
            h.id AS id, 
            h.label AS label, 
            h.metadata_impact_score AS impact_score,
            h.confidence_empirical_support AS conf_empirical,
            h.confidence_theoretical_basis AS conf_theoretical,
            h.confidence_methodological_rigor AS conf_methodological,
            h.confidence_consensus_alignment AS conf_consensus,
            h.metadata_plan_json AS plan_json, // Assuming plan is stored as JSON string
            h.metadata_layer_id AS layer_id
        ORDER BY impact_score DESC, conf_empirical ASC // Example sorting
        LIMIT 10 
        """ # Fetch a few candidates to score locally
        
        try:
            results = execute_query(query, {"hypothesis_ids": hypothesis_node_ids}, tx_type="read")
            if not results: return None

            eligible_hypotheses_data = []
            for record in results:
                hypo_data = dict(record) # Convert Neo4j record to dict
                # Reconstruct confidence vector for scoring
                conf_list = [
                    hypo_data.get('conf_empirical', 0.5), hypo_data.get('conf_theoretical', 0.5),
                    hypo_data.get('conf_methodological', 0.5), hypo_data.get('conf_consensus', 0.5)
                ]
                hypo_data['confidence_vector_list'] = conf_list
                eligible_hypotheses_data.append(hypo_data)

            if not eligible_hypotheses_data: return None

            def score_hypothesis_data(h_data: Dict[str, Any]):
                """
                Calculates a score for a hypothesis based on its impact and confidence variance.
                
                The score is computed as the sum of the hypothesis's impact score and the variance of its confidence vector, favoring hypotheses with both high impact and high confidence variance.
                
                Args:
                    h_data: Dictionary containing hypothesis data, expected to include 'impact_score' and 'confidence_vector_list'.
                
                Returns:
                    A float representing the combined score of impact and confidence variance.
                """
                impact = h_data.get('impact_score', 0.1)
                conf_list = h_data.get('confidence_vector_list', [0.5]*4)
                conf_variance = sum([(c - 0.5) ** 2 for c in conf_list]) / 4.0
                return impact + conf_variance # Higher score for higher impact and higher variance

            eligible_hypotheses_data.sort(key=score_hypothesis_data, reverse=True)
            selected_hypothesis_data = eligible_hypotheses_data[0]
            logger.debug(f"Selected hypothesis '{selected_hypothesis_data['label']}' (ID: {selected_hypothesis_data['id']}) from Neo4j for evidence integration.")
            return selected_hypothesis_data
        except Neo4jError as e:
            logger.error(f"Neo4j error selecting hypothesis: {e}")
            return None

    async def _execute_hypothesis_plan(
        self, hypothesis_data_from_neo4j: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generates simulated evidence data for a given hypothesis.
        
        Given hypothesis data from Neo4j, this method creates one or two mock evidence entries with randomized support, strength, statistical power, and disciplinary tags. The generated evidence mimics the outcome of executing a hypothesis plan and is intended for testing or demonstration purposes.
        
        Args:
            hypothesis_data_from_neo4j: Dictionary containing hypothesis properties, including optional plan information.
        
        Returns:
            A list of dictionaries, each representing a simulated piece of evidence with content, support flag, strength, statistical power, disciplinary tags, and timestamp.
        """
        hypo_label = hypothesis_data_from_neo4j.get("label", "Unknown Hypothesis")
        plan_json_str = hypothesis_data_from_neo4j.get("plan_json")
        plan_type_simulated = "SimulatedPlanExecution"
        if plan_json_str:
            try:
                plan_dict = json.loads(plan_json_str)
                plan_type_simulated = plan_dict.get("type", plan_type_simulated)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse plan_json for hypothesis {hypo_label}")
        
        logger.info(f"Executing plan type '{plan_type_simulated}' for hypothesis '{hypo_label}'.")
        num_evidence_pieces = random.randint(1, 2)
        generated_evidence_data_list = []
        for i in range(num_evidence_pieces):
            supports_hypothesis = random.random() > 0.25
            evidence_strength = random.uniform(0.4, 0.9)
            stat_power_val = random.uniform(0.5, 0.95)
            stat_power = StatisticalPower(value=stat_power_val, method_description="Simulated statistical power.")
            evidence_tags = set(random.sample(self.default_params.default_disciplinary_tags, random.randint(1, len(self.default_params.default_disciplinary_tags))))
            if random.random() < 0.3: evidence_tags.add(f"special_evidence_domain_{random.randint(1,3)}")
            evidence_content = f"Evidence piece {i+1} {'supporting' if supports_hypothesis else 'contradicting'} hypothesis '{hypo_label[:30]}...' (Strength: {evidence_strength:.2f})"
            generated_evidence_data_list.append({
                "content": evidence_content, "source_description": f"Simulated {plan_type_simulated} execution",
                "supports_hypothesis": supports_hypothesis, "strength": evidence_strength,
                "statistical_power": stat_power, "disciplinary_tags": list(evidence_tags),
                "timestamp": dt.now() # Use alias dt
            })
        logger.debug(f"Generated {len(generated_evidence_data_list)} pieces of mock evidence for hypothesis '{hypo_label}'.")
        return generated_evidence_data_list

    async def _create_evidence_in_neo4j(
        self, hypothesis_data_from_neo4j: Dict[str, Any], evidence_data: Dict[str, Any], iteration: int, evidence_index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Creates an evidence node in Neo4j and links it to a hypothesis node.
        
        Given hypothesis data and evidence details, this method constructs an evidence node with appropriate properties and metadata, inserts it into the Neo4j database, and creates a relationship to the hypothesis node indicating whether the evidence supports or contradicts the hypothesis. Returns the created evidence node's properties if successful, or None if creation or linking fails.
        """
        hypothesis_id = hypothesis_data_from_neo4j["id"]
        hypothesis_label = hypothesis_data_from_neo4j.get("label", "N/A")
        hypothesis_layer_id = hypothesis_data_from_neo4j.get("layer_id", self.default_params.initial_layer)

        evidence_id = f"ev_{hypothesis_id}_{iteration}_{evidence_index}"
        edge_type = EdgeType.SUPPORTIVE if evidence_data["supports_hypothesis"] else EdgeType.CONTRADICTORY
        
        evidence_metadata = NodeMetadata(
            description=evidence_data["content"], source_description=evidence_data["source_description"],
            epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED if evidence_data["supports_hypothesis"] else EpistemicStatus.EVIDENCE_CONTRADICTED,
            disciplinary_tags=set(evidence_data["disciplinary_tags"]), statistical_power=evidence_data["statistical_power"],
            impact_score=evidence_data["strength"] * (evidence_data["statistical_power"].value if evidence_data["statistical_power"] else 0.5),
            layer_id=hypothesis_layer_id, # Evidence inherits layer from hypothesis
            # Ensure temporal_data is correctly passed or constructed if needed by NodeMetadata
            # For simplicity, if NodeMetadata expects a specific structure for temporal_data, adjust here.
            # Assuming timestamp is directly usable or NodeMetadata handles it.
            # If NodeMetadata expects a TemporalContext object, create it:
            # temporal_context=TemporalContext(creation_timestamp=evidence_data["timestamp"])
        )
        evidence_confidence_vec = ConfidenceVector(
            empirical_support=evidence_data["strength"], methodological_rigor=evidence_data.get("methodological_rigor", evidence_data["strength"] * 0.8),
            theoretical_basis=0.5, consensus_alignment=0.5
        )
        evidence_node_pydantic = Node(
            id=evidence_id, label=f"Evidence {evidence_index+1} for H: {hypothesis_label[:20]}...",
            type=NodeType.EVIDENCE, confidence=evidence_confidence_vec, metadata=evidence_metadata
        )
        ev_props_for_neo4j = self._prepare_node_properties_for_neo4j(evidence_node_pydantic)
        # Add timestamp directly if not deeply nested in metadata prep
        ev_props_for_neo4j["metadata_timestamp_iso"] = evidence_data["timestamp"].isoformat()


        create_ev_node_query = """
        MERGE (e:Node {id: $props.id}) SET e += $props
        WITH e, $type_label AS typeLabel CALL apoc.create.addLabels(e, [typeLabel]) YIELD node
        RETURN node.id AS evidence_id, properties(node) as evidence_props
        """
        try:
            result_ev_node = execute_query(create_ev_node_query, {"props": ev_props_for_neo4j, "type_label": NodeType.EVIDENCE.value}, tx_type='write')
            if not result_ev_node or not result_ev_node[0].get("evidence_id"):
                logger.error(f"Failed to create evidence node {evidence_id} in Neo4j.")
                return None
            
            created_evidence_id = result_ev_node[0]["evidence_id"]
            created_evidence_props = result_ev_node[0]["evidence_props"]

            edge_to_hypo_id = f"edge_ev_{created_evidence_id}_{hypothesis_id}"
            edge_pydantic = Edge(
                id=edge_to_hypo_id, source_id=created_evidence_id, target_id=hypothesis_id, type=edge_type,
                confidence=evidence_data["strength"],
                metadata=EdgeMetadata(description=f"Evidence '{evidence_node_pydantic.label[:20]}...' {'supports' if evidence_data['supports_hypothesis'] else 'contradicts'} hypothesis.")
            )
            edge_props_for_neo4j = self._prepare_edge_properties_for_neo4j(edge_pydantic)

            create_rel_query = """
            MATCH (ev:Node {id: $evidence_id})
            MATCH (hyp:Node {id: $hypothesis_id})
            MERGE (ev)-[r:%s {id: $props.id}]->(hyp)
            SET r += $props
            RETURN r.id as rel_id
            """ % edge_type.value # Dynamically set relationship type
            
            params_rel = {"evidence_id": created_evidence_id, "hypothesis_id": hypothesis_id, "props": edge_props_for_neo4j}
            result_rel = execute_query(create_rel_query, params_rel, tx_type='write')

            if not result_rel or not result_rel[0].get("rel_id"):
                logger.error(f"Failed to link evidence {created_evidence_id} to hypothesis {hypothesis_id}.")
                # Potentially delete orphaned evidence node or mark for cleanup
                return None
            
            logger.debug(f"Created evidence node {created_evidence_id} and linked to hypothesis {hypothesis_id} with type {edge_type.value}.")
            # Return the properties of the created evidence node for IBN/Hyperedge creation
            return {"id": created_evidence_id, **created_evidence_props} # Include ID with other properties

        except Neo4jError as e:
            logger.error(f"Neo4j error creating evidence or link: {e}")
            return None
    
    async def _update_hypothesis_confidence_in_neo4j(
        self, hypothesis_id: str, prior_confidence: ConfidenceVector, 
        evidence_strength: float, supports_hypothesis: bool, 
        statistical_power: Optional[StatisticalPower], edge_type: Optional[EdgeType]
    ) -> bool:
        """
        Updates the confidence vector of a hypothesis node in Neo4j based on new evidence.
        
        Performs a Bayesian update of the hypothesis's confidence values using the provided evidence strength, support flag, statistical power, and edge type. The updated confidence and calculated information gain are persisted to the hypothesis node in Neo4j. Returns True if the update succeeds, otherwise False.
        
        Args:
            hypothesis_id: The unique identifier of the hypothesis node to update.
            prior_confidence: The current confidence vector of the hypothesis.
            evidence_strength: The strength of the new evidence.
            supports_hypothesis: Whether the evidence supports the hypothesis.
            statistical_power: The statistical power associated with the evidence, if available.
            edge_type: The type of relationship between the evidence and the hypothesis.
        
        Returns:
            True if the hypothesis confidence was successfully updated in Neo4j, False otherwise.
        """
        new_confidence_vec = bayesian_update_confidence(
            prior_confidence=prior_confidence, evidence_strength=evidence_strength,
            evidence_supports_hypothesis=supports_hypothesis, statistical_power=statistical_power, edge_type=edge_type
        )
        information_gain = calculate_information_gain(prior_confidence.to_list(), new_confidence_vec.to_list())

        update_query = """
        MATCH (h:Node:HYPOTHESIS {id: $id})
        SET h.confidence_empirical_support = $conf_emp,
            h.confidence_theoretical_basis = $conf_theo,
            h.confidence_methodological_rigor = $conf_meth,
            h.confidence_consensus_alignment = $conf_cons,
            h.metadata_information_gain = $info_gain,
            h.metadata_last_updated_iso = $timestamp
        RETURN h.id
        """
        params = {
            "id": hypothesis_id,
            "conf_emp": new_confidence_vec.empirical_support,
            "conf_theo": new_confidence_vec.theoretical_basis,
            "conf_meth": new_confidence_vec.methodological_rigor,
            "conf_cons": new_confidence_vec.consensus_alignment,
            "info_gain": information_gain,
            "timestamp": dt.now().isoformat()
        }
        try:
            result = execute_query(update_query, params, tx_type="write")
            if result and result[0].get("id"):
                logger.debug(f"Updated confidence for hypothesis {hypothesis_id} in Neo4j.")
                return True
            logger.warning(f"Failed to update confidence for hypothesis {hypothesis_id} in Neo4j.")
            return False
        except Neo4jError as e:
            logger.error(f"Neo4j error updating hypothesis confidence {hypothesis_id}: {e}")
            return False

    async def _create_ibn_in_neo4j(
        self, evidence_node_data: Dict[str, Any], hypothesis_node_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Creates an Interdisciplinary Bridge Node (IBN) in Neo4j to connect evidence and hypothesis nodes from distinct disciplines if their semantic similarity exceeds a threshold.
        
        If the evidence and hypothesis nodes have non-overlapping disciplinary tags and their semantic similarity is above the configured threshold, this method creates an IBN node in Neo4j, links it to both the evidence and hypothesis nodes, and returns the IBN node's ID. Returns None if conditions are not met or if Neo4j operations fail.
        """
        hypo_tags_str = hypothesis_node_data.get("metadata_disciplinary_tags", [])
        ev_tags_str = evidence_node_data.get("metadata_disciplinary_tags", [])
        hypo_tags = set(json.loads(hypo_tags_str) if isinstance(hypo_tags_str, str) else hypo_tags_str) # Handle JSON string or list
        ev_tags = set(json.loads(ev_tags_str) if isinstance(ev_tags_str, str) else ev_tags_str)


        if not hypo_tags or not ev_tags or hypo_tags.intersection(ev_tags):
            return None

        similarity = calculate_semantic_similarity(hypothesis_node_data.get("label",""), evidence_node_data.get("label",""))
        if similarity < self.ibn_similarity_threshold:
            return None

        ibn_id = f"ibn_{evidence_node_data['id']}_{hypothesis_node_data['id']}"
        ibn_label = f"IBN: {evidence_node_data.get('label', 'Ev')[:20]}... <=> {hypothesis_node_data.get('label', 'Hypo')[:20]}..."
        
        ibn_metadata = NodeMetadata(
            description=f"Interdisciplinary bridge between domains {hypo_tags} and {ev_tags}.",
            source_description="EvidenceStage IBN Creation (P1.8)", epistemic_status=EpistemicStatus.INFERRED,
            disciplinary_tags=list(hypo_tags.union(ev_tags)),
            interdisciplinary_info=InterdisciplinaryInfo(
                source_disciplines=list(hypo_tags), target_disciplines=list(ev_tags),
                bridging_concept=f"Connection between '{evidence_node_data.get('label', '')[:20]}' and '{hypothesis_node_data.get('label', '')[:20]}'"
            ),
            impact_score=0.6, layer_id=evidence_node_data.get("metadata_layer_id", self.default_params.initial_layer)
        )
        ibn_confidence = ConfidenceVector(empirical_support=similarity, theoretical_basis=0.4, methodological_rigor=0.5, consensus_alignment=0.3)
        ibn_node_pydantic = Node(id=ibn_id, label=ibn_label, type=NodeType.INTERDISCIPLINARY_BRIDGE, confidence=ibn_confidence, metadata=ibn_metadata)
        ibn_props = self._prepare_node_properties_for_neo4j(ibn_node_pydantic)

        try:
            create_ibn_query = """
            MERGE (ibn:Node {id: $props.id}) SET ibn += $props
            WITH ibn, $type_label AS typeLabel CALL apoc.create.addLabels(ibn, [typeLabel]) YIELD node
            RETURN node.id AS ibn_created_id
            """
            result_ibn = execute_query(create_ibn_query, {"props": ibn_props, "type_label": NodeType.INTERDISCIPLINARY_BRIDGE.value}, tx_type='write')
            if not result_ibn or not result_ibn[0].get("ibn_created_id"):
                 logger.error(f"Failed to create IBN node {ibn_id} in Neo4j.")
                 return None
            
            created_ibn_id = result_ibn[0]["ibn_created_id"]

            # Link IBN to evidence and hypothesis
            for rel_type_enum, source_id, target_id in [
                (EdgeType.IBN_SOURCE_LINK, evidence_node_data['id'], created_ibn_id),
                (EdgeType.IBN_TARGET_LINK, created_ibn_id, hypothesis_node_data['id'])
            ]:
                edge_id = f"edge_{source_id}_{rel_type_enum.value}_{target_id}"
                edge_pydantic = Edge(id=edge_id, source_id=source_id, target_id=target_id, type=rel_type_enum, confidence=0.8)
                edge_props = self._prepare_edge_properties_for_neo4j(edge_pydantic)
                create_rel_query = """
                MATCH (s:Node {id: $source_id}), (t:Node {id: $target_id})
                MERGE (s)-[r:%s {id: $props.id}]->(t) SET r += $props RETURN r.id
                """ % rel_type_enum.value
                execute_query(create_rel_query, {"source_id": source_id, "target_id": target_id, "props": edge_props}, tx_type='write')
            
            logger.info(f"Created IBN {created_ibn_id} between {evidence_node_data['id']} and {hypothesis_node_data['id']}.")
            return created_ibn_id
        except Neo4jError as e:
            logger.error(f"Neo4j error creating IBN {ibn_id}: {e}")
            return None

    async def _create_hyperedges_in_neo4j(
        self, hypothesis_data: Dict[str, Any], related_evidence_data_list: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Creates a hyperedge center node in Neo4j to represent joint influence on a hypothesis.
        
        If the number of related evidence nodes meets the minimum threshold, this method aggregates confidence values, creates a hyperedge center node, and links all member nodes (the hypothesis and its evidence) to the center node with `HAS_MEMBER` relationships.
        
        Args:
            hypothesis_data: Dictionary containing hypothesis node properties.
            related_evidence_data_list: List of dictionaries with evidence node properties.
        
        Returns:
            A list of created hyperedge center node IDs.
        """
        created_hyperedge_ids: List[str] = []
        if len(related_evidence_data_list) < self.min_nodes_for_hyperedge_consideration:
            return created_hyperedge_ids

        # Simplified: Check if all evidence points in the same direction (all supportive or all contradictory)
        # This requires knowing the edge type from evidence to hypothesis, which is not directly in evidence_data.
        # This part needs careful implementation if it's to be accurate.
        # For now, assume this check is simplified or done based on evidence_data["supports_hypothesis"]
        
        # Let's assume for this refactor that this logic is simplified and focuses on creating the structure
        # if the minimum number of evidences is met. A more robust check would query the actual edge types.
        
        hyperedge_center_id = f"hyper_{hypothesis_data['id']}_{random.randint(1000,9999)}"
        hyperedge_node_ids_for_pydantic = {hypothesis_data['id']} | {ev_data['id'] for ev_data in related_evidence_data_list}

        # Simplified confidence for hyperedge
        hypo_conf_emp = hypothesis_data.get("confidence_empirical_support", 0.5) # Use .get for safety
        avg_emp_support = (hypo_conf_emp + sum(ev.get("confidence_empirical_support", 0.5) for ev in related_evidence_data_list)) / (1 + len(related_evidence_data_list))
        
        hyper_confidence = ConfidenceVector(empirical_support=avg_emp_support, theoretical_basis=0.4, methodological_rigor=0.5, consensus_alignment=0.4)
        hyperedge_metadata = HyperedgeMetadata(
            description=f"Joint influence on hypothesis '{hypothesis_data.get('label', 'N/A')[:20]}...'",
            relationship_descriptor="Joint Support/Contradiction (Simulated)",
            layer_id=hypothesis_data.get("metadata_layer_id", self.default_params.initial_layer)
        )
        # Create the Hyperedge Pydantic model for property preparation for the central node
        hyperedge_pydantic_for_center_node = Node( # Treat the hyperedge center as a Node for properties
            id=hyperedge_center_id, label=f"Hyperedge for {hypothesis_data.get('label', 'N/A')[:20]}",
            type=NodeType.HYPEREDGE_CENTER, # A new NodeType to represent the hyperedge construct itself
            confidence=hyper_confidence, # Store aggregated confidence on the center node
            metadata=NodeMetadata( # Store hyperedge-specific metadata here
                description=hyperedge_metadata.description,
                misc_properties={"relationship_descriptor": hyperedge_metadata.relationship_descriptor}
            )
        )
        center_node_props = self._prepare_node_properties_for_neo4j(hyperedge_pydantic_for_center_node)

        try:
            create_center_query = """
            MERGE (hc:Node {id: $props.id}) SET hc += $props
            WITH hc, $type_label AS typeLabel CALL apoc.create.addLabels(hc, [typeLabel]) YIELD node
            RETURN node.id AS hyperedge_center_created_id
            """
            result_center = execute_query(create_center_query, {"props": center_node_props, "type_label": NodeType.HYPEREDGE_CENTER.value}, tx_type='write')
            if not result_center or not result_center[0].get("hyperedge_center_created_id"):
                logger.error(f"Failed to create hyperedge center node {hyperedge_center_id}.")
                return created_hyperedge_ids
            
            created_hyperedge_center_id = result_center[0]["hyperedge_center_created_id"]

            # Link members to the hyperedge center node
            member_ids_to_link = list(hyperedge_node_ids_for_pydantic) # Use the set from Pydantic model
            for member_id in member_ids_to_link:
                edge_id = f"edge_hyper_{created_hyperedge_center_id}_hasmember_{member_id}"
                # Minimal edge properties for HAS_MEMBER, can be expanded
                edge_props = {"id": edge_id} 
                
                link_member_query = """
                MATCH (hc:Node {id: $hyperedge_center_id})
                MATCH (member:Node {id: $member_node_id})
                MERGE (hc)-[r:HAS_MEMBER {id: $props.id}]->(member) SET r += $props RETURN r.id
                """
                execute_query(link_member_query, {
                    "hyperedge_center_id": created_hyperedge_center_id,
                    "member_node_id": member_id,
                    "props": edge_props
                }, tx_type='write')
            
            created_hyperedge_ids.append(created_hyperedge_center_id) # Return ID of the central hyperedge node
            logger.info(f"Created Hyperedge (center node {created_hyperedge_center_id}) for hypothesis {hypothesis_data['id']} and {len(related_evidence_data_list)} evidence nodes.")
        except Neo4jError as e:
            logger.error(f"Neo4j error creating hyperedge for hypothesis {hypothesis_data['id']}: {e}")
        
        return created_hyperedge_ids

    async def _apply_temporal_decay_and_patterns(self):
        """
        Placeholder for applying temporal decay and pattern detection to the graph.
        
        Currently, this method performs no operations.
        """
        logger.debug("Temporal decay and pattern detection (P1.18, P1.25) - placeholder, no action taken.")
        pass

    async def _adapt_graph_topology(self):
        """
        Placeholder for dynamic graph topology adaptation logic.
        
        Currently, this method does not perform any operations.
        """
        logger.debug("Dynamic graph topology adaptation (P1.22) - placeholder, no action taken.")
        pass

    async def execute(
        self, current_session_data: GoTProcessorSessionData # graph: ASRGoTGraph removed
    ) -> StageOutput:
        """
        Executes the evidence integration stage by generating and linking evidence nodes to hypotheses in Neo4j.
        
        This method iterates over provided hypothesis node IDs, selects hypotheses for evaluation, simulates evidence generation, creates evidence nodes and relationships in Neo4j, updates hypothesis confidence, and manages the creation of interdisciplinary bridge nodes (IBNs) and hyperedges as appropriate. It tracks and summarizes the number of created and updated entities, applies placeholder methods for temporal decay and graph adaptation, and returns a StageOutput with execution metrics and context updates.
        
        Args:
            current_session_data: The session data containing accumulated context, including hypothesis node IDs.
        
        Returns:
            A StageOutput summarizing the results of evidence integration, including counts of created evidence nodes, updated hypotheses, IBNs, and hyperedges, along with metrics and context updates.
        """
        self._log_start(current_session_data.session_id)
        hypothesis_data = current_session_data.accumulated_context.get(HypothesisStage.stage_name, {})
        hypothesis_node_ids: List[str] = hypothesis_data.get("hypothesis_node_ids", [])

        if not hypothesis_node_ids:
            logger.warning("No hypothesis IDs found. Skipping evidence stage.")
            return StageOutput(summary="Evidence skipped: No hypotheses.", metrics={},
                               next_stage_context_update={self.stage_name: {"error": "No hypotheses found"}})

        evidence_created_count = 0
        hypotheses_updated_count = 0
        ibns_created_count = 0
        hyperedges_created_count = 0
        
        processed_hypotheses_this_run: Set[str] = set()

        for iteration_num in range(self.max_iterations):
            logger.info(f"Evidence integration iteration {iteration_num + 1}/{self.max_iterations}")
            
            eligible_ids_for_selection = [hid for hid in hypothesis_node_ids if hid not in processed_hypotheses_this_run]
            if not eligible_ids_for_selection:
                logger.info("All hypotheses processed for this stage run or no eligible hypotheses left.")
                break

            selected_hypothesis_data = await self._select_hypothesis_to_evaluate_from_neo4j(eligible_ids_for_selection)
            if not selected_hypothesis_data:
                logger.info("No more eligible hypotheses to evaluate in this iteration.")
                break
            
            current_hypothesis_id = selected_hypothesis_data["id"]
            processed_hypotheses_this_run.add(current_hypothesis_id)

            found_evidence_conceptual_list = await self._execute_hypothesis_plan(selected_hypothesis_data)
            if not found_evidence_conceptual_list:
                logger.debug(f"No new evidence generated for hypothesis '{selected_hypothesis_data.get('label', current_hypothesis_id)}'.")
                continue

            related_evidence_data_for_hyperedge: List[Dict[str,Any]] = []

            for ev_idx, ev_conceptual_data in enumerate(found_evidence_conceptual_list):
                created_evidence_neo4j_data = await self._create_evidence_in_neo4j(
                    selected_hypothesis_data, ev_conceptual_data, iteration_num, ev_idx
                )
                if not created_evidence_neo4j_data:
                    continue
                evidence_created_count += 1
                related_evidence_data_for_hyperedge.append(created_evidence_neo4j_data)

                # Bayesian Update
                # Reconstruct prior confidence from selected_hypothesis_data (fetched from Neo4j)
                prior_confidence_list = selected_hypothesis_data.get('confidence_vector_list', [0.5]*4)
                prior_hypo_confidence_obj = ConfidenceVector(
                    empirical_support=prior_confidence_list[0],
                    theoretical_basis=prior_confidence_list[1],
                    methodological_rigor=prior_confidence_list[2],
                    consensus_alignment=prior_confidence_list[3]
                )
                
                # Determine edge type for update based on evidence support (simplified)
                edge_type_for_update = EdgeType.SUPPORTIVE if ev_conceptual_data["supports_hypothesis"] else EdgeType.CONTRADICTORY

                update_successful = await self._update_hypothesis_confidence_in_neo4j(
                    current_hypothesis_id, prior_hypo_confidence_obj,
                    ev_conceptual_data["strength"], ev_conceptual_data["supports_hypothesis"],
                    ev_conceptual_data["statistical_power"], edge_type_for_update
                )
                if update_successful:
                    hypotheses_updated_count +=1
                    # Refresh hypothesis data if needed for subsequent operations in this loop, e.g. IBN creation
                    # For now, assume selected_hypothesis_data is sufficient for IBN label/tags
                
                # IBN Creation
                # Pass data of the *created* evidence node and the *selected* hypothesis node
                ibn_created_id = await self._create_ibn_in_neo4j(created_evidence_neo4j_data, selected_hypothesis_data)
                if ibn_created_id:
                    ibns_created_count += 1
            
            # Hyperedge Creation (after all evidence for this hypothesis in this iteration)
            if related_evidence_data_for_hyperedge:
                hyperedge_ids = await self._create_hyperedges_in_neo4j(selected_hypothesis_data, related_evidence_data_for_hyperedge)
                hyperedges_created_count += len(hyperedge_ids)

        await self._apply_temporal_decay_and_patterns()
        await self._adapt_graph_topology()

        summary = (f"Evidence integration completed. Iterations: {iteration_num + 1 if self.max_iterations > 0 and hypothesis_node_ids else 0}. "
                   f"Evidence created: {evidence_created_count}. Hypotheses updated: {hypotheses_updated_count}. "
                   f"IBNs created: {ibns_created_count}. Hyperedges created: {hyperedges_created_count}.")
        metrics = {
            "iterations_completed": iteration_num + 1 if self.max_iterations > 0 and hypothesis_node_ids else 0,
            "evidence_nodes_created_in_neo4j": evidence_created_count,
            "hypotheses_updated_in_neo4j": hypotheses_updated_count,
            "ibns_created_in_neo4j": ibns_created_count,
            "hyperedges_created_in_neo4j": hyperedges_created_count,
        }
        context_update = {"evidence_integration_completed": True, "evidence_nodes_added_count": evidence_created_count}
        
        return StageOutput(summary=summary, metrics=metrics, next_stage_context_update={self.stage_name: context_update})
