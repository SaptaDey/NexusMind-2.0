import time
import uuid
from typing import Any, Optional, Dict
import json
from datetime import datetime
from enum import Enum

from loguru import logger

from src.asr_got_reimagined.domain.models.common_types import (
    ComposedOutput,
    GoTProcessorSessionData,
    ConfidenceVector, # Keep if used by _prepare_properties_for_neo4j, otherwise remove if helper is removed
)
# ASRGoTGraph and related Pydantic models (Node, Edge, etc.) from graph_state are no longer needed here
# as GoTProcessor will not interact with the graph structure directly.
# However, _prepare_properties_for_neo4j *might* still be used by a stage if it was not fully refactored.
# For this task, we assume _prepare_properties_for_neo4j is also being removed from GoTProcessor.
# If any Pydantic models like Node, Edge were used by it, their imports would go too.
# For now, keeping ConfidenceVector as it's from common_types.
# Let's assume Node, Edge etc. from graph_state are removed.
# from src.asr_got_reimagined.domain.models.graph_state import (
#     ASRGoTGraph,
#     Node,
#     Edge,
#     Hyperedge,
#     NodeMetadata,
#     EdgeMetadata,
#     HyperedgeMetadata,
# )
from src.asr_got_reimagined.domain.stages.base_stage import BaseStage, StageOutput
from src.asr_got_reimagined.domain.services.neo4j_utils import execute_query, Neo4jError # This is still needed if any stage uses it directly, or if processor has fallback.
                                                                                       # Given stages are Neo4j native, they use it. Processor itself won't after this refactor.


