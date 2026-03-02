#!/usr/bin/env python3
"""
DocLean Schema Diff Engine — structured API change detection.

Compares two DocLeanSpec objects and produces typed diffs with
breaking-change classification and semver severity.
"""

from dataclasses import dataclass, field
from typing import Optional
from core.formats.doclean import DocLeanSpec, Endpoint, Param, ResponseField, ErrorSchema


# ── Change Types ─────────────────────────────────────────────────────

@dataclass
class Change:
    """A single detected change between two specs."""
    category: str          # endpoint_added, endpoint_removed, param_added, param_removed,
                           # param_type_changed, response_field_added, response_field_removed,
                           # error_added, error_removed, description_changed
    breaking: bool
    endpoint: str          # "METHOD /path"
    detail: str            # human-readable description
    old_value: Optional[str] = None
    new_value: Optional[str] = None


@dataclass
class DiffResult:
    """Complete diff between two specs."""
    added_endpoints: list[str] = field(default_factory=list)
    removed_endpoints: list[str] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)

    @property
    def breaking_changes(self) -> list[Change]:
        return [c for c in self.changes if c.breaking]

    @property
    def non_breaking_changes(self) -> list[Change]:
        return [c for c in self.changes if not c.breaking]

    @property
    def has_breaking(self) -> bool:
        return bool(self.breaking_changes)


@dataclass
class CompatibilityResult:
    compatible: bool
    breaking_changes: list[Change]
    severity: str  # MAJOR / MINOR / PATCH


# ── Helpers ──────────────────────────────────────────────────────────

def _ep_key(ep: Endpoint) -> str:
    return f"{ep.method.upper()} {ep.path}"


def _all_params(ep: Endpoint) -> dict[str, Param]:
    params = {}
    for p in ep.required_params:
        params[p.name] = p
    for p in ep.optional_params:
        params[p.name] = p
    for p in ep.request_body:
        params[p.name] = p
    return params


def _response_fields(ep: Endpoint) -> dict[str, ResponseField]:
    fields = {}
    for rs in (ep.response_schemas or []):
        for f in rs.fields:
            fields[f"{rs.status_code}.{f.name}"] = f
    return fields


def _error_codes(ep: Endpoint) -> dict[str, ErrorSchema]:
    codes = {}
    for e in (ep.error_schemas or []):
        codes[e.code] = e
    return codes


def _is_required(param: Param, ep: Endpoint) -> bool:
    return param.required or param in ep.required_params


# ── Core Diff ────────────────────────────────────────────────────────

def diff_specs(old: DocLeanSpec, new: DocLeanSpec) -> DiffResult:
    """Diff two DocLeanSpec objects. Returns a DiffResult with all changes."""
    result = DiffResult()

    old_eps = {_ep_key(ep): ep for ep in old.endpoints}
    new_eps = {_ep_key(ep): ep for ep in new.endpoints}

    # Added / removed endpoints
    for key in sorted(set(new_eps) - set(old_eps)):
        result.added_endpoints.append(key)
        result.changes.append(Change(
            category="endpoint_added", breaking=False,
            endpoint=key, detail=f"Added endpoint: {key}",
        ))

    for key in sorted(set(old_eps) - set(new_eps)):
        result.removed_endpoints.append(key)
        result.changes.append(Change(
            category="endpoint_removed", breaking=True,
            endpoint=key, detail=f"Removed endpoint: {key}",
        ))

    # Changed endpoints
    for key in sorted(set(old_eps) & set(new_eps)):
        old_ep = old_eps[key]
        new_ep = new_eps[key]
        _diff_endpoint(old_ep, new_ep, key, result)

    return result


