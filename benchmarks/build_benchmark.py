#!/usr/bin/env python3
"""
Build the big benchmark harness for LAP evaluation.
"""

import sys
import json
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lap.core.compilers.openapi import compile_openapi

# Spec selections by tier
SPEC_CONFIG = {
    "small": [
        "stripe-charges.yaml",
        "github-core.yaml", 
        "discord.yaml"
    ],
    "medium": [
        "twitter.yaml",
        "resend.yaml",
        "launchdarkly.yaml",
        "petstore.yaml"
    ],
    "large": [
        "snyk.yaml",
        "hetzner.yaml",
        "plaid.yaml"
    ]
}

# Task templates for each spec
TASK_TEMPLATES = {
    "stripe-charges": [
        {"task": "Create a new charge for $50 USD for customer cus_123", "endpoint": "POST /v1/charges"},
        {"task": "Retrieve the details of charge ch_abc123", "endpoint": "GET /v1/charges/{charge}"},
        {"task": "Update the description of charge ch_xyz789 to 'Updated payment'", "endpoint": "POST /v1/charges/{charge}"},
        {"task": "Capture an authorized charge ch_capture123", "endpoint": "POST /v1/charges/{charge}/capture"},
        {"task": "List all charges with a limit of 10", "endpoint": "GET /v1/charges"}
    ],
    "github-core": [
        {"task": "Get details of the repository 'octocat/Hello-World'", "endpoint": "GET /repos/{owner}/{repo}"},
        {"task": "List issues for repository 'owner/repo'", "endpoint": "GET /repos/{owner}/{repo}/issues"},
        {"task": "Create a new issue in repository 'myuser/myrepo' with title 'Bug report'", "endpoint": "POST /repos/{owner}/{repo}/issues"},
        {"task": "List pull requests for repository 'owner/repo'", "endpoint": "GET /repos/{owner}/{repo}/pulls"},
        {"task": "Create a new pull request in repository 'owner/repo'", "endpoint": "POST /repos/{owner}/{repo}/pulls"}
    ],
    "discord": [
        {"task": "Send a message 'Hello World' to channel 123456789", "endpoint": "POST /channels/{channel_id}/messages"},
        {"task": "Create a new channel in guild 987654321", "endpoint": "POST /guilds/{guild_id}/channels"},
        {"task": "List all members in guild 555666777", "endpoint": "GET /guilds/{guild_id}/members"},
        {"task": "Add a thumbs up reaction to message 111222 in channel 333444", "endpoint": "PUT /channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"},
        {"task": "Send an announcement message to channel 999888777", "endpoint": "POST /channels/{channel_id}/messages"}
    ],
    "twitter": [
        {"task": "Post a new tweet with text 'Hello Twitter'", "endpoint": "POST /2/tweets"},
        {"task": "Get details of tweet with ID 123456789", "endpoint": "GET /2/tweets/{id}"},
        {"task": "Delete tweet with ID 987654321", "endpoint": "DELETE /2/tweets/{id}"},
        {"task": "Get the authenticated user's profile", "endpoint": "GET /2/users/me"},
        {"task": "Search recent tweets for keyword 'AI'", "endpoint": "GET /2/tweets/search/recent"}
    ],
    "resend": [
        {"task": "Send an email to user@example.com with subject 'Test'", "endpoint": "POST /emails"},
        {"task": "Get details of email with ID abc123", "endpoint": "GET /emails/{email_id}"},
        {"task": "List all emails sent", "endpoint": "GET /emails"},
        {"task": "Create a new API key", "endpoint": "POST /api-keys"},
        {"task": "List all domains configured", "endpoint": "GET /domains"}
    ],
    "launchdarkly": [
        {"task": "Get root information about the API", "endpoint": "GET /"},
        {"task": "List all relay proxy auto-configurations", "endpoint": "GET /account/relay-auto-configs"},
        {"task": "Create a new relay proxy auto-configuration", "endpoint": "POST /account/relay-auto-configs"},
        {"task": "Get details of relay proxy config with ID abc123", "endpoint": "GET /account/relay-auto-configs/{id}"},
        {"task": "Delete relay proxy configuration with ID xyz789", "endpoint": "DELETE /account/relay-auto-configs/{id}"}
    ],
    "petstore": [
        {"task": "Add a new pet to the store with name 'Fluffy'", "endpoint": "POST /pet"},
        {"task": "Get details of pet with ID 123", "endpoint": "GET /pet/{petId}"},
        {"task": "Update an existing pet's information", "endpoint": "PUT /pet"},
        {"task": "Find pets by status 'available'", "endpoint": "GET /pet/findByStatus"},
        {"task": "Delete pet with ID 456", "endpoint": "DELETE /pet/{petId}"}
    ],
    "snyk": [
        {"task": "Get audit logs for group grp123", "endpoint": "POST /group/{groupId}/audit"},
        {"task": "List all members in group grp456", "endpoint": "GET /group/{groupId}/members"},
        {"task": "List all organizations in group grp789", "endpoint": "GET /group/{groupId}/orgs"},
        {"task": "Get settings for group grp111", "endpoint": "GET /group/{groupId}/settings"},
        {"task": "Update settings for group grp222", "endpoint": "PUT /group/{groupId}/settings"}
    ],
    "hetzner": [
        {"task": "List all servers", "endpoint": "GET /servers"},
        {"task": "Get details of server with ID 12345", "endpoint": "GET /servers/{id}"},
        {"task": "Create a new server", "endpoint": "POST /servers"},
        {"task": "Power on server 67890", "endpoint": "POST /servers/{id}/actions/poweron"},
        {"task": "Delete server 11111", "endpoint": "DELETE /servers/{id}"}
    ],
    "plaid": [
        {"task": "Create a link token for initializing Plaid Link", "endpoint": "POST /link/token/create"},
        {"task": "Exchange a public token for an access token", "endpoint": "POST /item/public_token/exchange"},
        {"task": "Get account balances", "endpoint": "POST /accounts/balance/get"},
        {"task": "Get auth data for account", "endpoint": "POST /auth/get"},
        {"task": "Get transactions for an item", "endpoint": "POST /transactions/get"}
    ]
}


