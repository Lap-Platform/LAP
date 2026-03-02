#!/usr/bin/env python3
"""
Live Agent Benchmark - Generate prompts for head-to-head LLM testing.

This script:
1. Loads full_test_tasks.yaml
2. Picks the first 2 docs per protocol (10 docs total)
3. For each doc, compiles both verbose (raw) and LAP versions
4. Generates 20 prompt files (verbose_<protocol>_<n>.txt, lap_<protocol>_<n>.txt)
"""

import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Add src to path

from lap.core.compilers.openapi import compile_openapi
from lap.core.compilers.graphql import compile_graphql
from lap.core.compilers.asyncapi import compile_asyncapi
from lap.core.compilers.postman import compile_postman
from lap.core.compilers.protobuf import compile_protobuf


PROMPT_TEMPLATE = """You are an API integration assistant. You will be given API documentation and a series of tasks.
For each task, write the exact API call (curl command for REST, GraphQL query, protobuf RPC call, etc).

Format your response as:
TASK 1: <your api call>
TASK 2: <your api call>
... etc

--- API DOCUMENTATION ---
{doc}
--- END DOCUMENTATION ---

TASKS:
{tasks}
"""


def load_tasks():
    """Load the full test tasks YAML."""
    tasks_path = Path(__file__).parent / "full_test_tasks.yaml"
    with open(tasks_path) as f:
        return yaml.safe_load(f)


def get_spec_path(spec_rel_path):
    """Convert relative spec path to absolute."""
    return Path(__file__).parent.parent / spec_rel_path


def compile_doc(spec_path, protocol):
    """Compile a spec to LAP format based on protocol type."""
    spec_path = str(spec_path)
    
    try:
        if protocol == "openapi":
            doc = compile_openapi(spec_path)
            return doc.to_lap(lean=False)
        elif protocol == "graphql":
            doc = compile_graphql(spec_path)
            return doc.to_lap(lean=False)
        elif protocol == "asyncapi":
            doc = compile_asyncapi(spec_path)
            return doc.to_lap(lean=False)
        elif protocol == "postman":
            doc = compile_postman(spec_path)
            return doc.to_lap(lean=False)
        elif protocol == "protobuf":
            doc = compile_protobuf(spec_path)
            return doc.to_lap(lean=False)
        else:
            raise ValueError(f"Unknown protocol: {protocol}")
    except Exception as e:
        print(f"ERROR compiling {spec_path}: {e}")
        return None


def format_tasks(tasks_list):
    """Format tasks list as numbered text."""
    lines = []
    for i, task_data in enumerate(tasks_list, 1):
        lines.append(f"{i}. {task_data['task']}")
    return "\n".join(lines)


def generate_prompts():
    """Generate all prompt files."""
    data = load_tasks()
    protocols = data["protocols"]
    
    output_dir = Path(__file__).parent / "live_prompts"
    output_dir.mkdir(exist_ok=True)
    
    stats = {
        "total_prompts": 0,
        "by_protocol": {}
    }
    
    print("=" * 70)
    print("LAP Live Agent Benchmark - Prompt Generation")
    print("=" * 70)
    print()
    
    for protocol_name, protocol_data in protocols.items():
        docs_list = protocol_data["docs"]
        
        # Pick first 2 docs
        selected_docs = docs_list[:2]
        
        print(f"📋 Protocol: {protocol_name.upper()}")
        print(f"   Selected {len(selected_docs)} docs")
        
        protocol_count = 0
        
        for doc_idx, doc_data in enumerate(selected_docs):
            spec_rel_path = doc_data["spec"]
            api_name = doc_data["api"]
            tasks_list = doc_data["tasks"]
            
            spec_path = get_spec_path(spec_rel_path)
            
            if not spec_path.exists():
                print(f"   ⚠️  SKIP: {spec_path} not found")
                continue
            
            print(f"   📄 Doc {doc_idx}: {api_name}")
            print(f"      Spec: {spec_rel_path}")
            print(f"      Tasks: {len(tasks_list)}")
            
            # Load raw spec content (verbose)
            with open(spec_path, 'r') as f:
                verbose_doc = f.read()
            
            # Compile LAP version
            lap_doc = compile_doc(spec_path, protocol_name)
            
            if lap_doc is None:
                print(f"      ⚠️  SKIP: Compilation failed")
                continue
            
            # Format tasks
            tasks_text = format_tasks(tasks_list)
            
            # Generate verbose prompt
            verbose_prompt = PROMPT_TEMPLATE.format(
                doc=verbose_doc,
                tasks=tasks_text
            )
            
            # Generate LAP prompt
            lap_prompt = PROMPT_TEMPLATE.format(
                doc=lap_doc,
                tasks=tasks_text
            )
            
            # Save prompts
            verbose_filename = f"verbose_{protocol_name}_{doc_idx}.txt"
            lap_filename = f"lap_{protocol_name}_{doc_idx}.txt"
            
            verbose_path = output_dir / verbose_filename
            lap_path = output_dir / lap_filename
            
            with open(verbose_path, 'w') as f:
                f.write(verbose_prompt)
            
            with open(lap_path, 'w') as f:
                f.write(lap_prompt)
            
            print(f"      ✅ Generated: {verbose_filename} ({len(verbose_prompt):,} chars)")
            print(f"      ✅ Generated: {lap_filename} ({len(lap_prompt):,} chars)")
            print()
            
            protocol_count += 2
            stats["total_prompts"] += 2
        
        stats["by_protocol"][protocol_name] = protocol_count
        print()
    
    # Print summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total prompts generated: {stats['total_prompts']}")
    print(f"Output directory: {output_dir}")
    print()
    print("Breakdown by protocol:")
    for protocol, count in stats["by_protocol"].items():
        print(f"  {protocol.ljust(12)}: {count} prompts ({count//2} docs)")
    print()
    print("✅ All prompts generated successfully!")
    print()


if __name__ == "__main__":
    generate_prompts()
