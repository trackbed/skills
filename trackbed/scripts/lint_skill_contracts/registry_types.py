"""Static type of the decoded synced-contracts registry.

This module imports nothing from the package, so every module that receives
the registry can import it without an import cycle.
"""

from __future__ import annotations

from typing import Any, TypedDict


class Registry(TypedDict, total=False):
    """Top-level synced-contracts.yaml sections that the linter reads.

    ``cli.load_registry`` casts decoded JSON to this type without validating
    it, so every field must stay ``object`` or ``Any``. A typed section is
    ``object``, and its check narrows it before use: ``text_contracts`` becomes
    ``TextContract`` records in ``checks.basic``.
    """

    text_contracts: object
    contract_schema: Any
    base_diff_scope: Any
    ui_relevance_contracts: Any
    ordered_heading_contracts: Any
    required_file_contracts: Any
    marker_implies_manifest: Any
    source_provenance: Any
    epilogue_forbidden: Any
    hooks_json: Any
    readme_prose: Any
    readme_skill_sync: Any
    readme_agent_sync: Any
    readme_hook_sync: Any
    skill_contract_coverage: Any
    component_catalog: Any
    routing_distinctness: Any
    invocation_graph: Any
    mechanical: Any
