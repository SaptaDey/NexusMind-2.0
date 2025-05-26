from pathlib import Path
from typing import Any, Optional, Type # Added Type for settings_cls hint
import sys # For type checking PydanticBaseSettingsSource

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource

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
    initial_confidence: list[float] = Field(default=[0.9, 0.9, 0.9, 0.9])
    initial_layer: str = Field(default="root_layer")
    default_decomposition_dimensions: list[DecompositionDimension] = Field(
        default_factory=list
    )
    dimension_confidence: list[float] = Field(default=[0.8, 0.8, 0.8, 0.8])
    hypotheses_per_dimension: HypothesisParams = Field(
        default_factory=HypothesisParams, alias="hypotheses_per_dimension"
    )
    hypothesis_confidence: list[float] = Field(default=[0.5, 0.5, 0.5, 0.5])
    default_disciplinary_tags: list[str] = Field(default_factory=list)
    default_plan_types: list[str] = Field(default_factory=list)
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
    layers: dict[str, LayerDefinition] = Field(default_factory=dict)


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
    keywords: list[str] = Field(default_factory=list)
    description: Optional[str] = None


# --- Main Application Settings Model ---
class AppSettings(BaseModel):
    name: str = Field(default="NexusMind")
    version: str = Field(default="0.1.0")
    host: str = Field(default="0.0.0.0")
    port: int = Field(
        default=8000
    )  # Can be overridden by APP__PORT environment variable
    log_level: str = Field(default="INFO")
    # debug: bool = False


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    asr_got: ASRGoTConfig = Field(default_factory=ASRGoTConfig)
    mcp_settings: MCPSettings = Field(default_factory=MCPSettings)
    claude_api: Optional[ClaudeAPIConfig] = None  # Optional section
    knowledge_domains: list[KnowledgeDomain] = Field(default_factory=list)

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
        settings_cls: Type[BaseSettings], # Re-added settings_cls
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        
        # Define your custom source function
        # It needs to match the expected signature, though its args might not be used if it's simple
        # For pydantic-settings v2, it's typically (settings_cls: Type[BaseSettings]) -> Dict[str, Any]
        # However, since yaml_config is already loaded, we can wrap it simply.
        
        """
        Customizes the order of settings sources for Pydantic, inserting a YAML-based source.
        
        Inserts a settings source that loads from a pre-loaded YAML configuration dictionary after dotenv settings, allowing settings to be loaded in the following order: initialization, environment variables, dotenv files, YAML file, and file secrets.
        
        Args:
            settings_cls: The Pydantic settings class being configured.
        
        Returns:
            A tuple of settings sources in the desired order for Pydantic to use.
        """
        class YamlConfigSettingsSource(PydanticBaseSettingsSource):
            def __init__(self, settings_cls: Type[BaseSettings]):
                """
                Initializes the YAML settings source with a pre-loaded configuration dictionary.
                
                Args:
                    settings_cls: The Pydantic BaseSettings subclass for which this source is used.
                """
                super().__init__(settings_cls)
                self._yaml_config = yaml_config # Use pre-loaded config

            def get_field_value(self, field: Field, field_name: str) -> tuple[Any, str] | None:
                # This method is required by PydanticBaseSettingsSource if you want to customize field-level loading.
                # For a simple dict source, often just providing __call__ is enough.
                # Let's try with __call__ first, if it fails, we might need this.
                return None # Not using field-level logic from YAML here

            def __call__(self) -> dict[str, Any]:
                return self._yaml_config
            
            def prepare_field_value(self, field_name: str, field: Field, value: Any, value_is_complex: bool) -> Any:
                 # This method is called by Pydantic to prepare the field value.
                 # We don't need custom preparation for YAML simple values.
                return value


        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls), # Pass settings_cls here
            file_secret_settings,
        )


# Global settings instance, to be imported by other modules
settings = Settings()

# Example of how to access settings:
# from src.asr_got_reimagined.config import settings
# print(settings.app.name)
# print(settings.asr_got.default_parameters.initial_confidence)
