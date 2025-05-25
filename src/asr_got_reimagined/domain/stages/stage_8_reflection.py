from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from src.asr_got_reimagined.config import Settings
from src.asr_got_reimagined.domain.models.common import ConfidenceVector
from src.asr_got_reimagined.domain.models.graph_elements import (
    NodeType,
)
from src.asr_got_reimagined.domain.models.graph_state import ASRGoTGraph
from src.asr_got_reimagined.domain.models.common_types import GoTProcessorSessionData

from .base_stage import BaseStage, StageOutput
from .stage_7_composition import (  # To access composed output
    ComposedOutput,
    CompositionStage,
)


# Structure for audit check results
class AuditCheckResult(BaseModel):
    check_name: str
    status: str = Field(
        default="NOT_RUN", examples=["PASS", "WARNING", "FAIL", "NOT_APPLICABLE"]
    )
    message: str
    details: Optional[Dict[str, Any]] = None


class ReflectionStage(BaseStage):
    stage_name: str = "ReflectionStage"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        # Thresholds for reflection checks (could be in settings.yaml)
        self.high_confidence_threshold = 0.7
        self.high_impact_threshold = 0.7
        self.min_falsifiable_hypothesis_ratio = 0.6
        self.max_high_severity_bias_nodes = 0
        self.min_powered_evidence_ratio = 0.5
        # P1.7 checklist items
        self.audit_checklist_items = [
            "high_confidence_impact_coverage",
            "bias_flags_assessment",
            "knowledge_gaps_addressed",
            "hypothesis_falsifiability",
            "causal_claim_validity",  # Placeholder
            "temporal_consistency",  # Placeholder
            "statistical_rigor_of_evidence",
            "collaboration_attributions_check",  # Placeholder
        ]

    async def _check_high_confidence_impact_coverage(
        self, graph: ASRGoTGraph
    ) -> AuditCheckResult:
        """P1.7: Check coverage of high-confidence/high-impact nodes/dimensions."""
        high_conf_nodes = 0
        high_impact_nodes = 0
        total_relevant_nodes = 0  # e.g., Hypotheses, Evidence, IBNs

        for node in graph.nodes.values():
            if node.type in [
                NodeType.HYPOTHESIS,
                NodeType.EVIDENCE,
                NodeType.INTERDISCIPLINARY_BRIDGE,
            ]:
                total_relevant_nodes += 1
                if node.confidence.average_confidence >= self.high_confidence_threshold:
                    high_conf_nodes += 1
                if (node.metadata.impact_score or 0) >= self.high_impact_threshold:
                    high_impact_nodes += 1

        if total_relevant_nodes == 0:
            return AuditCheckResult(
                check_name="high_confidence_impact_coverage",
                status="NOT_APPLICABLE",
                message="No relevant nodes (hypotheses/evidence) to assess coverage.",
            )

        conf_coverage = high_conf_nodes / total_relevant_nodes
        impact_coverage = high_impact_nodes / total_relevant_nodes
        message = f"Confidence coverage: {conf_coverage:.2%} ({high_conf_nodes}/{total_relevant_nodes}). Impact coverage: {impact_coverage:.2%} ({high_impact_nodes}/{total_relevant_nodes})."

        # Simple pass/fail based on some threshold
        if conf_coverage >= 0.3 and impact_coverage >= 0.2:
            return AuditCheckResult(
                check_name="high_confidence_impact_coverage",
                status="PASS",
                message=message,
            )
        elif conf_coverage >= 0.1 or impact_coverage >= 0.1:
            return AuditCheckResult(
                check_name="high_confidence_impact_coverage",
                status="WARNING",
                message=f"Limited coverage. {message}",
            )
        else:
            return AuditCheckResult(
                check_name="high_confidence_impact_coverage",
                status="FAIL",
                message=f"Poor coverage. {message}",
            )

    async def _check_bias_flags_assessment(
        self, graph: ASRGoTGraph
    ) -> AuditCheckResult:
        """P1.7: Check bias flags (P1.17)."""
        flagged_nodes_count = 0
        high_severity_bias_count = 0
        for node in graph.nodes.values():
            if node.metadata.bias_flags:
                flagged_nodes_count += 1
                for flag in node.metadata.bias_flags:
                    if flag.severity == "high":
                        high_severity_bias_count += 1

        message = f"Found {flagged_nodes_count} nodes with bias flags. {high_severity_bias_count} have high severity."
        if high_severity_bias_count > self.max_high_severity_bias_nodes:
            return AuditCheckResult(
                check_name="bias_flags_assessment", status="FAIL", message=message
            )
        elif flagged_nodes_count > 0:
            return AuditCheckResult(
                check_name="bias_flags_assessment",
                status="WARNING",
                message=f"Potential biases flagged. {message}",
            )
        else:
            return AuditCheckResult(
                check_name="bias_flags_assessment",
                status="PASS",
                message="No bias flags detected or all are low/medium severity.",
            )

    async def _check_knowledge_gaps_addressed(
        self, graph: ASRGoTGraph, composed_output: Optional[ComposedOutput]
    ) -> AuditCheckResult:
        """P1.7: Check if knowledge gaps identified (P1.15) are addressed in output."""
        gap_nodes_present = any(
            node.metadata.is_knowledge_gap for node in graph.nodes.values()
        )
        gaps_mentioned_in_output = False
        if composed_output:
            for section in composed_output.sections:
                if "gap" in section.title.lower() or (
                    section.type and "gap" in section.type.lower()
                ):
                    gaps_mentioned_in_output = True
                    break

        if not gap_nodes_present:
            return AuditCheckResult(
                check_name="knowledge_gaps_addressed",
                status="NOT_APPLICABLE",
                message="No explicit knowledge gap nodes identified in the graph.",
            )
        if gap_nodes_present and gaps_mentioned_in_output:
            return AuditCheckResult(
                check_name="knowledge_gaps_addressed",
                status="PASS",
                message="Identified knowledge gaps appear to be addressed in the composed output.",
            )
        else:  # Gaps present but not mentioned
            return AuditCheckResult(
                check_name="knowledge_gaps_addressed",
                status="WARNING",
                message="Knowledge gaps were identified in the graph but might not be explicitly discussed in the output.",
            )

    async def _check_hypothesis_falsifiability(
        self, graph: ASRGoTGraph
    ) -> AuditCheckResult:
        """P1.7: Check falsifiability criteria (P1.16) for hypotheses."""
        hypothesis_nodes = [
            n for n in graph.nodes.values() if n.type == NodeType.HYPOTHESIS
        ]
        if not hypothesis_nodes:
            return AuditCheckResult(
                check_name="hypothesis_falsifiability",
                status="NOT_APPLICABLE",
                message="No hypothesis nodes to assess.",
            )

        falsifiable_count = sum(
            1
            for n in hypothesis_nodes
            if n.metadata.falsification_criteria
            and n.metadata.falsification_criteria.description
        )
        ratio = falsifiable_count / len(hypothesis_nodes)
        message = f"{falsifiable_count}/{len(hypothesis_nodes)} ({ratio:.2%}) hypotheses have falsifiability criteria."

        if ratio >= self.min_falsifiable_hypothesis_ratio:
            return AuditCheckResult(
                check_name="hypothesis_falsifiability", status="PASS", message=message
            )
        elif ratio > 0:
            return AuditCheckResult(
                check_name="hypothesis_falsifiability",
                status="WARNING",
                message=f"Suboptimal falsifiability. {message}",
            )
        else:
            return AuditCheckResult(
                check_name="hypothesis_falsifiability",
                status="FAIL",
                message=f"Poor falsifiability. {message}",
            )

    async def _check_statistical_rigor(self, graph: ASRGoTGraph) -> AuditCheckResult:
        """P1.7: Check statistical rigor of evidence (P1.26)."""
        evidence_nodes = [
            n for n in graph.nodes.values() if n.type == NodeType.EVIDENCE
        ]
        if not evidence_nodes:
            return AuditCheckResult(
                check_name="statistical_rigor_of_evidence",
                status="NOT_APPLICABLE",
                message="No evidence nodes to assess for statistical rigor.",
            )

        adequately_powered_count = 0
        for node in evidence_nodes:
            if (
                node.metadata.statistical_power
                and node.metadata.statistical_power.value >= 0.7
            ):  # Example threshold for "adequate"
                adequately_powered_count += 1

        ratio = adequately_powered_count / len(evidence_nodes)
        message = f"{adequately_powered_count}/{len(evidence_nodes)} ({ratio:.2%}) evidence nodes meet statistical power criteria (>=0.7)."

        if ratio >= self.min_powered_evidence_ratio:
            return AuditCheckResult(
                check_name="statistical_rigor_of_evidence",
                status="PASS",
                message=message,
            )
        else:
            return AuditCheckResult(
                check_name="statistical_rigor_of_evidence",
                status="WARNING",
                message=f"Limited statistical rigor in evidence. {message}",
            )

    # Placeholder checks for P1.7 items not yet deeply implemented in prior stages
    async def _check_causal_claim_validity(
        self, graph: ASRGoTGraph
    ) -> AuditCheckResult:  # P1.24
        return AuditCheckResult(
            check_name="causal_claim_validity",
            status="NOT_RUN",
            message="Causal claim validity check not fully implemented.",
        )

    async def _check_temporal_consistency(
        self, graph: ASRGoTGraph
    ) -> AuditCheckResult:  # P1.18, P1.25
        return AuditCheckResult(
            check_name="temporal_consistency",
            status="NOT_RUN",
            message="Temporal consistency check not fully implemented.",
        )

    async def _check_collaboration_attributions(
        self, graph: ASRGoTGraph
    ) -> AuditCheckResult:  # P1.29
        return AuditCheckResult(
            check_name="collaboration_attributions_check",
            status="NOT_RUN",
            message="Attribution check not fully implemented.",
        )

    async def _calculate_final_confidence(
        self, audit_results: List[AuditCheckResult], graph: ASRGoTGraph
    ) -> ConfidenceVector:
        """
        Calculates a final overall confidence vector based on audit results and graph state.
        This is a simplified heuristic.
        """
        # Start with a baseline (e.g., average confidence of key nodes or neutral)
        # For now, let's use a neutral base.
        final_conf = ConfidenceVector(
            empirical_support=0.5,
            theoretical_basis=0.5,
            methodological_rigor=0.5,
            consensus_alignment=0.5,
        )

        # Adjust based on audit checks
        # Example: Methodological rigor influenced by falsifiability and bias checks
        falsifiability_check = next(
            (r for r in audit_results if r.check_name == "hypothesis_falsifiability"),
            None,
        )
        bias_check = next(
            (r for r in audit_results if r.check_name == "bias_flags_assessment"), None
        )

        if falsifiability_check and falsifiability_check.status == "PASS":
            final_conf.methodological_rigor += 0.2
        elif falsifiability_check and falsifiability_check.status == "WARNING":
            final_conf.methodological_rigor += 0.05
        elif falsifiability_check and falsifiability_check.status == "FAIL":
            final_conf.methodological_rigor -= 0.2

        if bias_check and bias_check.status == "PASS":
            final_conf.methodological_rigor += 0.1
        elif bias_check and bias_check.status == "FAIL":
            final_conf.methodological_rigor -= 0.15

        # Empirical support influenced by statistical rigor
        stat_rigor_check = next(
            (
                r
                for r in audit_results
                if r.check_name == "statistical_rigor_of_evidence"
            ),
            None,
        )
        if stat_rigor_check and stat_rigor_check.status == "PASS":
            final_conf.empirical_support += 0.2
        elif stat_rigor_check and stat_rigor_check.status == "WARNING":
            final_conf.empirical_support -= 0.1

        # Clamp all values
        final_conf.empirical_support = max(0.0, min(1.0, final_conf.empirical_support))
        final_conf.theoretical_basis = max(
            0.0, min(1.0, final_conf.theoretical_basis)
        )  # Not strongly adjusted yet
        final_conf.methodological_rigor = max(
            0.0, min(1.0, final_conf.methodological_rigor)
        )
        final_conf.consensus_alignment = max(
            0.0, min(1.0, final_conf.consensus_alignment)
        )  # Not strongly adjusted yet

        logger.info(f"Calculated final confidence vector: {final_conf.model_dump()}")
        return final_conf

    async def execute(
        self, graph: ASRGoTGraph, current_session_data: GoTProcessorSessionData
    ) -> StageOutput:
        self._log_start(current_session_data.session_id)

        composition_stage_output = current_session_data.accumulated_context.get(
            CompositionStage.stage_name, {}
        )
        composed_output_dict = composition_stage_output.get("final_composed_output")
        composed_output_obj: Optional[ComposedOutput] = None
        if composed_output_dict:
            try:
                composed_output_obj = ComposedOutput(**composed_output_dict)
            except ValidationError as e:
                logger.warning(f"Could not parse ComposedOutput for reflection: {e}")
            except Exception as e:
                logger.error(f"Unexpected error parsing ComposedOutput: {e}")

        audit_results: List[AuditCheckResult] = []

        # Perform P1.7 audit checks
        try:
            audit_results.append(await self._check_high_confidence_impact_coverage(graph))
        except Exception as e:
            logger.error(f"Error in high_confidence_impact_coverage check: {e}")
        try:
            audit_results.append(await self._check_bias_flags_assessment(graph))
        except Exception as e:
            logger.error(f"Error in bias_flags_assessment check: {e}")
        try:
            audit_results.append(
                await self._check_knowledge_gaps_addressed(graph, composed_output_obj)
            )
        except Exception as e:
            logger.error(f"Error in knowledge_gaps_addressed check: {e}")
        try:
            audit_results.append(await self._check_hypothesis_falsifiability(graph))
        except Exception as e:
            logger.error(f"Error in hypothesis_falsifiability check: {e}")
        try:
            audit_results.append(await self._check_statistical_rigor(graph))
        except Exception as e:
            logger.error(f"Error in statistical_rigor_of_evidence check: {e}")
        try:
            audit_results.append(
                await self._check_causal_claim_validity(graph)
            )  # Placeholder
        except Exception as e:
            logger.error(f"Error in causal_claim_validity check: {e}")
        try:
            audit_results.append(
                await self._check_temporal_consistency(graph)
            )  # Placeholder
        except Exception as e:
            logger.error(f"Error in temporal_consistency check: {e}")
        try:
            audit_results.append(
                await self._check_collaboration_attributions(graph)
            )  # Placeholder
        except Exception as e:
            logger.error(f"Error in collaboration_attributions_check: {e}")

        # Filter out NOT_RUN checks if desired for summary
        active_audit_results = [r for r in audit_results if r.status != "NOT_RUN"]

        # Calculate final overall confidence (P1.5 style vector for the whole process)
        try:
            final_confidence_vector = await self._calculate_final_confidence(
                active_audit_results, graph
            )
        except Exception as e:
            logger.error(f"Error calculating final confidence vector: {e}")
            final_confidence_vector = ConfidenceVector(
                empirical_support=0.0,
                theoretical_basis=0.0,
                methodological_rigor=0.0,
                consensus_alignment=0.0,
            )

        summary = (
            f"Reflection stage complete. Performed {len(active_audit_results)} active audit checks. "
            f"Final overall confidence assessed. "
            f"PASS: {sum(1 for r in active_audit_results if r.status == 'PASS')}, "
            f"WARNING: {sum(1 for r in active_audit_results if r.status == 'WARNING')}, "
            f"FAIL: {sum(1 for r in active_audit_results if r.status == 'FAIL')}."
        )
        metrics = {
            "audit_checks_performed_count": len(active_audit_results),
            "audit_pass_count": sum(
                1 for r in active_audit_results if r.status == "PASS"
            ),
            "audit_warning_count": sum(
                1 for r in active_audit_results if r.status == "WARNING"
            ),
            "audit_fail_count": sum(
                1 for r in active_audit_results if r.status == "FAIL"
            ),
            "final_confidence_empirical": final_confidence_vector.empirical_support,
            "final_confidence_theoretical": final_confidence_vector.theoretical_basis,
            "final_confidence_methodological": final_confidence_vector.methodological_rigor,
            "final_confidence_consensus": final_confidence_vector.consensus_alignment,
        }
        # This stage primarily updates the session's final confidence.
        context_update = {
            "final_confidence_vector_from_reflection": final_confidence_vector.to_list(),
            "audit_check_results": [res.model_dump() for res in audit_results],
        }

        output = StageOutput(
            summary=summary,
            metrics=metrics,
            next_stage_context_update={self.stage_name: context_update},
        )
        self._log_end(current_session_data.session_id, output)
        return output
