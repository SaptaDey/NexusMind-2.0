from typing import List, Optional

from loguru import logger

from src.asr_got_reimagined.domain.models.common import CertaintyScore, ConfidenceVector
from src.asr_got_reimagined.domain.models.graph_elements import EdgeType, StatisticalPower


def bayesian_update_confidence(
    prior_confidence: ConfidenceVector,
    evidence_strength: CertaintyScore,  # A single score representing how strong this piece of evidence is
    evidence_supports_hypothesis: bool,  # True if supportive, False if contradictory
    statistical_power: Optional[StatisticalPower] = None,  # P1.26
    edge_type: Optional[EdgeType] = None,  # P1.10, P1.24, P1.25 for context
) -> ConfidenceVector:
    """
    Simplified Bayesian-inspired update for a ConfidenceVector.
    P1.14: Apply Bayesian updates... considering evidence reliability (P1.26 power) and edge type.

    Args:
        prior_confidence: The current confidence vector of the hypothesis.
        evidence_strength: A score (0-1) indicating the strength/reliability of the new evidence.
        evidence_supports_hypothesis: Boolean indicating if evidence supports or contradicts.
        statistical_power: Statistical power of the evidence.
        edge_type: Type of edge connecting evidence to hypothesis, can influence update.

    Returns:
        A new ConfidenceVector with updated values.
    """
    # This is a highly simplified placeholder. True Bayesian updates involve likelihoods, priors, etc.
    # and updating probability distributions, not just scores.
    # P1.14 mentions "probability distributions" for confidence components.

    # For now, we'll do a weighted adjustment.
    # Weight factor considers evidence strength and statistical power.
    power_multiplier = (
        statistical_power.value if statistical_power else 0.5
    )  # Default if no power info
    weight = evidence_strength * power_multiplier

    # Edge type influence (P1.14) - very simplified
    edge_type_factor = 1.0
    if edge_type:
        if edge_type in [EdgeType.CAUSES, EdgeType.SUPPORTIVE]:
            edge_type_factor = 1.1
        elif edge_type == EdgeType.CORRELATIVE:
            edge_type_factor = 0.9
        elif edge_type == EdgeType.CONTRADICTORY:
            # This case should be handled by evidence_supports_hypothesis=False
            pass

    weight *= edge_type_factor
    weight = max(0, min(weight, 1.0))  # Clamp weight

    new_confidence_values = prior_confidence.to_list()
    target_value = 1.0 if evidence_supports_hypothesis else 0.0

    # Adjust each component of the confidence vector
    # A more sophisticated approach would update each dimension based on how the evidence relates to it.
    # E.g., empirical evidence primarily boosts empirical_support.
    # This simple version boosts/reduces all components slightly.
    for i in range(len(new_confidence_values)):
        current_val = new_confidence_values[i]
        adjustment = weight * (target_value - current_val)
        new_confidence_values[i] = max(0.0, min(1.0, current_val + adjustment))

    logger.debug(
        f"Bayesian update: Prior {prior_confidence.to_list()}, Evidence Strength {evidence_strength}, "
        f"Supports: {evidence_supports_hypothesis}, Power: {power_multiplier}, Edge: {edge_type} "
        f"-> New {new_confidence_values}"
    )
    return ConfidenceVector.from_list(new_confidence_values)


def calculate_information_gain(
    prior_distribution: List[float], posterior_distribution: List[float]
) -> float:
    """
    Placeholder for calculating information gain (e.g., KL divergence reduction). P1.27.
    This would compare the uncertainty before and after evidence.
    """
    # Simplified: sum of absolute changes in probability for now
    if len(prior_distribution) != len(posterior_distribution):
        return 0.0  # Or raise error

    gain = sum(
        abs(p - q) for p, q in zip(prior_distribution, posterior_distribution)
    ) / len(prior_distribution)
    logger.debug(f"Calculated simplified info gain: {gain}")
    return gain