def parse_openapi_endpoints(spec_path):
    """Extract all endpoints from an OpenAPI spec."""
    with open(spec_path) as f:
        spec = yaml.safe_load(f)
    
    endpoints = []
    paths = spec.get('paths', {})
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                summary = details.get('summary', details.get('operationId', 'No description'))
                endpoints.append({
                    'method': method.upper(),
                    'path': path,
                    'summary': summary
                })
    
    return endpoints


def validate_task_endpoints(tasks, endpoints):
    """Verify that all tasks reference actual endpoints."""
    endpoint_lookup = {f"{ep['method']} {ep['path']}" for ep in endpoints}
    
    valid = []
    for task in tasks:
        expected = task['endpoint']
        # Normalize path parameters for matching
        for ep_key in endpoint_lookup:
            if compare_endpoints(expected, ep_key):
                valid.append(True)
                break
        else:
            valid.append(False)
    
    return all(valid), valid


def compare_endpoints(expected, actual):
    """Compare endpoints, accounting for path parameters."""
    exp_parts = expected.split()
    act_parts = actual.split()
    
    if len(exp_parts) != 2 or len(act_parts) != 2:
        return False
    
    if exp_parts[0] != act_parts[0]:  # Method must match
        return False
    
    # Compare paths segment by segment
    exp_path = exp_parts[1].strip('/').split('/')
    act_path = act_parts[1].strip('/').split('/')
    
    if len(exp_path) != len(act_path):
        return False
    
    for e, a in zip(exp_path, act_path):
        # If either is a parameter placeholder, consider it a match
        if (e.startswith('{') and e.endswith('}')) or (a.startswith('{') and a.endswith('}')):
            continue
        if e != a:
            return False
    
    return True


