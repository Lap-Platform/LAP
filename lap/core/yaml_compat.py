"""Shared YAML loader for LAP compilers.

Handles real-world API spec edge cases that trip up the default SafeLoader.
"""

import re as _re

import yaml


class _SafeLoaderCompat(yaml.SafeLoader):
    """YAML loader handling real-world API spec edge cases.

    Fixes:
    - Bare = in enums (YAML 1.1 value tag) e.g. Jira operator enums
    - NO/YES/ON/OFF parsed as booleans e.g. country code NO (Norway)
    - Unknown/custom YAML tags e.g. !include, AWS CloudFormation
    """
    pass


# Handle unknown tags gracefully (existing behavior)
_SafeLoaderCompat.add_constructor(
    None,
    lambda loader, node: (
        loader.construct_mapping(node) if isinstance(node, yaml.MappingNode)
        else loader.construct_sequence(node) if isinstance(node, yaml.SequenceNode)
        else loader.construct_scalar(node)
    )
)

# Handle bare = (YAML 1.1 value tag)
_SafeLoaderCompat.add_constructor(
    'tag:yaml.org,2002:value',
    lambda loader, node: loader.construct_scalar(node)
)

# Restrict booleans to only true/false (YAML 1.2 behavior)
# Prevents NO->False, YES->True, ON->True, OFF->False
#
# We must copy the inherited resolver dict and strip the old YAML 1.1 bool
# entries before adding our narrower pattern, because add_implicit_resolver
# only appends and the old pattern would still match first.
_SafeLoaderCompat.yaml_implicit_resolvers = {
    k: [(tag, regexp) for tag, regexp in v if tag != 'tag:yaml.org,2002:bool']
    for k, v in _SafeLoaderCompat.yaml_implicit_resolvers.copy().items()
}
# Remove keys that became empty after stripping
_SafeLoaderCompat.yaml_implicit_resolvers = {
    k: v for k, v in _SafeLoaderCompat.yaml_implicit_resolvers.items() if v
}
_SafeLoaderCompat.add_implicit_resolver(
    'tag:yaml.org,2002:bool',
    _re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$'),
    list('tTfF')
)
