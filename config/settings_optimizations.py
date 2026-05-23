"""Claude-code probe mocks and shortcuts for local optimization."""

from pydantic import BaseModel


class RequestOptimizationsMixin(BaseModel):
    enable_network_probe_mock: bool = True
    enable_title_generation_skip: bool = True
    enable_suggestion_mode_skip: bool = True
    enable_filepath_extraction_mock: bool = True
