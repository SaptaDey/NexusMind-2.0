from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Load the YAML configuration file
config_file_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
yaml_config = {}
if config_file_path.exists():
    with open(config_file_path) as f:
        yaml_config = yaml.safe_load(f)

# --- Models for NexusMind Default Parameters ---
class HypothesisParams(BaseModel):
    min_hypotheses: int = 2
    max_hypotheses: int = 4

class DecompositionDimension(BaseModel):
    label: str
    description: str

class ASRGoTDefaultParams(BaseModel):
    initial_confidence: List[float] = [0.9, 0.9, 0.9, 0.9]
    initial_layer: str = "root_layer"
    default_decomposition_dimensions: List[DecompositionDimension] = []
    dimension_confidence: List[float] = [0.8, 0.8, 0.8, 0.8]
    hypotheses_per_dimension: HypothesisParams = HypothesisParams()
    hypothesis_confidence: List[float] = [0.5, 0.5, 0.5, 0.5]
    default_disciplinary_tags: List[str] = []
    default_plan_types: List[str] = []
    evidence_max_iterations: int = 5
    pruning_confidence_threshold: float = 0.2
    pruning_impact_threshold: float = 0.3
    merging_semantic_overlap_threshold: float = 0.8
    subgraph_min_confidence_threshold: float = 0.6
    subgraph_min_impact_threshold: float = 0.5

class LayerDefinition(BaseModel):
    description: str

class ASRGoTConfig(BaseModel):
    default_parameters: ASRGoTDefaultParams = ASRGoTDefaultParams()
    layers: Dict[str, LayerDefinition] = {}

# --- Models for MCP Settings ---
class MCPSettings(BaseModel):
    protocol_version: str = "2024-11-05"
    server_name: str = "NexusMind MCP Server"
    server_version: str = "0.1.0"
    vendor_name: str = "AI Research Group"

# --- Main Application Settings Model ---
class AppSettings(BaseModel):
    name: str = "NexusMind"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

class Settings(BaseModel):
    app: AppSettings = AppSettings()
    asr_got: ASRGoTConfig = ASRGoTConfig()
    mcp_settings: MCPSettings = MCPSettings()
    knowledge_domains: List[Any] = []

# Create settings instance with values from YAML
settings = Settings(**yaml_config)
