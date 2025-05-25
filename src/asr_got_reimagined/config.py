from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load the YAML configuration file
config_file_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
yaml_config = {}
if config_file_path.exists():
    with open(config_file_path) as f:
        yaml_config = yaml.safe_load(f)


# --- Models for NexusMind Default Parameters ---
class HypothesisParams(BaseModel):
    min_hypotheses: int = Field(default=2, alias="min")
    max_hypotheses: int = Field(default=4, alias="max")


class DecompositionDimension(BaseModel):
    label: str
    description: str


class ASRGoTDefaultParams(BaseModel):
    initial_confidence: List[float] = Field(default=[0.9, 0.9, 0.9, 0.9])
    initial_layer: str = Field(default="root_layer")
    default_decomposition_dimensions: List[DecompositionDimension] = Field(
        default_factory=list
    )
    dimension_confidence: List[float] = Field(default=[0.8, 0.8, 0.8, 0.8])
    hypotheses_per_dimension: HypothesisParams = Field(
        default_factory=HypothesisParams, alias="hypotheses_per_dimension"
    )
    hypothesis_confidence: List[float] = Field(default=[0.5, 0.5, 0.5, 0.5])
    default_disciplinary_tags: List[str] = Field(default_factory=list)
    default_plan_types: List[str] = Field(default_factory=list)
    evidence_max_iterations: int = Field(default=5)
    pruning_confidence_threshold: float = Field(default=0.2)
    pruning_impact_threshold: float = Field(default=0.3)
    merging_semantic_overlap_threshold: float = Field(default=0.8)
    subgraph_min_confidence_threshold: float = Field(default=0.6)
    subgraph_min_impact_threshold: float = Field(default=0.5)
    # temporal_recency_days: Optional[int] = None # Example if used


class LayerDefinition(BaseModel):
    description: str


class ASRGoTConfig(BaseModel):
    default_parameters: ASRGoTDefaultParams = Field(default_factory=ASRGoTDefaultParams)
    layers: Dict[str, LayerDefinition] = Field(default_factory=dict)


# --- Models for MCP Settings ---
class MCPSettings(BaseModel):
    protocol_version: str = Field(default="2024-11-05")
    server_name: str = Field(default="NexusMind MCP Server")
    server_version: str = Field(default="0.1.0")
    vendor_name: str = Field(default="AI Research Group")
    # display_name: Optional[str] = None
    # description: Optional[str] = None


# --- Models for optional Claude API direct integration ---
class ClaudeAPIConfig(BaseModel):
    api_key: Optional[str] = (
        None  # Example: "env_var:CLAUDE_API_KEY" or actual key for dev
    )
    default_model: str = Field(default="claude-3-opus-20240229")
    timeout_seconds: int = Field(default=120)
    max_retries: int = Field(default=2)


class KnowledgeDomain(BaseModel):
    name: str
    keywords: List[str] = Field(default_factory=list)
    description: Optional[str] = None


# --- Main Application Settings Model ---
class AppSettings(BaseModel):
    name: str = Field(default="NexusMind")
    version: str = Field(default="0.1.0")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)  # Can be overridden by APP__PORT environment variable
    log_level: str = Field(default="INFO")
    # debug: bool = False


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    asr_got: ASRGoTConfig = Field(default_factory=ASRGoTConfig)
    mcp_settings: MCPSettings = Field(default_factory=MCPSettings)
    claude_api: Optional[ClaudeAPIConfig] = None  # Optional section
    knowledge_domains: List[KnowledgeDomain] = Field(default_factory=list)
    
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # e.g., APP__HOST to override app.host
        # Add other sources if needed, e.g., .env file
        # env_file = '.env',
        # env_file_encoding = 'utf-8',
        extra="ignore",  # Ignore extra fields from YAML if any
    )
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        def yaml_source(*args) -> dict[str, Any]:
            # Return the already loaded yaml_config directly
            return yaml_config

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_source,
            file_secret_settings,
        )


# Global settings instance, to be imported by other modules
settings = Settings()

# Example of how to access settings:
# from src.asr_got_reimagined.config import settings
# print(settings.app.name)
# print(settings.asr_got.default_parameters.initial_confidence)