def build_benchmark():
    """Build the complete benchmark harness."""
    examples_dir = Path('/data/workspace/lap-poc/examples')
    output_dir = Path('/data/workspace/lap-poc/benchmarks/big_benchmark')
    output_dir.mkdir(exist_ok=True, parents=True)
    
    benchmark_config = {"specs": []}
    summary_table = []
    
    for tier, specs in SPEC_CONFIG.items():
        for spec_file in specs:
            spec_name = spec_file.replace('.yaml', '')
            spec_path = examples_dir / spec_file
            
            print(f"\n{'='*60}")
            print(f"Processing: {spec_name} ({tier})")
            print('='*60)
            
            # Step 1: Parse endpoints
            print("Step 1: Parsing endpoints...")
            endpoints = parse_openapi_endpoints(spec_path)
            print(f"  Found {len(endpoints)} endpoints")
            
            # Get tasks for this spec
            tasks = TASK_TEMPLATES.get(spec_name, [])
            if not tasks:
                print(f"  WARNING: No tasks defined for {spec_name}")
                continue
            
            # Validate tasks
            all_valid, valid_flags = validate_task_endpoints(tasks, endpoints)
            print(f"  Task validation: {sum(valid_flags)}/{len(tasks)} valid")
            
            # Step 2: Compile LAP
            print("Step 2: Compiling LAP...")
            try:
                doc = compile_openapi(str(spec_path))
                lap = doc.to_lap(lean=False)
            except Exception as e:
                print(f"  ERROR compiling LAP: {e}")
                continue
            
            # Step 3: Read verbose spec
            with open(spec_path) as f:
                verbose_spec = f.read()
            
            verbose_chars = len(verbose_spec)
            lap_chars = len(lap)
            compression_ratio = round(verbose_chars / lap_chars, 2) if lap_chars > 0 else 0
            
            print(f"  Verbose: {verbose_chars:,} chars")
            print(f"  LAP: {lap_chars:,} chars")
            print(f"  Compression: {compression_ratio}x")
            
            # Step 4: Generate prompt files
            print("Step 3: Generating prompt files...")
            
            task_list = "\n".join([f"{i+1}. {t['task']}" for i, t in enumerate(tasks)])
            
            prompt_template = """You are an API integration assistant. Given API documentation and tasks, write the exact API call (curl command) for each.

Format: TASK 1: <curl command>  through TASK 5: <curl command>

--- API DOCUMENTATION ---
{doc}
--- END DOCUMENTATION ---

TASKS:
{tasks}
"""
            
            # Verbose prompt
            verbose_prompt = prompt_template.format(doc=verbose_spec, tasks=task_list)
            verbose_file = output_dir / f"verbose_{spec_name}.txt"
            with open(verbose_file, 'w') as f:
                f.write(verbose_prompt)
            
            # LAP prompt
            lap_prompt = prompt_template.format(doc=lap, tasks=task_list)
            lap_file = output_dir / f"lap_{spec_name}.txt"
            with open(lap_file, 'w') as f:
                f.write(lap_prompt)
            
            print(f"  Written: {verbose_file.name}")
            print(f"  Written: {lap_file.name}")
            
            # Add to config
            spec_config = {
                "name": spec_name,
                "tier": tier,
                "endpoints": len(endpoints),
                "verbose_chars": verbose_chars,
                "lap_chars": lap_chars,
                "compression_ratio": compression_ratio,
                "tasks": [{"task": t['task'], "expect_endpoint": t['endpoint']} for t in tasks]
            }
            benchmark_config["specs"].append(spec_config)
            
            # Add to summary
            summary_table.append({
                "spec": spec_name,
                "tier": tier,
                "endpoints": len(endpoints),
                "verbose_size": verbose_chars,
                "lap_size": lap_chars,
                "ratio": compression_ratio,
                "tasks_valid": f"{sum(valid_flags)}/{len(tasks)}"
            })
    
    # Write benchmark config
    config_file = Path('/data/workspace/lap-poc/benchmarks/big_benchmark_config.json')
    with open(config_file, 'w') as f:
        json.dump(benchmark_config, f, indent=2)
    
    print(f"\n{'='*60}")
    print("BENCHMARK BUILD COMPLETE")
    print('='*60)
    print(f"\nConfig written to: {config_file}")
    print(f"Prompt files written to: {output_dir}/")
    
    # Print summary table
    print("\n" + "="*100)
    print("SUMMARY TABLE")
    print("="*100)
    print(f"{'Spec':<20} {'Tier':<8} {'Endpoints':<10} {'Verbose':<12} {'LAP':<12} {'Ratio':<8} {'Valid':<10}")
    print("-"*100)
    
    for row in summary_table:
        print(f"{row['spec']:<20} {row['tier']:<8} {row['endpoints']:<10} "
              f"{row['verbose_size']:<12,} {row['lap_size']:<12,} "
              f"{row['ratio']:<8} {row['tasks_valid']:<10}")
    
    print("="*100)
    print(f"\nTotal specs: {len(summary_table)}")
    print(f"Total tasks: {sum(len(s['tasks']) for s in benchmark_config['specs'])}")
    
    return benchmark_config, summary_table


if __name__ == '__main__':
    build_benchmark()
