"""
Layer 2 LLM enhancement for skill generation.

Isolated module -- imported only when --layer 2 is requested.
Primary path: claude CLI subprocess (uses existing Claude Code subscription).
Fallback path: anthropic SDK (for CI environments like GitHub Actions).
"""

import shutil
import subprocess
import sys

from lap.core.compilers.skill import SkillOutput


ENHANCE_PROMPT = """You are enhancing a Claude Code skill for an API. Given the LAP spec below,
generate the following sections in markdown:

1. **Question Mapping** (10-15 entries): Natural language questions mapped to API endpoints.
   Format each as: - "Question?" -> METHOD /path
   Cover common use cases, edge cases, and multi-step workflows.

2. **Response Tips** (one line per endpoint category): How to interpret responses.
   Focus on pagination, error patterns, and nested objects.

3. **Anomaly Flags**: What should an agent surface proactively?
   (e.g., rate limits approaching, deprecated fields, unusual status codes)

4. **Playbook** (3-5 common workflows): Step-by-step guides for typical tasks.
   Format as numbered lists under descriptive headings.

Return ONLY the markdown content -- no preamble, no code fences.

LAP Spec:
{spec_text}
"""


def _has_claude_cli() -> bool:
    """Check whether the claude CLI is on PATH."""
    return shutil.which("claude") is not None


def _enhance_via_cli(prompt: str) -> str:
    """Call claude CLI as a subprocess, piping the prompt via stdin."""
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "opus", "--output-format", "text", "--verbose"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute timeout
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude CLI timed out after 5 minutes.")

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "unknown error"
        raise RuntimeError(f"claude CLI exited with code {result.returncode}: {stderr}")

    return result.stdout


def _enhance_via_sdk(prompt: str, api_key: str = None) -> str:
    """Fallback: call the Anthropic SDK directly (for CI environments)."""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "Layer 2 requires either the claude CLI or the 'anthropic' package. "
            "Install the CLI (https://docs.anthropic.com/en/docs/claude-code) "
            "or run: pip install anthropic"
        )

    client_kwargs = {}
    if api_key:
        client_kwargs["api_key"] = api_key

    client = anthropic.Anthropic(**client_kwargs)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APITimeoutError:
        raise RuntimeError("Anthropic API timed out. Check your network connection and try again.")
    except anthropic.RateLimitError:
        raise RuntimeError("Anthropic API rate limit reached. Wait a moment and try again.")
    except anthropic.APIError as e:
        raise RuntimeError(f"Anthropic API error: {e}")

    return message.content[0].text


def enhance_skill(spec, skill: SkillOutput, api_key: str = None) -> SkillOutput:
    """Add LLM-generated content to a Layer 1 skill.

    Primary: claude CLI subprocess. Fallback: anthropic SDK.
    Raises ImportError if neither is available, RuntimeError on failure.
    """
    from lap.core.formats.lap import LAPSpec
    from lap.core.utils import count_tokens

    # Generate lean spec text for context
    spec_text = spec.to_lap(lean=True)

    # Guard against oversized prompts
    prompt_tokens = count_tokens(spec_text)
    if prompt_tokens > 80_000:
        print(
            f"Warning: spec is {prompt_tokens:,} tokens, exceeding 80k limit. "
            "Returning Layer 1 skill unchanged.",
            file=sys.stderr,
        )
        return skill

    prompt = ENHANCE_PROMPT.format(spec_text=spec_text)

    # Primary path: claude CLI
    if _has_claude_cli():
        enhanced_content = _enhance_via_cli(prompt)
    else:
        # Fallback: anthropic SDK (deferred import inside _enhance_via_sdk)
        enhanced_content = _enhance_via_sdk(prompt, api_key)

    # Replace mechanical sections in SKILL.md with LLM-enhanced ones
    skill_md = skill.file_map["SKILL.md"]

    # Replace Common Questions section
    skill_md = _replace_section(skill_md, "Common Questions", enhanced_content)

    # Update file map
    new_file_map = dict(skill.file_map)
    new_file_map["SKILL.md"] = skill_md

    # Recalculate tokens
    total_tokens = sum(count_tokens(content) for content in new_file_map.values())

    return SkillOutput(
        name=skill.name,
        file_map=new_file_map,
        token_count=total_tokens,
        endpoint_count=skill.endpoint_count,
    )


def _replace_section(md: str, section_name: str, new_content: str) -> str:
    """Replace everything from ## {section_name} to the next ## heading."""
    import re
    pattern = rf'(## {re.escape(section_name)}\n).*?(?=\n## |\Z)'
    replacement = f"## Enhanced Skill Content\n{new_content}\n"
    result = re.sub(pattern, replacement, md, flags=re.DOTALL)
    return result
