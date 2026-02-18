#!/usr/bin/env python3
"""
LAP CLI -- LeanAgent Protocol command-line tool.

Compile, validate, benchmark, inspect, and convert LAP API specifications.
"""

import argparse
import glob
import json
import os
import sys
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


# ── Helpers ──────────────────────────────────────────────────────────

def info(msg):
    if HAS_RICH:
        console.print(f"[bold green]✓[/] {msg}")
    else:
        print(f"✓ {msg}")

def warn(msg):
    if HAS_RICH:
        console.print(f"[bold yellow]⚠[/] {msg}")
    else:
        print(f"⚠ {msg}")

def error(msg):
    if HAS_RICH:
        console.print(f"[bold red]✗[/] {msg}")
    else:
        print(f"✗ {msg}")
    sys.exit(1)

def heading(msg):
    if HAS_RICH:
        console.print(Panel(msg, style="bold cyan", box=box.ROUNDED))
    else:
        print(f"\n{'='*60}\n  {msg}\n{'='*60}")


# ── Commands ─────────────────────────────────────────────────────────

def cmd_compile(args):
    """Compile any API spec to LAP format (auto-detects format)."""
    from lap.core.compilers import compile as compile_spec

    spec_path = args.spec
    if not Path(spec_path).exists():
        error(f"File/directory not found: {spec_path}")

    fmt = getattr(args, "format", None)
    try:
        result_obj = compile_spec(spec_path, format=fmt)
    except ValueError as e:
        error(str(e))

    # Protobuf directories return a list
    if isinstance(result_obj, list):
        result = "\n---\n\n".join(s.to_lap(lean=args.lean) for s in result_obj)
        total_eps = sum(len(s.endpoints) for s in result_obj)
        label = f"{len(result_obj)} specs, {total_eps} endpoints"
    else:
        result = result_obj.to_lap(lean=args.lean)
        label = f"{len(result_obj.endpoints)} endpoints"

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result, encoding='utf-8')
        info(f"Compiled {Path(spec_path).name} -> {args.output}")
        info(f"{label} | {len(result):,} chars | {'lean' if args.lean else 'standard'} mode")
    else:
        print(result)


def cmd_validate(args):
    """Validate LAP output for information loss."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "benchmarks"))
    from validate import validate_schema_completeness, print_results

    if not Path(args.spec).exists():
        error(f"File not found: {args.spec}")

    heading("LAP Semantic Validation")
    results = validate_schema_completeness(args.spec)

    if HAS_RICH:
        table = Table(title="Validation Results", box=box.SIMPLE_HEAVY)
        table.add_column("Check", style="cyan")
        table.add_column("Result", justify="right")
        table.add_column("Status", justify="center")

        total_ep = results["total_endpoints"]
        comp_ep = results["compiled_endpoints"]
        ep_pct = (comp_ep / total_ep * 100) if total_ep else 100
        table.add_row("Endpoints", f"{comp_ep}/{total_ep} ({ep_pct:.0f}%)", "✅" if ep_pct == 100 else "⚠️")

        total_p = results["total_params"]
        cap_p = results["captured_params"]
        p_pct = (cap_p / total_p * 100) if total_p else 100
        table.add_row("Parameters", f"{cap_p}/{total_p} ({p_pct:.0f}%)", "✅" if p_pct == 100 else "⚠️")

        total_e = results["total_error_codes"]
        cap_e = results["captured_error_codes"]
        e_pct = (cap_e / total_e * 100) if total_e else 100
        table.add_row("Error Codes", f"{cap_e}/{total_e} ({e_pct:.0f}%)", "✅" if e_pct == 100 else "⚠️")

        console.print(table)

        if ep_pct == 100 and p_pct == 100:
            console.print("\n[bold green]PASS[/] -- Zero information loss!")
        else:
            console.print("\n[bold yellow]PARTIAL[/] -- Some data not captured")
            for m in results["missing_params"][:5]:
                console.print(f"  [red]Missing:[/] {m}")
    else:
        print_results(results)


def cmd_benchmark(args):
    """Benchmark token usage for an API spec."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "benchmarks"))
    from benchmark import run_benchmark

    if not Path(args.spec).exists():
        error(f"File not found: {args.spec}")

    heading(f"Token Benchmark: {Path(args.spec).name}")
    run_benchmark(args.spec)


