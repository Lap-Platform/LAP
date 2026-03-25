#!/usr/bin/env python3
"""
LAP CLI -- Lean API Platform command-line tool.

Compile, inspect, and convert LAP API specifications.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path so `lap.*` imports work when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lap import __version__

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    console = None


# ── Security helpers ─────────────────────────────────────────────────

_ANSI_ESCAPE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_CTRL_CHARS  = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')

def _sanitize(s: str) -> str:
    """Strip ANSI escapes and control characters from server-supplied strings."""
    return _CTRL_CHARS.sub('', _ANSI_ESCAPE.sub('', s))

def _validate_search_response(result):
    """Validate registry response shape before field access."""
    if not isinstance(result, dict):
        error("Unexpected response format from registry.")
    results = result.get("results", [])
    if not isinstance(results, list):
        error("Registry returned malformed results.")
    for r in results:
        if not isinstance(r, dict):
            error("Registry returned malformed result entry.")
    if not isinstance(result.get("total", 0), int):
        result["total"] = len(results)
    if not isinstance(result.get("offset", 0), int):
        result["offset"] = 0


# ── Helpers ──────────────────────────────────────────────────────────

def info(msg):
    if HAS_RICH:
        console.print(f"[bold green]{msg}[/]")
    else:
        print(msg)

def warn(msg):
    if HAS_RICH:
        console.print(f"[bold yellow][WARN][/] {msg}")
    else:
        print(f"[WARN] {msg}")

def error(msg):
    if HAS_RICH:
        console.print(f"[bold red][ERR][/] {msg}")
    else:
        print(f"[ERR] {msg}")
    sys.exit(1)

def _print_stat(label, tier, tokens, width, pct=None, style=None):
    """Print a token stat row. label is the left section header (first row only)."""
    pct_part = f"   -{pct}%" if pct is not None else ""
    num_part = f"{tokens:>{width},}"
    if HAS_RICH and style:
        console.print(f"  {label:<9}[{style}]{tier:<11}{num_part}{pct_part}[/]")
    elif HAS_RICH:
        console.print(f"  {label:<9}{tier:<11}{num_part}{pct_part}")
    else:
        print(f"  {label:<9}{tier:<11}{num_part}{pct_part}")

def heading(msg):
    if HAS_RICH:
        console.print(Panel(msg, style="bold cyan", box=box.ROUNDED))
    else:
        print(f"\n{'='*60}\n  {msg}\n{'='*60}")


@contextmanager
def _spinner(msg):
    if HAS_RICH:
        with console.status(f"[bold cyan]{msg}[/]"):
            yield
    else:
        print(msg)
        yield


def _resolve_ai(args, ai_attr="ai", layer_attr="layer"):
    """Resolve whether to use AI enhancement.

    Returns 2 (AI) or 1 (no AI).
    - --ai flag: force AI enhancement
    - --no-ai flag: skip AI
    - --layer (deprecated): mapped to 1 or 2
    - Default: no AI (Layer 1). Use --ai to opt in.
    """
    ai = getattr(args, ai_attr, None)
    if ai is True:
        return 2
    if ai is False:
        return 1
    layer = getattr(args, layer_attr, None)
    if layer is not None:
        warn("--layer is deprecated, use --ai or --no-ai")
        return layer
    return 1


def _collect_spec_files(directory):
    """Collect spec files from a directory, excluding known oversized specs."""
    spec_files = sorted(
        glob.glob(str(Path(directory) / "*.yaml")) +
        glob.glob(str(Path(directory) / "*.yml")) +
        glob.glob(str(Path(directory) / "*.json"))
    )
    return [f for f in spec_files if "stripe-full" not in f]


# ── Commands ─────────────────────────────────────────────────────────

def _render_lap(result_obj, lean):
    """Render compiled result to LAP text. Handles single spec or list (protobuf)."""
    if isinstance(result_obj, list):
        return "\n---\n\n".join(s.to_lap(lean=lean) for s in result_obj)
    return result_obj.to_lap(lean=lean)


def cmd_compile(args):
    """Compile any API spec to LAP format (auto-detects format)."""
    from lap.core.compilers import compile as compile_spec

    spec_p = Path(args.spec)
    if not spec_p.exists():
        error(f"File/directory not found: {args.spec}")

    fmt = getattr(args, "format", None)
    try:
        result_obj = compile_spec(str(spec_p), format=fmt)
    except ValueError as e:
        error(str(e))

    result = _render_lap(result_obj, lean=args.lean)

    # Protobuf directories return a list
    if isinstance(result_obj, list):
        total_eps = sum(len(s.endpoints) for s in result_obj)
        label = f"{len(result_obj)} specs, {total_eps} endpoints"
    else:
        label = f"{len(result_obj.endpoints)} endpoints"

    # --stdout: print to stdout (for piping)
    if args.stdout:
        print(result)
        return

    from lap.core.utils import count_tokens

    # Determine output path: -o overrides, otherwise derive from input name
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = spec_p.parent / f"{spec_p.stem}.lap"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result, encoding='utf-8')

    # Auto-save the other tier alongside
    other = _render_lap(result_obj, lean=not args.lean)

    stem = out_path.stem.removesuffix(".lean").removesuffix(".standard")
    if args.lean:
        other_path = out_path.parent / f"{stem}.standard.lap"
    else:
        other_path = out_path.parent / f"{stem}.lean.lap"
    other_path.write_text(other, encoding='utf-8')

    # Stats with savings percentages
    SPEC_EXTS = {".yaml", ".yml", ".json", ".proto", ".graphql", ".smithy"}
    if spec_p.is_dir():
        original_text = "\n".join(
            f.read_text(encoding='utf-8')
            for f in sorted(spec_p.rglob("*"))
            if f.is_file() and f.suffix in SPEC_EXTS
        )
    else:
        original_text = spec_p.read_text(encoding='utf-8')
    original_tokens = count_tokens(original_text)
    primary_tokens = count_tokens(result)
    other_tokens = count_tokens(other)
    standard_tokens = other_tokens if args.lean else primary_tokens
    lean_tokens = primary_tokens if args.lean else other_tokens
    std_pct = int((1 - standard_tokens / original_tokens) * 100) if original_tokens else 0
    lean_pct = int((1 - lean_tokens / original_tokens) * 100) if original_tokens else 0

    info(f"Compiled {spec_p.name} -- {label}")
    print()

    w = max(len(f"{t:,}") for t in [original_tokens, standard_tokens, lean_tokens])
    _print_stat("Tokens", "Original", original_tokens, w)
    _print_stat("", "Standard", standard_tokens, w, std_pct, style="green")
    _print_stat("", "Lean", lean_tokens, w, lean_pct, style="bold green")
    print()

    if args.lean:
        std_path, lean_path = other_path, out_path
    else:
        std_path, lean_path = out_path, other_path
    if HAS_RICH:
        console.print(f"  Output   [green]Standard   {std_path.resolve()}[/]")
        console.print(f"           [bold green]Lean       {lean_path.resolve()}[/]")
    else:
        print(f"  Output   Standard   {std_path.resolve()}")
        print(f"           Lean       {lean_path.resolve()}")
    print()

    print(f"  Next: lapsh skill {spec_p.name}")
    print(f"        lapsh publish {spec_p.name} --provider your-domain.com")



def cmd_benchmark_all(args):
    """Benchmark all specs in a directory."""
    from lap.core.compilers.openapi import compile_openapi
    from lap.core.utils import count_tokens as count

    specs_dir = Path(args.directory)
    if not specs_dir.is_dir():
        error(f"Not a directory: {args.directory}")

    spec_files = _collect_spec_files(args.directory)

    if not spec_files:
        error(f"No spec files found in {args.directory}")

    heading(f"Multi-API Benchmark ({len(spec_files)} specs)")

    if HAS_RICH:
        table = Table(title="LAP Compression Results", box=box.SIMPLE_HEAVY)
        table.add_column("API", style="cyan", min_width=18)
        table.add_column("Endpoints", justify="right")
        table.add_column("OpenAPI", justify="right")
        table.add_column("LAP", justify="right", style="green")
        table.add_column("Lean", justify="right", style="bold green")
        table.add_column("vs OpenAPI", justify="right", style="yellow")
        table.add_column("vs OpenAPI (Lean)", justify="right", style="bold yellow")

        totals = {"oa": 0, "dl": 0, "ln": 0}
        for spec_path in spec_files:
            name = Path(spec_path).stem
            raw = Path(spec_path).read_text(encoding='utf-8')
            ds = compile_openapi(spec_path)
            dl = ds.to_lap(lean=False)
            ln = ds.to_lap(lean=True)
            oa_t = count(raw)
            dl_t = count(dl)
            ln_t = count(ln)
            totals["oa"] += oa_t; totals["dl"] += dl_t; totals["ln"] += ln_t
            table.add_row(
                name, str(len(ds.endpoints)),
                f"{oa_t:,}", f"{dl_t:,}", f"{ln_t:,}",
                f"{oa_t/dl_t:.1f}x" if dl_t else "∞",
                f"{oa_t/ln_t:.1f}x" if ln_t else "∞",
            )

        t = totals
        table.add_section()
        table.add_row(
            "[bold]TOTAL[/]", "",
            f"[bold]{t['oa']:,}[/]", f"[bold]{t['dl']:,}[/]", f"[bold]{t['ln']:,}[/]",
            f"[bold]{t['oa']/t['dl']:.1f}x[/]" if t['dl'] else "∞",
            f"[bold]{t['oa']/t['ln']:.1f}x[/]" if t['ln'] else "∞",
        )
        console.print(table)
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "benchmarks"))
        from benchmark_all import run_all
        run_all()


def cmd_inspect(args):
    """Parse and inspect a LAP file."""
    from lap.core.parser import parse_lap

    path = Path(args.file)
    if not path.exists():
        error(f"File not found: {args.file}")

    text = path.read_text(encoding='utf-8')
    spec = parse_lap(text)

    if args.endpoint:
        # Filter to a specific endpoint
        parts = args.endpoint.split(None, 1)
        method = parts[0].lower() if parts else ""
        ep_path = parts[1] if len(parts) > 1 else ""
        matches = [e for e in spec.endpoints if e.method == method and e.path == ep_path]
        if not matches:
            error(f"Endpoint not found: {args.endpoint}")
        endpoints = matches
    else:
        endpoints = spec.endpoints

    if HAS_RICH:
        console.print(Panel(
            f"[bold]{spec.api_name}[/] v{spec.version}\n"
            f"Base: {spec.base_url}\n"
            f"Auth: {spec.auth_scheme}\n"
            f"Endpoints: {len(spec.endpoints)}",
            title="LAP Spec", box=box.ROUNDED
        ))

        for ep in endpoints:
            title = f"[bold cyan]{ep.method.upper()} {ep.path}[/]"
            if ep.summary:
                title += f"  [dim]{ep.summary}[/]"
            console.print(f"\n{title}")

            if ep.required_params:
                console.print("  [yellow]Required:[/]")
                for p in ep.required_params:
                    desc = f" [dim]# {p.description}[/]" if p.description else ""
                    console.print(f"    {p.name}: [green]{p.type}[/]{desc}")

            opt = ep.optional_params + [p for p in ep.request_body if not p.required]
            if opt:
                console.print("  [blue]Optional:[/]")
                for p in opt:
                    console.print(f"    {p.name}: [green]{p.type}[/]")

            if ep.response_schemas:
                for rs in ep.response_schemas:
                    n = len(rs.fields)
                    console.print(f"  [green]-> {rs.status_code}[/] {rs.description or ''} ({n} fields)")

            if ep.error_schemas:
                codes = ", ".join(e.code for e in ep.error_schemas)
                console.print(f"  [red]Errors:[/] {codes}")
    else:
        print(f"\n{spec.api_name} v{spec.version}")
        print(f"Base: {spec.base_url}")
        print(f"Auth: {spec.auth_scheme}")
        print(f"Endpoints: {len(spec.endpoints)}\n")
        for ep in endpoints:
            print(f"  {ep.method.upper()} {ep.path}  {ep.summary or ''}")
            for p in ep.required_params:
                print(f"    [req] {p.name}: {p.type}")
            for p in ep.optional_params:
                print(f"    [opt] {p.name}: {p.type}")


def cmd_convert(args):
    """Convert LAP back to OpenAPI YAML."""
    from lap.core.converter import convert_file

    path = Path(args.file)
    if not path.exists():
        error(f"File not found: {args.file}")

    if args.output:
        convert_file(str(path), args.output)
        info(f"Converted {path.name} -> {args.output} (OpenAPI 3.0)")
    else:
        result = convert_file(str(path))
        print(result)


def cmd_login(args):
    """Authenticate with the LAP registry via GitHub OAuth."""
    from lap.cli.auth import (
        api_request, save_credentials, load_credentials,
        poll_sse_stream, get_registry_url,
    )
    import webbrowser

    creds = load_credentials()
    if creds:
        info(f"Already logged in as {creds['username']}. Run 'lapsh logout' first to switch accounts.")
        return

    print(f"Authenticating with {get_registry_url()}...")

    # Create CLI session (pass optional token name)
    body = {}
    if getattr(args, "token_name", None):
        body["name"] = args.token_name
    result = api_request("POST", "/auth/cli/session", body=body if body else None)
    session_id = result["session_id"]
    stream_key = result["stream_key"]
    auth_url = result["auth_url"]

    # Open browser
    print(f"Opening browser for GitHub authorization...")
    webbrowser.open(auth_url)
    print("Waiting for authentication (press Ctrl+C to cancel)...")

    # Poll SSE stream
    token, username = poll_sse_stream(session_id, stream_key)
    save_credentials(token, username)
    info(f"Logged in as {username}")


def cmd_logout(args):
    """Log out and revoke the current API token."""
    from lap.cli.auth import get_token, clear_credentials, api_request

    token = get_token()
    if not token:
        info("Not logged in.")
        return

    # Revoke token on server
    try:
        api_request("DELETE", "/auth/cli/token", token=token)
    except SystemExit:
        pass  # Server error is OK -- still clear local creds

    clear_credentials()
    info("Logged out.")


def cmd_whoami(args):
    """Show the currently authenticated user."""
    from lap.cli.auth import get_token, api_request

    token = get_token()
    if not token:
        print("Not logged in. Run 'lapsh login' to authenticate.")
        return

    result = api_request("GET", "/auth/me", token=token)
    user = result.get("user", {})
    info(f"Logged in as {user.get('username', 'unknown')}")


def cmd_publish(args):
    """Compile and publish a spec to the registry."""
    from lap.cli.auth import get_token, api_request, get_registry_url
    from lap.core.compilers import compile as compile_spec

    token = get_token()
    if not token:
        error("Not logged in. Run 'lapsh login' first.")

    spec_path = args.spec
    if not Path(spec_path).exists():
        error(f"File not found: {spec_path}")

    # Determine spec name (and compile spec if needed)
    name = args.name
    result_obj = None
    if not name:
        try:
            result_obj = compile_spec(spec_path)
            if isinstance(result_obj, list):
                error("Protobuf directories produce multiple specs. Use --name to specify which to publish.")
            from lap.core.compilers.skill import _slugify
            name = _slugify(result_obj.api_name)
        except Exception as e:
            error(f"Could not auto-detect spec name: {e}. Use --name to specify.")

    if not name:
        error("Could not determine spec name. Use --name to specify.")

    # Compile spec (reuse cached result if available)
    print(f"Compiling {Path(spec_path).name}...")
    if result_obj is None:
        try:
            result_obj = compile_spec(spec_path)
        except ValueError as e:
            error(str(e))

    if isinstance(result_obj, list):
        error("Protobuf directories produce multiple specs. Publish each individually.")

    spec_text = result_obj.to_lap(lean=False)
    lean_text = result_obj.to_lap(lean=True)

    source_url = args.source_url or ""
    source_size = Path(spec_path).stat().st_size

    body = {
        "spec": spec_text,
        "lean_spec": lean_text,
        "provider": args.provider,
        "source_url": source_url,
        "source_size": source_size,
    }

    # Generate and include skill if --skill flag is set
    if getattr(args, "skill", False):
        from lap.core.compilers.skill import generate_skill, SkillOptions
        skill_layer = _resolve_ai(args, ai_attr="skill_ai", layer_attr="skill_layer")
        skill_opts = SkillOptions(layer=skill_layer, lean=True)
        skill = generate_skill(result_obj, skill_opts)

        if skill_layer == 2:
            try:
                from lap.core.compilers.skill_llm import enhance_skill
                print("Enhancing skill with AI...")
                skill = enhance_skill(result_obj, skill)
            except ImportError:
                if getattr(args, "skill_ai", None) is True or getattr(args, "skill_layer", None) == 2:
                    warn("claude CLI not available, skipping AI enhancement.")
            except RuntimeError as e:
                if getattr(args, "skill_ai", None) is True or getattr(args, "skill_layer", None) == 2:
                    warn(f"AI enhancement failed: {e}")

        body["skill_md"] = skill.file_map[skill.main_file]
        body["skill_refs"] = {
            k: v for k, v in skill.file_map.items() if k != skill.main_file
        }
        print(f"Including skill ({skill.token_count:,} tokens)...")

    from urllib.parse import quote
    print(f"Publishing {name} to provider {args.provider}...")
    result = api_request("POST", f"/v1/apis/{quote(name, safe='')}", body=body, token=token)
    info(f"Published {name} v{result.get('version', '?')} (provider: {result.get('provider', args.provider)})")
    print()
    print(f"  View: {get_registry_url()}/apis/{name}")
    print()
    print(f"  Next: lapsh skill-install {name}")


def cmd_skill(args):
    """Generate an AI IDE skill from an API spec."""
    from lap.core.compilers import compile as compile_spec
    from lap.core.compilers.skill import generate_skill, SkillOptions, detect_target
    from lap.core.utils import count_tokens

    spec_path = args.spec
    if not Path(spec_path).exists():
        error(f"File not found: {spec_path}")

    # Count source tokens for compression stats
    raw_tokens = count_tokens(Path(spec_path).read_text(encoding="utf-8"))

    filename = Path(spec_path).name
    fmt = getattr(args, "format", None)
    with _spinner(f"Compiling {filename}..."):
        try:
            result_obj = compile_spec(spec_path, format=fmt)
        except ValueError as e:
            error(str(e))

    if isinstance(result_obj, list):
        error("Protobuf directories produce multiple specs. Generate skills individually.")

    layer = _resolve_ai(args)
    options = SkillOptions(
        layer=layer,
        lean=not getattr(args, "full_spec", False),
        version=getattr(args, "skill_version", "1.0.0"),
        target=getattr(args, "target", None) or detect_target(),
    )

    with _spinner("Generating skill..."):
        skill = generate_skill(result_obj, options)

    # AI enhancement
    if layer == 2:
        try:
            from lap.core.compilers.skill_llm import enhance_skill
            with _spinner("Enhancing with AI..."):
                skill = enhance_skill(result_obj, skill)
        except ImportError:
            if getattr(args, "ai", None) is True or getattr(args, "layer", None) == 2:
                warn("claude CLI not available, skipping AI enhancement.")
        except RuntimeError as e:
            if getattr(args, "ai", None) is True or getattr(args, "layer", None) == 2:
                warn(f"AI enhancement failed: {e}")
                warn("Using standard generation.")

    # --stdout: print to stdout (old default behavior)
    if getattr(args, "stdout", False):
        print(skill.file_map[skill.main_file])
        return

    # Determine output directory
    if getattr(args, "install", False):
        out_dir = _resolve_install_dir(options.target, skill.name)
    elif args.output:
        out_dir = Path(args.output) / skill.name
    else:
        out_dir = Path(spec_path).parent / skill.name

    # Write skill files
    for rel_path, content in skill.file_map.items():
        out = out_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding='utf-8')

    reduction = int((1 - skill.token_count / raw_tokens) * 100) if raw_tokens else 0
    info(f"Generated skill -- {skill.name}")
    stats = f"     {skill.endpoint_count} endpoints | {skill.token_count:,} tokens | {reduction}% smaller than source"
    if HAS_RICH:
        console.print(f"[green]{stats}[/]")
    else:
        print(stats)
    print()

    if getattr(args, "install", False):
        print(f"  Installed to {out_dir.resolve()}")
    else:
        print(f"  Output   {out_dir.resolve()}")
        print()
        print(f"  Next: lapsh skill --install {Path(spec_path).name}")


def cmd_skill_batch(args):
    """Generate skills for all specs in a directory."""
    from lap.core.compilers import compile as compile_spec
    from lap.core.compilers.skill import generate_skill, SkillOptions, detect_target

    specs_dir = Path(args.directory)
    if not specs_dir.is_dir():
        error(f"Not a directory: {args.directory}")

    spec_files = _collect_spec_files(args.directory)

    if not spec_files:
        error(f"No spec files found in {args.directory}")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    layer = _resolve_ai(args)
    options = SkillOptions(layer=layer, lean=True, target=getattr(args, "target", None) or detect_target())
    success, failed, skipped = 0, 0, 0

    heading(f"Generating skills for {len(spec_files)} specs")

    for spec_path in spec_files:
        name = Path(spec_path).stem
        try:
            result_obj = compile_spec(spec_path)
            if isinstance(result_obj, list):
                warn(f"Skipping {name} (multi-spec)")
                skipped += 1
                continue
            skill = generate_skill(result_obj, options)

            if layer == 2:
                try:
                    from lap.core.compilers.skill_llm import enhance_skill
                    skill = enhance_skill(result_obj, skill)
                except (ImportError, RuntimeError) as e:
                    if getattr(args, "verbose", False):
                        warn(f"AI enhancement failed for {name}: {e}")

            skill_dir = out_dir / skill.name
            for rel_path, content in skill.file_map.items():
                out = skill_dir / rel_path
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(content, encoding='utf-8')
            success += 1
            print(f"  {name} -> {skill.name} ({skill.token_count:,} tokens)")
        except Exception as e:
            failed += 1
            warn(f"Failed {name}: {e}")
            if getattr(args, "verbose", False):
                import traceback
                traceback.print_exc()

    info(f"Generated {success} skills, {failed} failures, {skipped} skipped")


# ── Built-in skills ───────────────────────────────────────────────────

_BUILTIN_TARGET_DIRS = {
    "claude": "lap",
    "cursor": "cursor",
    "codex": "codex",
}


def _get_skills_dir():
    """Find bundled skills directory (repo root or installed package)."""
    # Development: repo root (lap/cli/main.py -> 3 parents up)
    repo_skills = Path(__file__).resolve().parent.parent.parent / "skills"
    if repo_skills.is_dir():
        return repo_skills
    # Installed package: lap/skills/ (lap/cli/main.py -> 2 parents up)
    pkg_skills = Path(__file__).resolve().parent.parent / "skills"
    if pkg_skills.is_dir():
        return pkg_skills
    return None


def _resolve_install_dir(target, name, custom_dir=None):
    """Determine install directory based on target IDE and optional override."""
    if custom_dir:
        return Path(custom_dir)
    if target == "cursor":
        return Path.home() / ".cursor" / "rules" / name
    if target == "codex":
        return Path.home() / ".codex" / "skills" / name
    return Path.home() / ".claude" / "skills" / name


def _install_builtin_skill(name, target, custom_dir):
    """Install a built-in skill (bundled with the package) to the target IDE directory."""
    skills_dir = _get_skills_dir()
    if not skills_dir:
        error("Built-in skill files not found. Reinstall the package.")

    src_subdir = _BUILTIN_TARGET_DIRS.get(target, "lap")
    src = skills_dir / src_subdir
    if not src.is_dir():
        error(f"No built-in skill '{name}' for target '{target}'.")

    install_dir = _resolve_install_dir(target, name, custom_dir)

    count = 0
    for src_file in src.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(src)
            dest = install_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")
            count += 1

    info(f"Installed {count} files to {install_dir}")


# ── Metadata helpers ─────────────────────────────────────────────────

def _metadata_path(target: str) -> Path:
    """Return path to lap-metadata.json for the given target platform."""
    if target == "cursor":
        return Path.home() / ".cursor" / "lap-metadata.json"
    if target == "codex":
        return Path.home() / ".codex" / "lap-metadata.json"
    return Path.home() / ".claude" / "lap-metadata.json"


def _read_metadata(target: str) -> dict:
    """Read lap-metadata.json for the given target. Returns {"skills": {}} if missing/corrupt."""
    p = _metadata_path(target)
    if not p.exists():
        return {"skills": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "skills" not in data:
            return {"skills": {}}
        return data
    except (json.JSONDecodeError, OSError):
        print(f"Warning: corrupt metadata at {p}, resetting.", file=sys.stderr)
        return {"skills": {}}


def _write_metadata(target: str, data: dict) -> None:
    """Atomically write lap-metadata.json for the given target."""
    p = _metadata_path(target)
    if p.exists() and p.is_symlink():
        raise RuntimeError(f"Refusing to write: {p} is a symlink")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)


def _compute_spec_hash(content: str) -> str:
    """Compute SHA-256 hex digest of spec content."""
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def _is_valid_skill_name(name: str) -> bool:
    """Check if skill name is safe (no path traversal, no hidden files)."""
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', name))


def _validate_registry_url(url: str) -> str:
    """Ensure registry URL uses HTTPS (except localhost for dev)."""
    for prefix in ("http://localhost:", "http://localhost/", "http://127.0.0.1:", "http://127.0.0.1/"):
        if url.startswith(prefix):
            return url
    if url in ("http://localhost", "http://127.0.0.1"):
        return url
    if not url.startswith("https://"):
        raise ValueError(f"Registry URL must use HTTPS: {url}")
    return url


def _register_session_hook(target: str) -> None:
    """Register LAP check hook for session start (idempotent)."""
    if target == "cursor":
        config_path = Path.home() / ".cursor" / "hooks.json"
        _register_cursor_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean --hook cursor")
    elif target == "codex":
        config_path = Path.home() / ".codex" / "hooks.json"
        _register_codex_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean --hook codex")
    else:
        config_path = Path.home() / ".claude" / "settings.json"
        _register_claude_hook(config_path, "npx @lap-platform/lapsh check --silent-if-clean --hook claude")


def _has_lap_hook(entries: list) -> bool:
    """Check if any entry in a hook list contains a lapsh check command."""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for h in entry.get("hooks", []):
            if isinstance(h, dict) and "lapsh check" in h.get("command", ""):
                return True
        if "lapsh check" in entry.get("command", ""):
            return True
    return False


def _register_claude_hook(config_path: Path, command: str) -> None:
    """Add SessionStart hook to .claude/settings.json (idempotent)."""
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if not isinstance(config, dict):
        config = {}

    hooks = config.setdefault("hooks", {})
    session_hooks = hooks.setdefault("SessionStart", [])

    if _has_lap_hook(session_hooks):
        info("Session hook already registered.")
        return

    session_hooks.append({
        "matcher": "",
        "hooks": [{"type": "command", "command": command}],
    })

    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp.replace(config_path)
    info("Registered session-start hook for update checking.")


def _register_cursor_hook(config_path: Path, command: str) -> None:
    """Add sessionStart hook to .cursor/hooks.json (idempotent)."""
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if not isinstance(config, dict):
        config = {}

    config.setdefault("version", 1)
    hooks = config.setdefault("hooks", {})
    session_hooks = hooks.setdefault("sessionStart", [])

    if _has_lap_hook(session_hooks):
        info("Session hook already registered.")
        return

    session_hooks.append({
        "command": command,
        "type": "command",
        "timeout": 30,
    })

    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp.replace(config_path)
    info("Registered session-start hook for update checking.")


def _register_codex_hook(config_path: Path, command: str) -> None:
    """Add SessionStart and TaskStarted hooks to .codex/hooks.json (idempotent)."""
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if not isinstance(config, dict):
        config = {}

    hooks = config.setdefault("hooks", {})

    for event_key in ("SessionStart", "TaskStarted"):
        event_hooks = hooks.setdefault(event_key, [])

        if not _has_lap_hook(event_hooks):
            event_hooks.append({
                "matcher": "",
                "hooks": [{"type": "command", "command": command}],
            })

    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp.replace(config_path)
    info("Registered session-start hook for update checking.")


_LAP_HOOK_MARKER = "<!-- LAP-HOOK-INSTRUCTION -->"
_LAP_HOOK_INSTRUCTION = f"""
{_LAP_HOOK_MARKER}
## LAP API Skill Updates

