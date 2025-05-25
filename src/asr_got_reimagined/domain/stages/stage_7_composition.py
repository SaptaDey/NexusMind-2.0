import random
from typing import Optional, Union

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from src.asr_got_reimagined.config import Settings
from src.asr_got_reimagined.domain.models.common_types import GoTProcessorSessionData
from src.asr_got_reimagined.domain.models.graph_elements import (
    Node,
    NodeType,
)
from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph

from .base_stage import BaseStage, StageOutput
from .stage_6_subgraph_extraction import (  # To get subgraph definitions
    ExtractedSubgraph,
    SubgraphExtractionStage,
)


# --- Pydantic models for structured output of Composition Stage ---
class CitationItem(
    BaseModel
):  # P1.6 Vancouver citations (K1.3 implies a specific style)
    id: Union[str, int]  # e.g., "[1]" or "Node-XYZ"
    text: str  # Full citation text formatted in Vancouver style
    source_node_id: Optional[str] = (
        None  # Link back to the graph node if citation is for a node
    )
    url: Optional[str] = None  # If the source is external


class OutputSection(BaseModel):
    title: str
    content: str  # This would ideally be rich text or markdown
    type: str = Field(
        default="generic",
        examples=["summary", "analysis", "findings", "gaps", "interdisciplinary"],
    )
    referenced_subgraph_name: Optional[str] = None
    # Optional: List of node IDs or claims made in this section for traceability (P1.6)
    related_node_ids: list[str] = Field(default_factory=list)
    # P1.6: Annotate claims with node IDs & edge types
    # This could be part of the 'content' or a more structured field.


class ComposedOutput(BaseModel):  # This will be the main "final_composed_answer"
    title: str
    executive_summary: str
    sections: list[OutputSection] = Field(default_factory=list)
    citations: list[CitationItem] = Field(default_factory=list)
    reasoning_trace_appendix_summary: Optional[str] = None  # P1.6
    # P1.6: Numeric node labels (handled by graph serialization if needed)
    # P1.6: Verbatim queries in metadata (handled by node metadata)
    # P1.6: Annotate claims with node IDs & edge types (partially via OutputSection.related_node_ids, content formatting)
    # P1.6: Dimensional reduction/topology metrics for visualization (from graph state, P1.22)
    graph_topology_summary: Optional[str] = None


