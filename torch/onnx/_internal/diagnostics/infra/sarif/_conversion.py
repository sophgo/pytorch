# DO NOT EDIT! This file was generated by jschema_to_python version 0.0.1.dev29,
# with extension for dataclasses and type annotation.

from __future__ import annotations

import dataclasses
from typing import List, Optional

from torch.onnx._internal.diagnostics.infra.sarif import (
    _artifact_location,
    _invocation,
    _property_bag,
    _tool,
)


@dataclasses.dataclass
class Conversion(object):
    """Describes how a converter transformed the output of a static analysis tool from the analysis tool's native output format into the SARIF format."""

    tool: _tool.Tool = dataclasses.field(metadata={"schema_property_name": "tool"})
    analysis_tool_log_files: Optional[
        List[_artifact_location.ArtifactLocation]
    ] = dataclasses.field(
        default=None, metadata={"schema_property_name": "analysisToolLogFiles"}
    )
    invocation: Optional[_invocation.Invocation] = dataclasses.field(
        default=None, metadata={"schema_property_name": "invocation"}
    )
    properties: Optional[_property_bag.PropertyBag] = dataclasses.field(
        default=None, metadata={"schema_property_name": "properties"}
    )


# flake8: noqa