If a SessionStart hook injects LAP API skill update notifications into your context, you MUST present them to the user in your first response. Do not skip, defer, or wait to be asked. Include the full notification exactly as provided -- the update command, the diff command, and the pin command.
"""


def _ensure_md_hook_instruction(dot_dir: str, filename: str) -> None:
    """Add LAP hook instruction to a markdown config file (idempotent)."""
    md_path = Path.home() / dot_dir / filename
    content = ""
    if md_path.exists():
        content = md_path.read_text(encoding="utf-8")
        if _LAP_HOOK_MARKER in content:
            return
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(content + _LAP_HOOK_INSTRUCTION, encoding="utf-8")
    info(f"Added LAP update instruction to ~/{dot_dir}/{filename}")


def _ensure_cursor_update_rule() -> None:
    """Add LAP update always-apply rule to ~/.cursor/rules/ (idempotent)."""
    rule_path = Path.home() / ".cursor" / "rules" / "lap-updates.mdc"
    if rule_path.exists():
        return
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    rule_path.write_text(
        '---\ndescription: "LAP API skill update notifications"\nalwaysApply: true\n---\n\n'
        "If a sessionStart hook injects LAP API skill update notifications into your context, "
        "you MUST present them to the user in your first response. Do not skip, defer, or wait to be asked. "
        "Include the full notification exactly as provided -- the update command, the diff command, and the pin command.\n",
        encoding="utf-8",
    )
    info("Added LAP update rule to ~/.cursor/rules/lap-updates.mdc")


def cmd_init(args):
    """Set up LAP in your IDE (installs skill and config)."""
    target = getattr(args, "target", None) or "claude"
    _install_builtin_skill("lap", target, None)
    _register_session_hook(target)
    if target == "cursor":
        _ensure_cursor_update_rule()
    elif target == "codex":
        _ensure_md_hook_instruction(".codex", "AGENTS.md")
    else:
        _ensure_md_hook_instruction(".claude", "CLAUDE.md")


def cmd_skill_install(args):
    """Install a skill from the LAP registry."""
    from lap.cli.auth import get_registry_url
    from lap.core.compilers.skill import generate_skill, SkillOptions, detect_target
    from lap.core.parser import parse_lap as parse
    from urllib.parse import quote
    import urllib.request

    name = args.name
    if not _is_valid_skill_name(name):
        error(f"Invalid skill name: {name}")
    target = getattr(args, "target", None) or detect_target()

    registry = get_registry_url()
    try:
        registry = _validate_registry_url(registry)
    except ValueError as e:
        error(str(e))
    print(f"Fetching spec for {name} (target: {target})...")

    # Fetch LAP spec from registry
    try:
        url = f"{registry}/v1/apis/{quote(name, safe='')}"
        req = urllib.request.Request(url, headers={"Accept": "text/lap", "User-Agent": "lapsh"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            spec_text = resp.read().decode("utf-8")
    except Exception:
        error(f"Failed to fetch spec for '{name}' from {registry}.")

    if not spec_text.strip():
        error(f"No spec found for '{name}'.")

    # Parse and generate skill with target
    spec = parse(spec_text)
    options = SkillOptions(target=target)
    skill = generate_skill(spec, options)

    # Use raw fetched spec as reference (avoid lossy parse->serialize roundtrip)
    if "references/api-spec.lap" in skill.file_map:
        skill.file_map["references/api-spec.lap"] = spec_text

    # Determine install directory
    install_dir = _resolve_install_dir(target, skill.name, getattr(args, "dir", None))

    for rel_path, content in skill.file_map.items():
        out = install_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding='utf-8')

    info(f"Installed {len(skill.file_map)} files to {install_dir} ({skill.token_count:,} tokens)")

    # Write metadata
    try:
        spec_hash = _compute_spec_hash(spec_text) if spec_text else ""

        # Fetch version from registry (JSON response)
        try:
            json_url = f"{registry}/v1/apis/{quote(name, safe='')}"
            json_req = urllib.request.Request(json_url, headers={"Accept": "application/json", "User-Agent": "lapsh"})
            with urllib.request.urlopen(json_req, timeout=10) as json_resp:
                api_info = json.loads(json_resp.read().decode("utf-8"))
                registry_version = api_info.get("version", "unknown")
        except Exception:
            registry_version = "unknown"

        meta = _read_metadata(target)
        meta["skills"][name] = {
            "registryVersion": registry_version,
            "specHash": spec_hash,
            "installedAt": datetime.now(timezone.utc).isoformat(),
            "pinned": False,
            "skillName": skill.name,
        }
        _write_metadata(target, meta)
    except Exception as e:
        print(f"Warning: could not write metadata: {e}", file=sys.stderr)


def cmd_skill_uninstall(args):
    """Uninstall one or more skills."""
    import shutil

    explicit_target = getattr(args, "target", None)
    failed = 0

    for name in args.names:
        if not _is_valid_skill_name(name):
            warn(f"Invalid skill name: {name}")
            failed += 1
            continue

        target, meta = _resolve_skill_target(name, explicit_target)

        if name not in meta.get("skills", {}):
            warn(f"Skill '{name}' is not installed.")
            failed += 1
            continue

        # Resolve directory using skillName from metadata (may differ from registry name)
        skill_entry = meta["skills"][name]
        skill_dir_name = skill_entry.get("skillName", name)
        install_dir = _resolve_install_dir(target, skill_dir_name)

        # Remove skill directory
        if install_dir.is_dir():
            try:
                shutil.rmtree(install_dir)
            except OSError as e:
                warn(f"Failed to remove {install_dir}: {e}")
                failed += 1
                continue

        # Remove metadata entry
        del meta["skills"][name]
        _write_metadata(target, meta)

        info(f"Uninstalled '{name}' from {target}")

    if failed:
        sys.exit(1)


def _entry_has_lapsh(entry: dict) -> bool:
    """Check if a hook entry contains a lapsh command (any format)."""
    if not isinstance(entry, dict):
        return False
    for h in entry.get("hooks", []):
        if isinstance(h, dict) and "lapsh" in h.get("command", ""):
            return True
    return "lapsh" in entry.get("command", "")


def _remove_hook_entries(config_path: Path, event_keys: list) -> None:
    """Remove LAP hook entries from a JSON config file."""
    if not config_path.exists():
        return
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(config, dict):
        return

    hooks = config.get("hooks", {})
    changed = False

    for key in event_keys:
        event_hooks = hooks.get(key, [])
        if not event_hooks:
            continue
        filtered = [e for e in event_hooks if not _entry_has_lapsh(e)]
        if len(filtered) != len(event_hooks):
            changed = True
        if filtered:
            hooks[key] = filtered
        else:
            hooks.pop(key, None)

    if not changed:
        return

    if not hooks:
        config.pop("hooks", None)

    tmp = config_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2), encoding="utf-8")
    tmp.replace(config_path)
    info(f"Removed LAP session hook from {config_path.name}")


def _remove_session_hook(target: str) -> None:
    """Remove LAP check hook for the given target."""
    if target == "cursor":
        _remove_hook_entries(Path.home() / ".cursor" / "hooks.json", ["sessionStart"])
    elif target == "codex":
        _remove_hook_entries(Path.home() / ".codex" / "hooks.json", ["SessionStart", "TaskStarted"])
    else:
        _remove_hook_entries(Path.home() / ".claude" / "settings.json", ["SessionStart"])


def _remove_md_hook_instruction(dot_dir: str, filename: str) -> None:
    """Remove LAP hook instruction from a markdown config file."""
    md_path = Path.home() / dot_dir / filename
    if not md_path.exists():
        return
    content = md_path.read_text(encoding="utf-8")
    if _LAP_HOOK_MARKER not in content:
        return
    import re
    new_content = content.replace(_LAP_HOOK_INSTRUCTION, "")
    if _LAP_HOOK_MARKER in new_content:
        # Exact match failed (different version wrote the block) -- strip from marker
        new_content = re.sub(r"\n*<!-- LAP-HOOK-INSTRUCTION -->[\s\S]*?(?=\n## (?!LAP API Skill)|$)", "", new_content)
    new_content = new_content.rstrip("\n") + "\n"
    if new_content.strip():
        tmp = md_path.with_suffix(".tmp")
        tmp.write_text(new_content, encoding="utf-8")
        tmp.replace(md_path)
    else:
        md_path.unlink(missing_ok=True)
    info(f"Removed LAP instruction from ~/{dot_dir}/{filename}")


def _remove_cursor_update_rule() -> None:
    """Remove LAP update rule from ~/.cursor/rules/."""
    rule_path = Path.home() / ".cursor" / "rules" / "lap-updates.mdc"
    try:
        rule_path.unlink()
        info("Removed ~/.cursor/rules/lap-updates.mdc")
    except FileNotFoundError:
        pass




def cmd_uninstall(args):
    """Fully remove LAP from your IDE."""
    import shutil
    from lap.core.compilers.skill import detect_target

    target = getattr(args, "target", None) or detect_target()

    # 1. Remove all installed API skills (using metadata)
    meta = _read_metadata(target)
    for name, entry in list(meta.get("skills", {}).items()):
        skill_dir_name = entry.get("skillName", name)
        install_dir = _resolve_install_dir(target, skill_dir_name)
        if install_dir.is_dir():
            try:
                shutil.rmtree(install_dir)
                info(f"Removed skill '{name}'")
            except OSError as e:
                warn(f"Failed to remove skill '{name}': {e}")
        else:
            info(f"Removed skill '{name}' (directory already gone)")

    # 2. Remove built-in LAP skill directory
    lap_skill_dir = _resolve_install_dir(target, "lap")
    if lap_skill_dir.is_dir():
        try:
            shutil.rmtree(lap_skill_dir)
            info("Removed built-in LAP skill")
        except OSError as e:
            warn(f"Failed to remove built-in LAP skill: {e}")

    # 3. Remove metadata file
    meta_path = _metadata_path(target)
    try:
        meta_path.unlink()
        info(f"Removed {meta_path}")
    except FileNotFoundError:
        pass

    # 4. Remove session hook from config
    _remove_session_hook(target)

    # 5. Remove CLAUDE.md instruction / Cursor update rule / Codex AGENTS.md
    if target == "claude":
        _remove_md_hook_instruction(".claude", "CLAUDE.md")
    elif target == "codex":
        _remove_md_hook_instruction(".codex", "AGENTS.md")
    else:
        _remove_cursor_update_rule()

    info(f"LAP fully uninstalled from {target}")


def cmd_check(args):
    """Check for LAP skill updates."""
    from lap.cli.auth import get_registry_url
    import urllib.request

    silent = getattr(args, "silent_if_clean", False)
    json_output = getattr(args, "json", False)
    target_arg = getattr(args, "target", None)
    hook_format = getattr(args, "hook", "") or ""

    targets = []
    if target_arg and target_arg != "auto":
        targets = [target_arg]
    else:
        for t in ["claude", "cursor", "codex"]:
            if _metadata_path(t).exists():
                targets.append(t)

    if not targets:
        if not silent:
            print("No LAP metadata found. Install skills first with: lapsh skill-install <name>")
        return

    skills_to_check = []
    skill_targets = {}

    for t in targets:
        meta = _read_metadata(t)
        for name, skill_info in meta.get("skills", {}).items():
            if skill_info.get("pinned", False):
                continue
            skills_to_check.append({"name": name, "version": skill_info.get("registryVersion", "")})
            skill_targets[name] = t

    if not skills_to_check:
        if not silent:
            print("All skills are up to date (or pinned).")
        return

    registry = get_registry_url()
    try:
        registry = _validate_registry_url(registry)
    except ValueError as e:
        if not silent:
            print(f"Error: {e}", file=sys.stderr)
        return

    try:
        url = f"{registry}/v1/skills/check"
        payload = json.dumps({"skills": skills_to_check}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "lapsh"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception:
        if silent:
            return
        print("Warning: Could not reach LAP registry for update check.", file=sys.stderr)
        return

    updates = [r for r in result.get("results", []) if r.get("has_update")]

    if not updates:
        if json_output:
            print(json.dumps({"updates": []}, indent=2))
        elif not silent:
            print("All skills are up to date.")
        return

    if json_output:
        print(json.dumps({"updates": updates}, indent=2))
        return

    # Build human-readable message
    lines = []
    if len(updates) == 1:
        u = updates[0]
        sn = _sanitize(str(u.get('name', '')))
        si = _sanitize(str(u.get('installed_version', '')))
        sl = _sanitize(str(u.get('latest_version', '')))
        st = skill_targets.get(sn, "claude")
        lines.append("LAP skill update available:")
        lines.append(f"  {sn}: {si} -> {sl}")
        lines.append("")
        lines.append(f"  Update:  lapsh skill-install {sn} --target {st}")
        lines.append(f"  Changes: lapsh diff {sn}")
        lines.append(f"  Pin:     lapsh pin {sn}")
    else:
        lines.append(f"{len(updates)} LAP skills have updates:")
        names = []
        update_targets = set()
        for u in updates:
            sn = _sanitize(str(u.get('name', '')))
            si = _sanitize(str(u.get('installed_version', '')))
            sl = _sanitize(str(u.get('latest_version', '')))
            names.append(sn)
            update_targets.add(skill_targets.get(sn, "claude"))
            lines.append(f"  {sn:<20s} {si} -> {sl}")
        lines.append("")
        common_target = next(iter(update_targets)) if len(update_targets) == 1 else "claude"
        lines.append(f"  Update all: lapsh skill-install {' '.join(names)} --target {common_target}")
        lines.append("  See changes: lapsh diff <skill>")
        lines.append("  Pin a skill: lapsh pin <skill>")

    msg = "\n".join(lines)

    if hook_format:
        context = "ACTION REQUIRED -- You MUST present the following LAP API skill updates to the user in your FIRST response. Do not skip or defer this:\n\n" + msg
        if hook_format == "cursor":
            print(json.dumps({"additional_context": context}))
        else:
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context},
            }))
    else:
        print(msg)


def _resolve_skill_target(name: str, explicit_target=None):
    """Find which target has the skill installed. Returns (target, metadata)."""
    from lap.core.compilers.skill import detect_target
    target = explicit_target or detect_target()
    meta = _read_metadata(target)
    if name in meta.get("skills", {}):
        return target, meta
    # Try other targets
    for other in ("claude", "cursor", "codex"):
        if other == target:
            continue
        other_meta = _read_metadata(other)
        if name in other_meta.get("skills", {}):
            return other, other_meta
    return target, meta  # return original (will fail the "not found" check)


def cmd_pin(args):
    """Pin a skill to skip update checks."""
    name = args.name
    if not _is_valid_skill_name(name):
        error(f"Invalid skill name: {name}")
    target, meta = _resolve_skill_target(name, getattr(args, "target", None))
    if name not in meta.get("skills", {}):
        error(f"Skill '{name}' is not installed. Install it first: lapsh skill-install {name}")
    meta["skills"][name]["pinned"] = True
    _write_metadata(target, meta)
    info(f"Pinned '{name}'. It will be skipped during update checks.")


def cmd_unpin(args):
    """Unpin a skill to resume update checks."""
    name = args.name
    if not _is_valid_skill_name(name):
        error(f"Invalid skill name: {name}")
    target, meta = _resolve_skill_target(name, getattr(args, "target", None))
    if name not in meta.get("skills", {}):
        error(f"Skill '{name}' is not installed. Install it first: lapsh skill-install {name}")
    meta["skills"][name]["pinned"] = False
    _write_metadata(target, meta)
    info(f"Unpinned '{name}'. It will be included in update checks.")


def _format_search_results(results, total, offset):
    """Format and print search results."""
    rows = []
    for r in results:
        name = _sanitize(r.get("name", ""))
        prov = r.get("provider") or {}
        prov_str = _sanitize(prov.get("domain", "") or prov.get("display_name", "") or "")
        desc = _sanitize(r.get("description", ""))
        ep = r.get("endpoints")
        ep_str = f"{ep} endpoints" if isinstance(ep, int) else ""
        size = r.get("size", 0)
        lean = r.get("lean_size")
        if isinstance(size, (int, float)) and isinstance(lean, (int, float)) and lean:
            ratio_str = f"{size / lean:.1f}x compressed"
        else:
            ratio_str = ""
        skill = " [skill]" if r.get("has_skill") else ""
        community = " [community]" if r.get("is_community") else ""
        rows.append((name, prov_str, ep_str, ratio_str, desc, skill, community))

    name_w = max((len(r[0]) for r in rows), default=0)
    prov_w = max((len(r[1]) for r in rows), default=0)
    ep_w = max((len(r[2]) for r in rows), default=0)
    ratio_w = max((len(r[3]) for r in rows), default=0)

    for name, prov_str, ep_str, ratio_str, desc, skill, community in rows:
        print(f"  {name:<{name_w}}  {prov_str:<{prov_w}}  {ep_str:>{ep_w}}  {ratio_str:>{ratio_w}}   {desc}{skill}{community}")

    shown = offset + len(results)
    if shown < total:
        info(f"Showing {shown}/{total} results. Use --offset {shown} for more.")


from urllib.request import urlopen, Request as _UrlRequest


def cmd_get(args):
    """Download a LAP spec from the registry by name."""
    from lap.cli.auth import get_registry_url
    from urllib.parse import quote

    name = args.name
    url = f"{get_registry_url()}/v1/apis/{quote(name, safe='')}"
    if getattr(args, "lean", False):
        url += "?format=lean"

    try:
        req = _UrlRequest(url, headers={"Accept": "text/lap", "User-Agent": "lapsh/0.4.7"})
        with urlopen(req) as resp:
            body = resp.read().decode("utf-8")
    except Exception as e:
        error(f"Failed to fetch '{name}': {e}")

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(body, encoding="utf-8")
        info(f"Saved {name} to {args.output}")
    else:
        print(body)


def cmd_search(args):
    """Search the LAP registry for APIs. No auth required."""
    from lap.cli.auth import api_request
    from urllib.parse import urlencode

    query = " ".join(args.query)
    if not query.strip():
        error("Please provide a search query.")

    params = {"q": query}
    if args.tag:
        params["tag"] = args.tag
    if args.sort:
        params["sort"] = args.sort
    if args.limit is not None:
        params["limit"] = str(args.limit)
    if args.offset is not None:
        params["offset"] = str(args.offset)

    try:
        result = api_request("GET", f"/v1/search?{urlencode(params)}")
    except SystemExit:
        raise
    except Exception as e:
        error(f"Search failed: {e}")

    _validate_search_response(result)

    results = result.get("results", [])
    total = result.get("total", len(results))
    offset = result.get("offset", 0)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return

    if not results:
        info(f"No results for '{query}'.")
        return

    _format_search_results(results, total, offset)


def cmd_benchmark_skill(args):
    """Benchmark skill token usage for a spec."""
    from lap.core.compilers import compile as compile_spec
    from lap.core.compilers.skill import generate_skill
    from lap.core.utils import count_tokens as count

    spec_path = args.spec
    if not Path(spec_path).exists():
        error(f"File not found: {spec_path}")

    try:
        result_obj = compile_spec(spec_path)
    except ValueError as e:
        error(str(e))

    if isinstance(result_obj, list):
        error("Multi-spec not supported for skill benchmark.")

    skill = generate_skill(result_obj)
    raw = Path(spec_path).read_text(encoding='utf-8')
    raw_tokens = count(raw)

    heading(f"Skill Benchmark: {Path(spec_path).name}")
    print(f"  API: {result_obj.api_name}")
    print(f"  Endpoints: {len(result_obj.endpoints)}")
    print(f"  Raw spec tokens: {raw_tokens:,}")
    for file_path, content in skill.file_map.items():
        print(f"  {file_path} tokens: {count(content):,}")
    print(f"  Total skill tokens: {skill.token_count:,}")
    ratio = raw_tokens / skill.token_count if skill.token_count else 0
    print(f"  Compression ratio: {ratio:.1f}x")


def cmd_benchmark_skill_all(args):
    """Benchmark skills for all specs in a directory."""
    from lap.core.compilers.openapi import compile_openapi
    from lap.core.compilers.skill import generate_skill
    from lap.core.utils import count_tokens as count

    specs_dir = Path(args.directory)
    if not specs_dir.is_dir():
        error(f"Not a directory: {args.directory}")

    spec_files = _collect_spec_files(args.directory)

    if not spec_files:
        error(f"No spec files found in {args.directory}")

    heading(f"Skill Benchmark ({len(spec_files)} specs)")

    totals = {"raw": 0, "skill_md": 0, "total": 0, "endpoints": 0}
    results = []

    for spec_path in spec_files:
        name = Path(spec_path).stem
        try:
            raw = Path(spec_path).read_text(encoding='utf-8')
            ds = compile_openapi(spec_path)
            skill = generate_skill(ds)
            raw_t = count(raw)
            skill_md_t = count(skill.file_map[skill.main_file])
            total_t = skill.token_count
            ratio = raw_t / total_t if total_t else 0
            totals["raw"] += raw_t
            totals["skill_md"] += skill_md_t
            totals["total"] += total_t
            totals["endpoints"] += len(ds.endpoints)
            results.append((name, len(ds.endpoints), raw_t, skill_md_t, total_t, ratio))
        except Exception as e:
            warn(f"Failed {name}: {e}")

    if HAS_RICH:
        table = Table(title="Skill Token Benchmark", box=box.SIMPLE_HEAVY)
        table.add_column("API", style="cyan", min_width=18)
        table.add_column("Endpoints", justify="right")
        table.add_column("Raw", justify="right")
        table.add_column("SKILL.md", justify="right", style="green")
        table.add_column("Total", justify="right", style="bold green")
        table.add_column("Ratio", justify="right", style="yellow")

        for name, eps, raw_t, skill_md_t, total_t, ratio in results:
            table.add_row(name, str(eps), f"{raw_t:,}", f"{skill_md_t:,}", f"{total_t:,}", f"{ratio:.1f}x")

        t = totals
        table.add_section()
        overall_ratio = t["raw"] / t["total"] if t["total"] else 0
        table.add_row(
            "[bold]TOTAL[/]", str(t["endpoints"]),
            f"[bold]{t['raw']:,}[/]", f"[bold]{t['skill_md']:,}[/]",
            f"[bold]{t['total']:,}[/]", f"[bold]{overall_ratio:.1f}x[/]",
        )
        console.print(table)
    else:
        for name, eps, raw_t, skill_md_t, total_t, ratio in results:
            print(f"  {name}: {eps} eps, {total_t:,} total tokens, {ratio:.1f}x compression")
        overall = totals["raw"] / totals["total"] if totals["total"] else 0
        print(f"\nTotal: {len(results)} specs, {totals['total']:,} tokens, {overall:.1f}x compression")


def cmd_diff(args):
    """Diff two LAP files or compare installed skill vs registry latest."""
    from lap.core.parser import parse_lap
    from lap.core.differ import diff_specs, generate_changelog, check_compatibility

    # Smart overload: single arg that doesn't look like a file path = skill name
    if args.new is None:
        name = args.old
        if name.endswith('.lap') or '/' in name or '\\' in name:
            error("Need two files to diff. Usage: lapsh diff old.lap new.lap")
        _diff_skill(name, args)
        return

    # Existing two-file diff behavior
    old_path, new_path = Path(args.old), Path(args.new)
    if not old_path.exists():
        error(f"File not found: {args.old}")
    if not new_path.exists():
        error(f"File not found: {args.new}")

    old_spec = parse_lap(old_path.read_text(encoding='utf-8'))
    new_spec = parse_lap(new_path.read_text(encoding='utf-8'))

    if args.format == "changelog":
        print(generate_changelog(old_spec, new_spec, version=args.version or "0.0.0"))
        return

    diff = diff_specs(old_spec, new_spec)
    compat = check_compatibility(old_spec, new_spec)

    if HAS_RICH:
        status = "[bold red]BREAKING[/]" if compat.severity == "MAJOR" else "[bold green]COMPATIBLE[/]"
        console.print(f"\nSemver: [bold]{compat.severity}[/] -- {status}\n")

        if diff.breaking_changes:
            console.print("[bold red]Breaking Changes:[/]")
            for c in diff.breaking_changes:
                console.print(f"  [red]x[/] {c.detail}")
            console.print()

        if diff.non_breaking_changes:
            console.print("[bold green]Non-breaking Changes:[/]")
            for c in diff.non_breaking_changes:
                console.print(f"  [green]o[/] {c.detail}")
            console.print()

        if not diff.changes:
            console.print("[dim]No changes detected.[/]")
    else:
        print(f"\nSemver: {compat.severity}")
        for c in diff.breaking_changes:
            print(f"  BREAKING: {c.detail}")
        for c in diff.non_breaking_changes:
            print(f"  {c.detail}")
        if not diff.changes:
            print("No changes detected.")


def _diff_skill(name: str, args) -> None:
    """Compare installed skill spec vs registry latest."""
    from lap.cli.auth import get_registry_url
    from lap.core.parser import parse_lap
    from lap.core.differ import diff_specs, check_compatibility
    from lap.core.compilers.skill import detect_target
    from urllib.parse import quote
    import urllib.request

    if not _is_valid_skill_name(name):
        error(f"Invalid skill name: {name}")

    # Find installed spec -- use skillName from metadata if available (folder may differ from registry name)
    target = detect_target()
    meta = _read_metadata(target)
    folder_name = meta.get("skills", {}).get(name, {}).get("skillName", name)

    install_dir = _resolve_install_dir(target, folder_name)
    spec_file = install_dir / "references" / "api-spec.lap"

    if not spec_file.exists():
        # Try other targets
        for other in ("claude", "cursor", "codex"):
            if other == target:
                continue
            other_meta = _read_metadata(other)
            folder_name = other_meta.get("skills", {}).get(name, {}).get("skillName", name)
            install_dir = _resolve_install_dir(other, folder_name)
            spec_file = install_dir / "references" / "api-spec.lap"
            if spec_file.exists():
                target = other
                meta = other_meta
                break

    if not spec_file.exists():
        error(f"No installed spec found for '{name}'. Install it first: lapsh skill-install {name}")

    old_text = spec_file.read_text(encoding='utf-8')
    old_spec = parse_lap(old_text)

    # Fetch latest from registry
    registry = get_registry_url()
    try:
        registry = _validate_registry_url(registry)
    except ValueError as e:
        error(str(e))
    try:
        url = f"{registry}/v1/apis/{quote(name, safe='')}"
        req = urllib.request.Request(url, headers={"Accept": "text/lap", "User-Agent": "lapsh"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            new_text = resp.read().decode("utf-8")
    except Exception:
        error(f"Failed to fetch latest spec for '{name}' from registry.")

    new_spec = parse_lap(new_text)

    # Get version info from metadata (already read above)
    old_version = meta.get("skills", {}).get(name, {}).get("registryVersion", "installed")

    diff = diff_specs(old_spec, new_spec)

    print(f"{name}: {old_version} -> latest")
    print()

    if diff.added_endpoints:
        print(f"  Added ({len(diff.added_endpoints)}):")
        for ep in diff.added_endpoints:
            print(f"    + {ep}")

    if diff.removed_endpoints:
        print(f"  Removed ({len(diff.removed_endpoints)}):")
        for ep in diff.removed_endpoints:
            print(f"    - {ep}")

    changes = diff.changes
    if changes:
        print(f"  Changed ({len(changes)}):")
        for c in changes[:10]:
            print(f"    ~ {c.endpoint} -- {c.detail}")
        if len(changes) > 10:
            print(f"    ... and {len(changes) - 10} more")

    if not diff.added_endpoints and not diff.removed_endpoints and not changes:
        print("  No differences found.")

    # Token impact
    from lap.core.utils import count_tokens
    old_tokens = count_tokens(old_text)
    new_tokens = count_tokens(new_text)
    if old_tokens and new_tokens:
        delta = new_tokens - old_tokens
        pct = (delta / old_tokens * 100) if old_tokens else 0
        sign = "+" if delta >= 0 else ""
        print(f"\n  Token impact: {old_tokens:,} -> {new_tokens:,} tokens ({sign}{pct:.0f}%)")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="lapsh",
        description="LAP -- Lean API Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'lapsh <command> --help' for more info on a command.",
    )
    parser.add_argument("--version", action="version", version=f"lapsh {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # compile (unified -- auto-detects format)
    p = sub.add_parser("compile", help="Compile API spec to LAP (auto-detects format)")
    p.add_argument("spec", help="Path to API spec file or directory")
    p.add_argument("-o", "--output", help="Output file path")
    p.add_argument("-f", "--format",
                   choices=["openapi", "graphql", "asyncapi", "protobuf", "postman", "smithy"],
                   help="Force spec format (auto-detected if omitted)")
    p.add_argument("--lean", action="store_true", help="Maximum compression (strip descriptions)")
    p.add_argument("--stdout", action="store_true", help="Print to stdout instead of saving files")

    # benchmark-all
    p = sub.add_parser("benchmark-all", help="Benchmark all specs in a directory")
    p.add_argument("directory", help="Directory containing spec files")

    # inspect
    p = sub.add_parser("inspect", help="Parse and inspect a LAP file")
    p.add_argument("file", help="Path to .lap file")
    p.add_argument("--endpoint", "-e", help='Filter endpoint, e.g. "POST /v1/charges"')

    # convert
    p = sub.add_parser("convert", help="Convert LAP back to OpenAPI")
    p.add_argument("file", help="Path to .lap file")
    p.add_argument("-f", "--format", default="openapi", help="Output format (default: openapi)")
    p.add_argument("-o", "--output", help="Output file path")

    # diff
    p = sub.add_parser("diff", help="Diff two LAP files or compare installed skill vs registry")
    p.add_argument("old", help="Path to old .lap file or skill name")
    p.add_argument("new", nargs="?", default=None, help="Path to new .lap file (omit for skill diff)")
    p.add_argument("--format", choices=["summary", "changelog"], default="summary", help="Output format")
    p.add_argument("--version", help="Version label for changelog")

    # login
    p = sub.add_parser("login", help="Authenticate with the LAP registry via GitHub")
    p.add_argument("--name", dest="token_name", help="Token name for identification (e.g. ci-github-actions)")

    # logout
    p = sub.add_parser("logout", help="Log out and revoke API token")

    # whoami
    p = sub.add_parser("whoami", help="Show current authenticated user")

    # publish
    p = sub.add_parser("publish", help="Compile and publish a spec to the registry")
    p.add_argument("spec", help="Path to API spec file")
    p.add_argument("--provider", required=True, help="Provider domain or slug (e.g. stripe.com)")
    p.add_argument("--name", help="Override spec name (auto-detected if omitted)")
    p.add_argument("--source-url", help="Upstream spec URL")
    p.add_argument("--skill", action="store_true", help="Generate and include a Claude Code skill")
    p.add_argument("--skill-ai", action="store_true", default=None,
                   help="Force AI enhancement for skill (requires claude CLI)")
    p.add_argument("--no-skill-ai", dest="skill_ai", action="store_false",
                   help="Skip AI enhancement for skill")
    p.add_argument("--skill-layer", type=int, default=None, choices=[1, 2],
                   help=argparse.SUPPRESS)  # deprecated

    # skill
    p = sub.add_parser("skill", help="Generate an AI IDE skill from an API spec")
    p.add_argument("spec", help="Path to API spec file")
    p.add_argument("-o", "--output", help="Output parent directory (default: same directory as spec)")
    p.add_argument("-f", "--format",
                   choices=["openapi", "graphql", "asyncapi", "protobuf", "postman", "smithy"],
                   help="Force spec format (auto-detected if omitted)")
    p.add_argument("--ai", action="store_true", default=None,
                   help="Force AI enhancement (requires claude CLI)")
    p.add_argument("--no-ai", dest="ai", action="store_false",
                   help="Skip AI enhancement")
    p.add_argument("--stdout", action="store_true",
                   help="Print to stdout instead of writing files")
    p.add_argument("--layer", type=int, default=None, choices=[1, 2],
                   help=argparse.SUPPRESS)  # deprecated
    p.add_argument("--full-spec", action="store_true", help="Include full spec (not lean)")
    p.add_argument("--install", action="store_true", help="Install skill to target IDE directory")
    p.add_argument("--version", dest="skill_version", default="1.0.0",
                   help="Skill version (default: 1.0.0)")
    p.add_argument("--target", choices=["claude", "cursor", "codex"],
                   default=None,
                   help="Target IDE for skill output (default: auto-detect)")

    # skill-batch
    p = sub.add_parser("skill-batch", help="Generate skills for all specs in a directory")
    p.add_argument("directory", help="Directory containing spec files")
    p.add_argument("-o", "--output", required=True, help="Output directory")
    p.add_argument("--ai", action="store_true", default=None,
                   help="Force AI enhancement (requires claude CLI)")
    p.add_argument("--no-ai", dest="ai", action="store_false",
                   help="Skip AI enhancement")
    p.add_argument("--layer", type=int, default=None, choices=[1, 2],
                   help=argparse.SUPPRESS)  # deprecated
    p.add_argument("--verbose", "-v", action="store_true", help="Print full tracebacks on failure")
    p.add_argument("--target", choices=["claude", "cursor", "codex"],
                   default=None,
                   help="Target IDE for skill output (default: auto-detect)")

    # init
    p = sub.add_parser("init", help="Set up LAP in your IDE (installs skill and config)")
    p.add_argument("--target", choices=["claude", "cursor", "codex"], default=None,
                   help="Target IDE (default: auto-detect)")

    # skill-install
    p = sub.add_parser("skill-install", help="Install a skill from the LAP registry")
    p.add_argument("name", help="API name from the registry")
    p.add_argument("--dir", help="Custom install directory")
    p.add_argument("--target", choices=["claude", "cursor", "codex"],
                   default=None,
                   help="Target IDE (default: auto-detect)")

    # skill-uninstall / skill-remove
    p = sub.add_parser("skill-uninstall", aliases=["skill-remove"],
                        help="Uninstall one or more skills")
    p.add_argument("names", nargs="+", help="Skill name(s) to uninstall")
    p.add_argument("--target", choices=["claude", "cursor", "codex"], default=None,
                   help="Target IDE (default: auto-detect)")

    # uninstall
    p = sub.add_parser("uninstall", help="Fully remove LAP from your IDE")
    p.add_argument("--target", choices=["claude", "cursor", "codex"], default=None,
                   help="Target IDE (default: auto-detect)")

    # get
    p = sub.add_parser("get", help="Download a LAP spec from the registry")
    p.add_argument("name", help="API name (e.g. stripe)")
    p.add_argument("-o", "--output", help="Output file path")
    p.add_argument("--lean", action="store_true", help="Download lean variant")

    # search
    p = sub.add_parser("search", help="Search the LAP registry for APIs")
    p.add_argument("query", nargs="+", help="Search query")
    p.add_argument("--tag", help="Filter by tag")
    p.add_argument("--sort", choices=["relevance", "popularity", "date"], help="Sort order")
    p.add_argument("--limit", type=int, help="Max results (default: 50)")
    p.add_argument("--offset", type=int, help="Pagination offset")
    p.add_argument("--json", action="store_true", help="Output raw JSON")

    # benchmark-skill
    p = sub.add_parser("benchmark-skill", help="Benchmark skill token usage for a spec")
    p.add_argument("spec", help="Path to API spec file")

    # benchmark-skill-all
    p = sub.add_parser("benchmark-skill-all", help="Benchmark skills for all specs in a directory")
    p.add_argument("directory", help="Directory containing spec files")

    # check
    p = sub.add_parser("check", help="Check for LAP skill updates")
    p.add_argument("--silent-if-clean", action="store_true", help="No output if everything is up to date")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p.add_argument("--hook", nargs="?", const="claude", default="", help="Output format for IDE hooks (claude, cursor, codex)")
    p.add_argument("--target", choices=["auto", "claude", "cursor", "codex"], default="auto", help="Target platform")

    # pin
    p = sub.add_parser("pin", help="Pin a skill to skip update checks")
    p.add_argument("name", help="Skill name to pin")
    p.add_argument("--target", choices=["claude", "cursor", "codex"], default=None, help="Target platform")

    # unpin
    p = sub.add_parser("unpin", help="Unpin a skill to resume update checks")
    p.add_argument("name", help="Skill name to unpin")
    p.add_argument("--target", choices=["claude", "cursor", "codex"], default=None, help="Target platform")

    args = parser.parse_args()

    commands = {
        "compile": cmd_compile,
        "benchmark-all": cmd_benchmark_all,
        "inspect": cmd_inspect,
        "convert": cmd_convert,
        "diff": cmd_diff,
        "login": cmd_login,
        "logout": cmd_logout,
        "whoami": cmd_whoami,
        "publish": cmd_publish,
        "skill": cmd_skill,
        "skill-batch": cmd_skill_batch,
        "init": cmd_init,
        "skill-install": cmd_skill_install,
        "skill-uninstall": cmd_skill_uninstall,
        "skill-remove": cmd_skill_uninstall,
        "uninstall": cmd_uninstall,
        "get": cmd_get,
        "search": cmd_search,
        "benchmark-skill": cmd_benchmark_skill,
        "benchmark-skill-all": cmd_benchmark_skill_all,
        "check": cmd_check,
        "pin": cmd_pin,
        "unpin": cmd_unpin,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