class GoTProcessor:
    def __init__(self, settings):
        """
        Initializes the GoTProcessor with the specified settings.
        
        Args:
            settings: Configuration parameters for the processor instance.
        """
        self.settings = settings
        logger.info("Initializing GoTProcessor")

    # _prepare_properties_for_neo4j helper method is removed as per instructions.
    # Individual stages are now responsible for their own Neo4j property preparation if needed,
    # or this specific helper (if it was generic enough) would be in a utils module.

    def _initialize_stages(self) -> list[BaseStage]:
        """
        Creates and returns the ordered list of all processing stage instances for the ASR-GoT pipeline.
        
        Returns:
            A list of eight initialized stage objects, each representing a distinct step in the query processing pipeline. Logs a warning if the number of stages is not exactly eight.
        """
        from src.asr_got_reimagined.domain.stages import (
            CompositionStage,
            DecompositionStage,
            EvidenceStage,
            HypothesisStage,
            InitializationStage,
            PruningMergingStage,
            ReflectionStage,
            SubgraphExtractionStage,
        )

        # All stages are now real implementations
        stages_to_load: list[type[BaseStage]] = [
            InitializationStage,
            DecompositionStage,
            HypothesisStage,
            EvidenceStage,
            PruningMergingStage,
            SubgraphExtractionStage,
            CompositionStage,
            ReflectionStage,
        ]

        initialized_stages = [stage_cls(self.settings) for stage_cls in stages_to_load]

        if len(initialized_stages) != 8:
            logger.warning(
                f"Expected 8 stages, but only {len(initialized_stages)} were initialized. Check _initialize_stages."
            )

        return initialized_stages

    async def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        operational_params: Optional[dict[str, Any]] = None,
        initial_context: Optional[dict[str, Any]] = None,
    ) -> GoTProcessorSessionData:
        """
        Processes a natural language query through the ASR-GoT pipeline, executing all processing stages in sequence and managing session state, context, and error handling.
        
        Initializes or continues a session, stores the query and any provided context or operational parameters, and orchestrates the execution of all pipeline stages. Logs detailed input and output information for each stage, including special handling and early halting for initialization errors. After all stages or upon halt, extracts the final answer and confidence vector from the appropriate stage outputs, compiles a trace of stage execution, and returns the session data with results.
        
        Args:
            query: The natural language query to process.
            session_id: Optional identifier for continuing or managing a session.
            operational_params: Optional parameters to control processing behavior.
            initial_context: Optional initial context to seed the processing.
        
        Returns:
            GoTProcessorSessionData containing the final answer, confidence vector, accumulated context, and a trace of stage outputs.
        """
        from src.asr_got_reimagined.domain.stages import (
            CompositionStage,
            DecompositionStage,  # Added for logging
            EvidenceStage,  # Added for logging
            HypothesisStage,  # Added for logging
            InitializationStage,
            ReflectionStage,
        )

        start_total_time = time.time()
        logger.info(f"Starting NexusMind query processing for: '{query[:100]}...'")

        # Initialize or retrieve session data
        current_session_data = GoTProcessorSessionData(
            session_id=session_id or f"session-{uuid.uuid4()}", query=query
        )

        # ASRGoTGraph instantiation removed.
        # The graph_state attribute in GoTProcessorSessionData will also be removed.
        # If any metadata was stored in graph_state.graph_metadata, 
        # it needs a new home if still required (e.g., directly in accumulated_context).
        # For this task, assuming such metadata is either not critical or handled by stages.
        # current_session_data.accumulated_context["graph_metadata"] = {
        #     "query": query,
        #     "session_id": current_session_data.session_id
        # } # Example if we wanted to keep this info

        # Process initial context
        if initial_context:
            current_session_data.accumulated_context["initial_context"] = (
                initial_context
            )

        # Process operational parameters
        op_params = operational_params or {}
        current_session_data.accumulated_context["operational_params"] = op_params

        # Execute stages in sequence
        stages = self._initialize_stages()
        logger.info(f"Initialized {len(stages)} processing stages")

        for i, stage in enumerate(stages):
            stage_start_time = time.time()
            stage_name = stage.__class__.__name__
            logger.info(f"Executing stage {i + 1}/{len(stages)}: {stage_name}")

            # --- BEGIN ADDED LOGGING (Before Stage Execution) ---
            logger.debug(f"--- Preparing for Stage: {stage_name} ---")
            if isinstance(stage, InitializationStage):
                logger.debug(
                    f"Input for {stage_name}: Query='{query[:100]}...', InitialContextKeys={list(initial_context.keys()) if initial_context else []}, OpParamsKeys={list(op_params.keys())}"
                )
            elif isinstance(stage, DecompositionStage):
                init_output = current_session_data.accumulated_context.get(
                    InitializationStage.stage_name, {}
                )
                logger.debug(
                    f"Input for {stage_name} (from {InitializationStage.stage_name}): root_node_id='{init_output.get('root_node_id')}', initial_disciplinary_tags='{init_output.get('initial_disciplinary_tags')}'"
                )
            elif isinstance(stage, HypothesisStage):
                decomp_output = current_session_data.accumulated_context.get(
                    DecompositionStage.stage_name, {}
                )
                logger.debug(
                    f"Input for {stage_name} (from {DecompositionStage.stage_name}): decomposition_results keys='{list(decomp_output.keys()) if decomp_output else 'No output found'}'"
                )
            elif isinstance(stage, EvidenceStage):
                hypo_output = current_session_data.accumulated_context.get(
                    HypothesisStage.stage_name, {}
                )
                logger.debug(
                    f"Input for {stage_name} (from {HypothesisStage.stage_name}): hypothesis_results keys='{list(hypo_output.keys()) if hypo_output else 'No output found'}'"
                )
            else:
                # General case: log keys of accumulated_context or a summary
                context_keys = list(current_session_data.accumulated_context.keys())
                logger.debug(
                    f"Accumulated context keys before {stage_name}: {context_keys}"
                )
                # Optionally, log specific known general inputs like current graph node/edge count if relevant for all
                # logger.debug(f"Graph state for {stage_name}: Nodes={len(current_session_data.graph_state.nodes)}, Edges={len(current_session_data.graph_state.edges)}")
            logger.debug(f"--- End Preparing for Stage: {stage_name} ---")
            # --- END ADDED LOGGING ---

            try:  # Execute the stage
                # Graph argument removed from stage execution call
                stage_result = await stage.execute(
                    current_session_data=current_session_data,
                )

                # --- BEGIN ADDED LOGGING (After Stage Execution) ---
                logger.debug(f"--- Output from Stage: {stage_name} ---")
                if isinstance(stage_result, StageOutput):
                    if (
                        hasattr(stage_result, "next_stage_context_update")
                        and stage_result.next_stage_context_update
                    ):
                        logger.debug(
                            f"Raw output (next_stage_context_update): {stage_result.next_stage_context_update}"
                        )
                    else:
                        logger.debug(
                            f"Stage {stage_name} produced StageOutput but 'next_stage_context_update' is missing or empty."
                        )

                    if hasattr(stage_result, "summary") and stage_result.summary:
                        logger.debug(f"Summary: {stage_result.summary}")
                    if hasattr(stage_result, "metrics") and stage_result.metrics:
                        logger.debug(f"Metrics: {stage_result.metrics}")
                    if (
                        stage_result.error_message
                    ):  # Also log error if any, though handled later
                        logger.debug(
                            f"Error reported by stage: {stage_result.error_message}"
                        )
                elif stage_result is not None:
                    logger.debug(f"Raw output (non-StageOutput): {stage_result}")
                else:
                    logger.debug("Stage execution returned None.")
                logger.debug(f"--- End Output from Stage: {stage_name} ---")
                # --- END ADDED LOGGING ---

                # Update session data with stage results
                if (
                    stage_result
                    and hasattr(stage_result, "next_stage_context_update")
                    and stage_result.next_stage_context_update
                ):
                    # Merge the context update from the stage into the accumulated_context.
                    # Stages should structure their next_stage_context_update as a dictionary,
                    # typically like { ActualStageNameConstant: {output_key: output_value} }.
                    current_session_data.accumulated_context.update(
                        stage_result.next_stage_context_update
                    )
                elif stage_result:
                    # Fallback or warning if next_stage_context_update is missing, though it implies an issue with the stage itself.
                    logger.warning(
                        f"Stage {stage_name} produced a result but it was missing 'next_stage_context_update' or it was empty. No context updated by this stage."
                    )

                # Record stage execution in trace
                stage_duration_ms = int((time.time() - stage_start_time) * 1000)
                trace_entry = {
                    "stage_number": i + 1,
                    "stage_name": stage_name,
                    "duration_ms": stage_duration_ms,
                    "summary": f"Completed {stage_name}",
                }
                current_session_data.stage_outputs_trace.append(trace_entry)

                logger.info(
                    f"Completed stage {i + 1}: {stage_name} in {stage_duration_ms}ms"
                )

                # ADD new error checking logic for InitializationStage:
                if isinstance(stage, InitializationStage):
                    initialization_output = (
                        current_session_data.accumulated_context.get(
                            InitializationStage.stage_name, {}
                        )
                    )

                    halt_message = None
                    error_reason_summary = None

                    # Priority 1: Explicit error message from StageOutput object
                    if (
                        isinstance(stage_result, StageOutput)
                        and stage_result.error_message
                    ):
                        error_reason_summary = stage_result.error_message
                        halt_message = f"Processing halted: Initialization failed with error: {error_reason_summary}"
                        logger.error(
                            f"Critical error from InitializationStage (StageOutput): {error_reason_summary}. Halting further processing."
                        )

                    # Priority 2: "error" key in the stage's output within accumulated_context (if not already caught by P1)
                    elif initialization_output.get("error"):
                        error_reason_summary = str(
                            initialization_output.get("error")
                        )  # Ensure string
                        halt_message = f"Processing halted: Initialization failed with error from context: {error_reason_summary}"
                        logger.error(
                            f"Critical error found in InitializationStage context: {error_reason_summary}. Halting further processing."
                        )

                    # Priority 3: Missing 'root_node_id' (if no other errors were caught by P1 or P2)
                    elif not initialization_output.get("root_node_id"):
                        error_reason_summary = (
                            "InitializationStage did not provide root_node_id."
                        )
                        halt_message = "Processing halted: Graph initialization failed (missing root_node_id)."
                        logger.error(
                            f"{error_reason_summary} Halting further processing."
                        )

                    if halt_message:  # This block executes if any of the above conditions set halt_message
                        current_session_data.final_answer = halt_message
                        current_session_data.final_confidence_vector = [
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                        ]  # Indicate failure
                        # Append a specific trace entry for the halt
                        current_session_data.stage_outputs_trace.append(
                            {
                                "stage_number": i
                                + 1,  # Reflects the stage that caused the halt
                                "stage_name": stage_name,  # Name of the InitializationStage
                                "error": "Halting due to critical error in InitializationStage.",  # Standardized error type
                                "summary": error_reason_summary,  # Specific reason for halting from P1, P2, or P3
                            }
                        )
                        break  # Exit the loop of stages
            except Exception as e:
                logger.error(f"Error in stage {i + 1} ({stage_name}): {e!s}")
                trace_entry = {
                    "stage_number": i + 1,
                    "stage_name": stage_name,
                    "error": str(e),
                    "summary": f"Error in {stage_name}: {e!s}",
                }
                current_session_data.stage_outputs_trace.append(trace_entry)
                # Continue to next stage despite errors

        # Extract final answer from composition stage
        composition_stage_output_key = CompositionStage.stage_name
        composition_stage_result = current_session_data.accumulated_context.get(
            composition_stage_output_key
        )
        final_composed_output_dict = None
        if composition_stage_result and isinstance(
            composition_stage_result, StageOutput
        ):
            final_composed_output_dict = (
                composition_stage_result.next_stage_context_update.get(
                    "final_composed_output"
                )
            )
        elif isinstance(
            composition_stage_result, dict
        ):  # Should not happen if stages return StageOutput
            final_composed_output_dict = composition_stage_result.get(
                "final_composed_output"
            )

        if final_composed_output_dict:
            try:
                final_output_obj = ComposedOutput(**final_composed_output_dict)
                current_session_data.final_answer = f"{final_output_obj.executive_summary}\n\n(Full report details generated)"
            except Exception as e:
                logger.error(
                    f"Could not parse final_composed_output from CompositionStage: {e}"
                )
                current_session_data.final_answer = (
                    "Error during final composition of answer."
                )
        else:
            current_session_data.final_answer = (
                "Composition stage did not produce a final output structure."
            )

        # Get final confidence from ReflectionStage's output
        reflection_stage_output_key = ReflectionStage.stage_name
        reflection_stage_result = current_session_data.accumulated_context.get(
            reflection_stage_output_key
        )
        current_session_data.final_confidence_vector = [0.1, 0.1, 0.1, 0.1]  # Default
        if reflection_stage_result and isinstance(reflection_stage_result, StageOutput):
            current_session_data.final_confidence_vector = (
                reflection_stage_result.next_stage_context_update.get(
                    "final_confidence_vector_from_reflection",
                    [0.1, 0.1, 0.1, 0.1],  # Low default if not found
                )
            )
        elif isinstance(reflection_stage_result, dict):  # Should not happen
            current_session_data.final_confidence_vector = reflection_stage_result.get(
                "final_confidence_vector_from_reflection",
                [0.1, 0.1, 0.1, 0.1],  # Low default if not found
            )

        total_execution_time_ms = int((time.time() - start_total_time) * 1000)
        logger.info(
            f"NexusMind query processing completed for session {current_session_data.session_id} in {total_execution_time_ms}ms."
        )

        # --- Final Graph Persistence Logic Removed ---
        # The graph persistence logic that was here (iterating graph.nodes, graph.edges, etc.)
        # and using self._prepare_properties_for_neo4j has been removed.
        # Each stage is now responsible for its own Neo4j interactions.

        return current_session_data

    async def shutdown_resources(self):
        """
        Performs cleanup operations when shutting down the GoTProcessor.
        
        Currently, this method logs the shutdown event. No active resource management is performed, but this method serves as a placeholder for future cleanup tasks such as closing database connections or releasing external resources.
        """
        logger.info("Shutting down GoTProcessor resources")
        # Example: Close Neo4j driver if it were managed here, though it's managed in neo4j_utils
        # from src.asr_got_reimagined.domain.services.neo4j_utils import close_neo4j_driver
        # close_neo4j_driver() # This would be appropriate if driver lifecycle tied to processor
        return