def cmd_benchmark_all(args):
    """Benchmark all specs in a directory."""
    from lap.core.compilers.openapi import compile_openapi
    from lap.core.utils import count_tokens as count

    specs_dir = Path(args.directory)
    if not specs_dir.is_dir():
        error(f"Not a directory: {args.directory}")

    spec_files = sorted(
        glob.glob(str(specs_dir / "*.yaml")) +
        glob.glob(str(specs_dir / "*.yml")) +
        glob.glob(str(specs_dir / "*.json"))
    )
    spec_files = [f for f in spec_files if "stripe-full" not in f]

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
        info(f"Already logged in as {creds['username']}. Run 'lap logout' first to switch accounts.")
        return

    print(f"Authenticating with {get_registry_url()}...")

    # Create CLI session (pass optional token name)
    body = {}
    if getattr(args, "token_name", None):
        body["name"] = args.token_name
    result = api_request("POST", "/auth/cli/session", body=body if body else None)
    session_id = result["session_id"]
    auth_url = result["auth_url"]

    # Open browser
    print(f"Opening browser for GitHub authorization...")
    webbrowser.open(auth_url)
    print("Waiting for authentication (press Ctrl+C to cancel)...")

    # Poll SSE stream
    token, username = poll_sse_stream(session_id)
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
        print("Not logged in. Run 'lap login' to authenticate.")
        return

    result = api_request("GET", "/auth/me", token=token)
    user = result.get("user", {})
    info(f"Logged in as {user.get('username', 'unknown')}")


def cmd_publish(args):
    """Compile and publish a spec to the registry."""
    from lap.cli.auth import get_token, api_request
    from lap.core.compilers import compile as compile_spec

    token = get_token()
    if not token:
        error("Not logged in. Run 'lap login' first.")

    spec_path = args.spec
    if not Path(spec_path).exists():
        error(f"File not found: {spec_path}")

    # Determine spec name
    name = args.name
    if not name:
        # Try to extract from spec
        try:
            result_obj = compile_spec(spec_path)
            if isinstance(result_obj, list):
                error("Protobuf directories produce multiple specs. Use --name to specify which to publish.")
            name = result_obj.api_name.lower().replace(" ", "-").replace("_", "-")
            # Strip non-alphanumeric except hyphens
            name = "".join(c for c in name if c.isalnum() or c == "-").strip("-")
        except Exception as e:
            error(f"Could not auto-detect spec name: {e}. Use --name to specify.")

    if not name:
        error("Could not determine spec name. Use --name to specify.")

    # Compile spec
    print(f"Compiling {Path(spec_path).name}...")
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

    from urllib.parse import quote
    print(f"Publishing {name} to provider {args.provider}...")
    result = api_request("POST", f"/v1/apis/{quote(name, safe='')}", body=body, token=token)
    info(f"Published {name} v{result.get('version', '?')} (provider: {result.get('provider', args.provider)})")


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
        prog="lap",
        description="LAP -- LeanAgent Protocol CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'lap <command> --help' for more info on a command.",
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

    # validate
    p = sub.add_parser("validate", help="Validate LAP for zero info loss")
    p.add_argument("spec", help="Path to OpenAPI spec")

    # benchmark
    p = sub.add_parser("benchmark", help="Benchmark token usage for a spec")
    p.add_argument("spec", help="Path to OpenAPI spec")

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
    p.add_argument("--provider", required=True, help="Provider slug (e.g. stripe)")
    p.add_argument("--name", help="Override spec name (auto-detected if omitted)")
    p.add_argument("--source-url", help="Upstream spec URL")

    args = parser.parse_args()

    commands = {
        "compile": cmd_compile,
        "validate": cmd_validate,
        "benchmark": cmd_benchmark,
        "benchmark-all": cmd_benchmark_all,
        "inspect": cmd_inspect,
        "convert": cmd_convert,
        "diff": cmd_diff,
        "login": cmd_login,
        "logout": cmd_logout,
        "whoami": cmd_whoami,
        "publish": cmd_publish,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
