#!/usr/bin/env python3
"""
LAP CLI -- Lean API Platform command-line tool.

Compile, inspect, and convert LAP API specifications.
"""

import argparse
import glob
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

# Add project root to path so `lap.*` imports work when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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
            name = result_obj.api_name.lower().replace(" ", "-").replace("_", "-")
            name = "".join(c for c in name if c.isalnum() or c == "-").strip("-")
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

        body["skill_md"] = skill.file_map["SKILL.md"]
        body["skill_refs"] = {
            k: v for k, v in skill.file_map.items() if k != "SKILL.md"
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
    """Generate a Claude Code skill from an API spec."""
    from lap.core.compilers import compile as compile_spec
    from lap.core.compilers.skill import generate_skill, SkillOptions
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
        print(skill.file_map["SKILL.md"])
        return

    # Determine output directory
    if getattr(args, "install", False):
        out_dir = Path.home() / ".claude" / "skills" / skill.name
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
    from lap.core.compilers.skill import generate_skill, SkillOptions

    specs_dir = Path(args.directory)
    if not specs_dir.is_dir():
        error(f"Not a directory: {args.directory}")

    spec_files = _collect_spec_files(args.directory)

    if not spec_files:
        error(f"No spec files found in {args.directory}")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    layer = _resolve_ai(args)
    options = SkillOptions(layer=layer, lean=True)
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


def cmd_skill_install(args):
    """Install a skill from the LAP registry."""
    from lap.cli.auth import api_request, get_registry_url
    from urllib.parse import quote
    import json as json_mod

    name = args.name
    registry = get_registry_url()
    print(f"Fetching skill bundle for {name}...")

    try:
        result = api_request("GET", f"/v1/apis/{quote(name, safe='')}/skill/bundle")
    except SystemExit:
        error(f"Failed to fetch skill from {registry}. Check that '{name}' exists and has a skill.")

    files = result.get("files", {})
    if not files:
        error(f"No skill files found for '{name}'.")

    install_dir = Path(getattr(args, "dir", None) or (Path.home() / ".claude" / "skills" / name))
    for rel_path, content in files.items():
        out = install_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding='utf-8')

    info(f"Installed {len(files)} files to {install_dir}")


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
        rows.append((name, prov_str, ep_str, ratio_str, desc, skill))

    name_w = max((len(r[0]) for r in rows), default=0)
    prov_w = max((len(r[1]) for r in rows), default=0)
    ep_w = max((len(r[2]) for r in rows), default=0)
    ratio_w = max((len(r[3]) for r in rows), default=0)

    for name, prov_str, ep_str, ratio_str, desc, skill in rows:
        print(f"  {name:<{name_w}}  {prov_str:<{prov_w}}  {ep_str:>{ep_w}}  {ratio_str:>{ratio_w}}   {desc}{skill}")

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
            skill_md_t = count(skill.file_map["SKILL.md"])
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
    """Diff two LAP files."""
    from lap.core.parser import parse_lap
    from lap.core.differ import diff_specs, generate_changelog, check_compatibility

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
                console.print(f"  [red]✗[/] {c.detail}")
            console.print()

        if diff.non_breaking_changes:
            console.print("[bold green]Non-breaking Changes:[/]")
            for c in diff.non_breaking_changes:
                console.print(f"  [green]✓[/] {c.detail}")
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


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="lapsh",
        description="LAP -- Lean API Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'lapsh <command> --help' for more info on a command.",
    )
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
    p = sub.add_parser("diff", help="Diff two LAP files")
    p.add_argument("old", help="Path to old .lap file")
    p.add_argument("new", help="Path to new .lap file")
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
    p = sub.add_parser("skill", help="Generate a Claude Code skill from an API spec")
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
    p.add_argument("--install", action="store_true", help="Install skill to ~/.claude/skills/")
    p.add_argument("--version", dest="skill_version", default="1.0.0",
                   help="Skill version (default: 1.0.0)")

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

    # skill-install
    p = sub.add_parser("skill-install", help="Install a skill from the LAP registry")
    p.add_argument("name", help="API name from the registry")
    p.add_argument("--dir", help="Custom install directory (default: ~/.claude/skills/)")

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
        "skill-install": cmd_skill_install,
        "get": cmd_get,
        "search": cmd_search,
        "benchmark-skill": cmd_benchmark_skill,
        "benchmark-skill-all": cmd_benchmark_skill_all,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