def _diff_endpoint(old_ep: Endpoint, new_ep: Endpoint, key: str, result: DiffResult):
    # --- Params ---
    old_params = _all_params(old_ep)
    new_params = _all_params(new_ep)

    for name in sorted(set(new_params) - set(old_params)):
        p = new_params[name]
        req = _is_required(p, new_ep)
        result.changes.append(Change(
            category="param_added", breaking=req,
            endpoint=key,
            detail=f"{key}: added {'required' if req else 'optional'} param `{name}` ({p.type})",
            new_value=f"{name}: {p.type}",
        ))

    for name in sorted(set(old_params) - set(new_params)):
        p = old_params[name]
        result.changes.append(Change(
            category="param_removed", breaking=False,
            endpoint=key,
            detail=f"{key}: removed param `{name}` ({p.type})",
            old_value=f"{name}: {p.type}",
        ))

    for name in sorted(set(old_params) & set(new_params)):
        op, np = old_params[name], new_params[name]
        if op.type != np.type:
            result.changes.append(Change(
                category="param_type_changed", breaking=True,
                endpoint=key,
                detail=f"{key}: param `{name}` type changed {op.type} → {np.type}",
                old_value=op.type, new_value=np.type,
            ))

    # --- Response fields ---
    old_fields = _response_fields(old_ep)
    new_fields = _response_fields(new_ep)

    for fkey in sorted(set(new_fields) - set(old_fields)):
        result.changes.append(Change(
            category="response_field_added", breaking=False,
            endpoint=key,
            detail=f"{key}: added response field `{fkey}`",
            new_value=fkey,
        ))

    for fkey in sorted(set(old_fields) - set(new_fields)):
        result.changes.append(Change(
            category="response_field_removed", breaking=True,
            endpoint=key,
            detail=f"{key}: removed response field `{fkey}`",
            old_value=fkey,
        ))

    # --- Error codes ---
    old_errors = _error_codes(old_ep)
    new_errors = _error_codes(new_ep)

    for code in sorted(set(new_errors) - set(old_errors)):
        result.changes.append(Change(
            category="error_added", breaking=False,
            endpoint=key,
            detail=f"{key}: added error code {code}",
            new_value=code,
        ))

    for code in sorted(set(old_errors) - set(new_errors)):
        result.changes.append(Change(
            category="error_removed", breaking=True,
            endpoint=key,
            detail=f"{key}: removed error code {code}",
            old_value=code,
        ))

    # --- Description ---
    if (old_ep.summary or "") != (new_ep.summary or ""):
        result.changes.append(Change(
            category="description_changed", breaking=False,
            endpoint=key,
            detail=f"{key}: description changed",
            old_value=old_ep.summary, new_value=new_ep.summary,
        ))


# ── Compatibility Checker ────────────────────────────────────────────

def check_compatibility(old: DocLeanSpec, new: DocLeanSpec) -> CompatibilityResult:
    """Check backward compatibility between two spec versions."""
    diff = diff_specs(old, new)
    breaking = diff.breaking_changes

    if breaking:
        severity = "MAJOR"
    elif diff.added_endpoints or any(
        c.category in ("param_added", "response_field_added", "error_added", "endpoint_added")
        for c in diff.changes
    ):
        severity = "MINOR"
    elif diff.changes:
        severity = "PATCH"
    else:
        severity = "PATCH"  # no changes

    return CompatibilityResult(
        compatible=not breaking,
        breaking_changes=breaking,
        severity=severity,
    )


# ── Changelog Generator ─────────────────────────────────────────────

def generate_changelog(old: DocLeanSpec, new: DocLeanSpec, version: str = "0.0.0") -> str:
    """Generate a markdown changelog from two specs."""
    diff = diff_specs(old, new)
    lines = [f"## v{version}", ""]

    breaking = diff.breaking_changes
    non_breaking = diff.non_breaking_changes

    if breaking:
        lines.append("### Breaking Changes")
        for c in breaking:
            lines.append(f"- {c.detail}")
        lines.append("")

    if non_breaking:
        lines.append("### New Features")
        for c in non_breaking:
            lines.append(f"- {c.detail}")
        lines.append("")

    if not breaking and not non_breaking:
        lines.append("No changes detected.")
        lines.append("")

    return "\n".join(lines)