class CompositionStage(BaseStage):
    stage_name: str = "CompositionStage"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        # K1.3 implies Vancouver citation style from config or a utility
        self.citation_style = "Vancouver"  # Placeholder for P1.6

    async def _generate_executive_summary(
        self,
        # graph: ASRGoTGraph, # Marked as unused by Ruff
        extracted_subgraphs: list[ExtractedSubgraph],
        initial_query: str,
    ) -> str:
        """
        Generates a placeholder executive summary describing the extracted subgraphs for a given query.
        
        Summarizes the number and names of subgraphs identified by the ASR-GoT process in relation to the initial query, and highlights a sample of key subgraphs. Intended as a stand-in for a more sophisticated summary.
        """
        num_subgraphs = len(extracted_subgraphs)
        subgraph_names = [sg.name for sg in extracted_subgraphs]
        summary = (
            f"Executive summary for the analysis of query: '{initial_query}'.\n"
            f"The ASR-GoT process identified {num_subgraphs} key subgraphs of interest: {', '.join(subgraph_names)}. "
            f"These subgraphs highlight various facets of the research topic, including "
            f"{', '.join(random.sample(subgraph_names, min(2, num_subgraphs)) if subgraph_names else ['key findings'])}. "
            f"Further details are provided in the subsequent sections."
            # In a real system, this would synthesize key findings from high-impact nodes or subgraphs.
        )
        logger.debug("Generated placeholder executive summary.")
        return summary

    async def _format_node_as_claim(
        self,
        node: Node,  # graph: ASRGoTGraph, # Marked as unused by Ruff
    ) -> tuple[str, Optional[CitationItem]]:
        """
        Formats a graph node as a claim statement and generates a corresponding citation.
        
        Args:
            node: The graph node to be formatted as a claim.
        
        Returns:
            A tuple containing the formatted claim string (with a citation reference) and the generated CitationItem.
        """
        claim_text = (
            f"Claim based on Node {node.id} ('{node.label}', Type: {node.type.value}): "
        )
        # Further elaborate based on node content/confidence.
        # Example: Append metadata like epistemic status or key findings from its description.
        if node.metadata.description:
            claim_text += node.metadata.description[:100] + "..."  # Snippet

        # P1.6: Vancouver citations (K1.3)
        # Simplified citation generation
        citation_text = f"NexusMind Internal Node. ID: {node.id}. Label: {node.label}. Type: {node.type.value}. Created: {node.created_at.strftime('%Y-%m-%d')}."
        citation = CitationItem(
            id=f"Node-{node.id}", text=citation_text, source_node_id=node.id
        )

        return f"{claim_text} [{citation.id}]", citation

    async def _generate_section_from_subgraph(
        self, graph: ASRGoTGraph, subgraph_def: ExtractedSubgraph
    ) -> tuple[OutputSection, list[CitationItem]]:
        """
        Generates an output section and associated citations for a given extracted subgraph.
        
        Analyzes the subgraph to identify and summarize key nodes (such as hypotheses, evidence, or interdisciplinary bridges) with high confidence or impact. Formats up to three key nodes as claims with citations. If no qualifying nodes are found, adds a placeholder statement. Returns the constructed output section and a list of citations.
        """
        section_title = f"Analysis: {subgraph_def.name.replace('_', ' ').title()}"
        content_parts: list[str] = [
            f"This section discusses findings from the '{subgraph_def.name}' subgraph, which focuses on: {subgraph_def.description}.\n"
        ]
        citations: list[CitationItem] = []
        related_node_ids_for_section: list[str] = list(
            subgraph_def.node_ids
        )  # Start with all nodes in subgraph

        # Highlight a few key nodes from the subgraph (e.g., high confidence/impact)
        key_nodes_in_subgraph: list[Node] = []
        for node_id in subgraph_def.node_ids:
            node = graph.get_node(node_id)
            if (
                node
                and node.type
                in [
                    NodeType.HYPOTHESIS,
                    NodeType.EVIDENCE,
                    NodeType.INTERDISCIPLINARY_BRIDGE,
                ]
                and (
                    node.confidence.average_confidence > 0.6
                    or (node.metadata.impact_score or 0) > 0.6
                )
            ):
                key_nodes_in_subgraph.append(node)

        key_nodes_in_subgraph.sort(
            key=lambda n: (
                -(n.metadata.impact_score or 0),
                -n.confidence.average_confidence,
            )
        )

        for i, node in enumerate(
            key_nodes_in_subgraph[:3]
        ):  # Max 3 key claims per section for this placeholder
            claim_text, citation = await self._format_node_as_claim(node) # Removed graph
            content_parts.append(f"Key Point {i + 1}: {claim_text}")
            if citation:
                citations.append(citation)
            # P1.6: Annotate with edge types (simplified - list connections)
            # incoming_edges = [edge for edge in graph.edges.values() if edge.target_id == node.id and edge.source_id in subgraph_def.node_ids]
            # outgoing_edges = [edge for edge in graph.edges.values() if edge.source_id == node.id and edge.target_id in subgraph_def.node_ids]
            # if incoming_edges: content_parts.append(f"  - Supported/Caused by: {', '.join([f'{e.type.value} from {e.source_id}' for e in incoming_edges[:2]])}")
            # if outgoing_edges: content_parts.append(f"  - Supports/Causes: {', '.join([f'{e.type.value} to {e.target_id}' for e in outgoing_edges[:2]])}")

        if not key_nodes_in_subgraph:
            content_parts.append(
                "No specific high-impact claims identified in this subgraph based on current criteria."
            )

        section = OutputSection(
            title=section_title,
            content="\n".join(content_parts),
            type="analysis_subgraph",
            referenced_subgraph_name=subgraph_def.name,
            related_node_ids=related_node_ids_for_section,
        )
        logger.debug(f"Generated content for section: '{section_title}'.")
        return section, citations

    async def _generate_reasoning_trace_appendix_summary(
        self, session_data: GoTProcessorSessionData
    ) -> str:
        # P1.6: Reasoning Trace appendix. This is a summary for the composed output.
        # The full trace is available in session_data.stage_outputs_trace.
        lines = ["Summary of Reasoning Trace Appendix:"]
        for trace_item in session_data.stage_outputs_trace:
            lines.append(
                f"  Stage {trace_item['stage_number']}. {trace_item['stage_name']}: {trace_item['summary']} ({trace_item.get('duration_ms', 'N/A')}ms)"
            )
        return "\n".join(lines)

    async def execute(
        self, graph: ASRGoTGraph, current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        """
        Assembles the final composed output from extracted subgraphs and session data.
        
        This asynchronous method generates an executive summary, detailed output sections, and citations based on extracted subgraphs from the previous processing stage. If no subgraphs are available, it produces a minimal output. The method also appends a reasoning trace summary and packages all results into a `StageOutput` for downstream consumption.
        
        Args:
            graph: The ASR-GoT graph containing all nodes and edges.
            current_session_data: The current session's data, including accumulated context and the initial query.
        
        Returns:
            A `StageOutput` containing the composed output, summary, metrics, and updated context for the next stage.
        """
        self._log_start(current_session_data.session_id)

        # GoTProcessor now stores the dictionary from next_stage_context_update directly.
        subgraph_extraction_data_from_context = (
            current_session_data.accumulated_context.get(
                SubgraphExtractionStage.stage_name, {}
            )
        )
        extracted_subgraphs_data: list[dict] = (
            subgraph_extraction_data_from_context.get(
                "extracted_subgraphs_definitions", []
            )
        )

        extracted_subgraphs: list[ExtractedSubgraph] = []
        if extracted_subgraphs_data:
            try:
                extracted_subgraphs = [
                    ExtractedSubgraph(**data) for data in extracted_subgraphs_data
                ]
            except ValidationError as e:
                logger.error(f"Error parsing extracted subgraph definitions: {e}")

        initial_query = current_session_data.query

        if not extracted_subgraphs:
            logger.warning(
                "No subgraphs found from SubgraphExtractionStage. Composition will be minimal."
            )
            composed_output_obj = ComposedOutput(
                title=f"NexusMind Analysis (Minimal): {initial_query[:50]}...",
                executive_summary="No specific subgraphs were extracted for detailed composition. The graph may be too sparse or criteria too strict.",
                sections=[],
                citations=[],
                reasoning_trace_appendix_summary=await self._generate_reasoning_trace_appendix_summary(
                    current_session_data
                ),
            )
            return StageOutput(
                summary="Composition complete (minimal output due to no subgraphs).",
                metrics={"sections_generated": 0, "citations_generated": 0},
                next_stage_context_update={
                    self.stage_name: {
                        "composed_output": composed_output_obj.model_dump()
                    }
                },
            )

        all_citations: list[CitationItem] = []
        output_sections: list[OutputSection] = []

        # 1. Generate Executive Summary
        exec_summary = await self._generate_executive_summary(
            extracted_subgraphs, initial_query # Removed graph
        )

        # 2. Generate sections from each subgraph
        for subgraph_def in extracted_subgraphs:
            try:
                section, section_citations = await self._generate_section_from_subgraph(
                    graph, subgraph_def
                )
                output_sections.append(section)
                all_citations.extend(section_citations)
            except Exception as e:
                logger.error(
                    f"Error generating section for subgraph '{subgraph_def.name}': {e}"
                )

        # Deduplicate citations by id (simplified)
        final_citations_map: dict[str, CitationItem] = {}
        for cit in all_citations:
            key = str(cit.id)
            if key not in final_citations_map:
                final_citations_map[key] = cit
        final_citations = list(final_citations_map.values())
        # Re-number citations if they were sequentially numbered (more complex, skipped for now)

        # 3. Generate Reasoning Trace Appendix Summary
        trace_appendix_summary = await self._generate_reasoning_trace_appendix_summary(
            current_session_data
        )

        # P1.6: Output formatting
        composed_output_obj = ComposedOutput(
            title=f"NexusMind Analysis: {initial_query[:50]}...",
            executive_summary=exec_summary,
            sections=output_sections,
            citations=final_citations,
            reasoning_trace_appendix_summary=trace_appendix_summary,
            # graph_topology_summary = "Topology metrics: (P1.22 data would go here)" # Placeholder
        )

        summary = f"Composed final output with {len(output_sections)} sections and {len(final_citations)} citations."
        metrics = {
            "sections_generated": len(output_sections),
            "citations_generated": len(final_citations),
            "subgraphs_processed": len(extracted_subgraphs),
        }
        # The main output for the GoTProcessor (and potentially MCP) is the composed_output itself.
        context_update = {"final_composed_output": composed_output_obj.model_dump()}

        output = StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
        self._log_end(current_session_data.session_id, output)
        return output
