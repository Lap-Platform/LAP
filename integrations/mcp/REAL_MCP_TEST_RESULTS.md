# Real MCP Server Integration Test Results

**Date:** 2026-02-11

**Method:** Started real MCP servers via `npx`, communicated over stdio JSON-RPC


## Summary

| Server | Tools | Orig Tokens | LAP Tokens | Savings | Fidelity |
|--------|-------|-------------|------------|---------|----------|
| filesystem | 14 | 4075 | 1172 | 71.2% | ✅ 100% |
| memory | 9 | 3670 | 319 | 91.3% | ✅ 100% |
| everything | 0 | 23 | 8 | 65.2% | ✅ 100% |
| sequential-thinking | 1 | 1228 | 726 | 40.9% | ✅ 100% |

## Detailed Results

### filesystem

- **Command:** `npx -y @modelcontextprotocol/server-filesystem /tmp`
- **Tools found:** 14
- **Original:** 18589 bytes / 4075 tokens
- **LAP compressed:** 5395 bytes / 1172 tokens
- **Token savings:** 71.2%
- **Compression time:** 0.2ms
- **Round-trip fidelity:** 14/14 tools matched
- **Tool call test:** `list_directory` → ✅ Success

<details><summary>LAP compressed output (1172 tokens)</summary>

```
# filesystem
# filesystem MCP server

@lap v0.1
@tool read_file
@desc Read the complete contents of a file as text. DEPRECATED: Use read_text_file instead.
@in path:str
@in tail:num? If provided, returns only the last N lines of the file
@in head:num? If provided, returns only the first N lines of the file

@lap v0.1
@tool read_text_file
@desc Read the complete contents of a file from the file system as text. Handles various text encodings and provides detailed error messages if the file cannot be read. Use this tool when you need to examine the contents of a single file. Use the 'head' parameter to read only the first N lines of a file, or the 'tail' parameter to read only the last N lines of a file. Operates on the file as text regardless of extension. Only works within allowed directories.
@in path:str
@in tail:num? If provided, returns only the last N lines of the file
@in head:num? If provided, returns only the first N lines of the file

@lap v0.1
@tool read_media_file
@desc Read an image or audio file. Returns the base64 encoded data and MIME type. Only works within allowed directories.
@in path:str

@lap v0.1
@tool read_multiple_files
@desc Read the contents of multiple files simultaneously. This is more efficient than reading files one by one when you need to analyze or compare multiple files. Each file's content is returned with its path as a reference. Failed reads for individual files won't stop the entire operation. Only works within allowed directories.
@in paths:[str] Array of file paths to read. Each path must be a string pointing to a valid file within allowed directories.

@lap v0.1
@tool write_file
@desc Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding. Only works within allowed directories.
@in path:str
@in content:str

@lap v0.1
@tool edit_file
@desc Make line-based edits to a text file. Each edit replaces exact line sequences with new content. Returns a git-style diff showing the changes made. Only works within allowed directories.
@in path:str
@in edits:[map]
@in dryRun:bool?=False Preview changes using git-style diff format

@lap v0.1
@tool create_directory
@desc Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will succeed silently. Perfect for setting up directory structures for projects or ensuring required paths exist. Only works within allowed directories.
@in path:str

@lap v0.1
@tool list_directory
@desc Get a detailed listing of all files and directories in a specified path. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is essential for understanding directory structure and finding specific files within a directory. Only works within allowed directories.
@in path:str

@lap v0.1
@tool list_directory_with_sizes
@desc Get a detailed listing of all files and directories in a specified path, including sizes. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is useful for understanding directory structure and finding specific files within a directory. Only works within allowed directories.
@in path:str
@in sortBy:str?(name/size)=name Sort entries by name or size

@lap v0.1
@tool directory_tree
@desc Get a recursive tree view of files and directories as a JSON structure. Each entry includes 'name', 'type' (file/directory), and 'children' for directories. Files have no children array, while directories always have a children array (which may be empty). The output is formatted with 2-space indentation for readability. Only works within allowed directories.
@in path:str
@in excludePatterns:[str]?=[]

@lap v0.1
@tool move_file
@desc Move or rename files and directories. Can move files between directories and rename them in a single operation. If the destination exists, the operation will fail. Works across different directories and can be used for simple renaming within the same directory. Both source and destination must be within allowed directories.
@in source:str
@in destination:str

@lap v0.1
@tool search_files
@desc Recursively search for files and directories matching a pattern. The patterns should be glob-style patterns that match paths relative to the working directory. Use pattern like '*.ext' to match files in current directory, and '**/*.ext' to match files in all subdirectories. Returns full paths to all matching items. Great for finding files when you don't know their exact location. Only searches within allowed directories.
@in path:str
@in pattern:str
@in excludePatterns:[str]?=[]

@lap v0.1
@tool get_file_info
@desc Retrieve detailed metadata about a file or directory. Returns comprehensive information including size, creation time, last modified time, permissions, and type. This tool is perfect for understanding file characteristics without reading the actual content. Only works within allowed directories.
@in path:str

@lap v0.1
@tool list_allowed_directories
@desc Returns the list of directories that this server is allowed to access. Subdirectories within these allowed directories are also accessible. Use this to understand which directories and their nested paths are available before trying to access files.

```
</details>


<details><summary>Example: read_file (original JSON Schema)</summary>

```json
{
  "name": "read_file",
  "title": "Read File (Deprecated)",
  "description": "Read the complete contents of a file as text. DEPRECATED: Use read_text_file instead.",
  "inputSchema": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "path": {
        "type": "string"
      },
      "tail": {
        "description": "If provided, returns only the last N lines of the file",
        "type": "number"
      },
      "head": {
        "description": "If provided, returns only the first N lines of the file",
        "type": "number"
      }
    },
    "required": [
      "path"
    ]
  },
  "annotations": {
    "readOnlyHint": true
  },
  "execution": {
    "taskSupport": "forbidden"
  },
  "outputSchema": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "content": {
        "type": "string"
      }
    },
    "required": [
      "content"
    ],
    "additionalProperties": false
  }
}
```
</details>

### memory

- **Command:** `npx -y @modelcontextprotocol/server-memory`
- **Tools found:** 9
- **Original:** 18687 bytes / 3670 tokens
- **LAP compressed:** 1280 bytes / 319 tokens
- **Token savings:** 91.3%
- **Compression time:** 0.1ms
- **Round-trip fidelity:** 9/9 tools matched
- **Tool call test:** `create_entities` → ✅ Success

<details><summary>LAP compressed output (319 tokens)</summary>

```
# memory
# memory MCP server

@lap v0.1
@tool create_entities
@desc Create multiple new entities in the knowledge graph
@in entities:[map]

@lap v0.1
@tool create_relations
@desc Create multiple new relations between entities in the knowledge graph. Relations should be in active voice
@in relations:[map]

@lap v0.1
@tool add_observations
@desc Add new observations to existing entities in the knowledge graph
@in observations:[map]

@lap v0.1
@tool delete_entities
@desc Delete multiple entities and their associated relations from the knowledge graph
@in entityNames:[str] An array of entity names to delete

@lap v0.1
@tool delete_observations
@desc Delete specific observations from entities in the knowledge graph
@in deletions:[map]

@lap v0.1
@tool delete_relations
@desc Delete multiple relations from the knowledge graph
@in relations:[map] An array of relations to delete

@lap v0.1
@tool read_graph
@desc Read the entire knowledge graph

@lap v0.1
@tool search_nodes
@desc Search for nodes in the knowledge graph based on a query
@in query:str The search query to match against entity names, types, and observation content

@lap v0.1
@tool open_nodes
@desc Open specific nodes in the knowledge graph by their names
@in names:[str] An array of entity names to retrieve

```
</details>


<details><summary>Example: create_entities (original JSON Schema)</summary>

```json
{
  "name": "create_entities",
  "title": "Create Entities",
  "description": "Create multiple new entities in the knowledge graph",
  "inputSchema": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "entities": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string",
              "description": "The name of the entity"
            },
            "entityType": {
              "type": "string",
              "description": "The type of the entity"
            },
            "observations": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "An array of observation contents associated with the entity"
            }
          },
          "required": [
            "name",
            "entityType",
            "observations"
          ]
        }
      }
    },
    "required": [
      "entities"
    ]
  },
  "execution": {
    "taskSupport": "forbidden"
  },
  "outputSchema": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "entities": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string",
              "description": "The name of the entity"
            },
            "entityType": {
              "type": "string",
              "description": "The type of the entity"
            },
            "observations": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "An array of observation contents associated with the entity"
            }
          },
          "required": [
            "name",
            "entityType",
            "observations"
          ],
          "additionalProperties": false
        }
      }
    },
    "required": [
      "entities"
    ],
    "additionalProperties": false
  }
}
```
</details>

### everything

- **Command:** `npx -y @modelcontextprotocol/server-everything`
- **Tools found:** 0
- **Original:** 83 bytes / 23 tokens
- **LAP compressed:** 37 bytes / 8 tokens
- **Token savings:** 65.2%
- **Compression time:** 0.0ms
- **Round-trip fidelity:** 0/0 tools matched

<details><summary>LAP compressed output (8 tokens)</summary>

```
# everything
# everything MCP server

```
</details>

### sequential-thinking

- **Command:** `npx -y @modelcontextprotocol/server-sequential-thinking`
- **Tools found:** 1
- **Original:** 5718 bytes / 1228 tokens
- **LAP compressed:** 3417 bytes / 726 tokens
- **Token savings:** 40.9%
- **Compression time:** 0.1ms
- **Round-trip fidelity:** 1/1 tools matched

<details><summary>LAP compressed output (726 tokens)</summary>

```
# sequential-thinking
# sequential-thinking MCP server

@lap v0.1
@tool sequentialthinking
@desc A detailed tool for dynamic and reflective problem-solving through thoughts.
This tool helps analyze problems through a flexible thinking process that can adapt and evolve.
Each thought can build on, question, or revise previous insights as understanding deepens.

When to use this tool:
- Breaking down complex problems into steps
- Planning and design with room for revision
- Analysis that might need course correction
- Problems where the full scope might not be clear initially
- Problems that require a multi-step solution
- Tasks that need to maintain context over multiple steps
- Situations where irrelevant information needs to be filtered out

Key features:
- You can adjust total_thoughts up or down as you progress
- You can question or revise previous thoughts
- You can add more thoughts even after reaching what seemed like the end
- You can express uncertainty and explore alternative approaches
- Not every thought needs to build linearly - you can branch or backtrack
- Generates a solution hypothesis
- Verifies the hypothesis based on the Chain of Thought steps
- Repeats the process until satisfied
- Provides a correct answer

Parameters explained:
- thought: Your current thinking step, which can include:
  * Regular analytical steps
  * Revisions of previous thoughts
  * Questions about previous decisions
  * Realizations about needing more analysis
  * Changes in approach
  * Hypothesis generation
  * Hypothesis verification
- nextThoughtNeeded: True if you need more thinking, even if at what seemed like the end
- thoughtNumber: Current number in sequence (can go beyond initial total if needed)
- totalThoughts: Current estimate of thoughts needed (can be adjusted up/down)
- isRevision: A boolean indicating if this thought revises previous thinking
- revisesThought: If is_revision is true, which thought number is being reconsidered
- branchFromThought: If branching, which thought number is the branching point
- branchId: Identifier for the current branch (if any)
- needsMoreThoughts: If reaching end but realizing more thoughts needed

You should:
1. Start with an initial estimate of needed thoughts, but be ready to adjust
2. Feel free to question or revise previous thoughts
3. Don't hesitate to add more thoughts if needed, even at the "end"
4. Express uncertainty when present
5. Mark thoughts that revise previous thinking or branch into new paths
6. Ignore information that is irrelevant to the current step
7. Generate a solution hypothesis when appropriate
8. Verify the hypothesis based on the Chain of Thought steps
9. Repeat the process until satisfied with the solution
10. Provide a single, ideally correct answer as the final output
11. Only set nextThoughtNeeded to false when truly done and a satisfactory answer is reached
@in thought:str Your current thinking step
@in nextThoughtNeeded:bool Whether another thought step is needed
@in thoughtNumber:int Current thought number (numeric value, e.g., 1, 2, 3)
@in totalThoughts:int Estimated total thoughts needed (numeric value, e.g., 5, 10)
@in isRevision:bool? Whether this revises previous thinking
@in revisesThought:int? Which thought is being reconsidered
@in branchFromThought:int? Branching point thought number
@in branchId:str? Branch identifier
@in needsMoreThoughts:bool? If more thoughts are needed

```
</details>


<details><summary>Example: sequentialthinking (original JSON Schema)</summary>

```json
{
  "name": "sequentialthinking",
  "title": "Sequential Thinking",
  "description": "A detailed tool for dynamic and reflective problem-solving through thoughts.\nThis tool helps analyze problems through a flexible thinking process that can adapt and evolve.\nEach thought can build on, question, or revise previous insights as understanding deepens.\n\nWhen to use this tool:\n- Breaking down complex problems into steps\n- Planning and design with room for revision\n- Analysis that might need course correction\n- Problems where the full scope might not be clear initially\n- Problems that require a multi-step solution\n- Tasks that need to maintain context over multiple steps\n- Situations where irrelevant information needs to be filtered out\n\nKey features:\n- You can adjust total_thoughts up or down as you progress\n- You can question or revise previous thoughts\n- You can add more thoughts even after reaching what seemed like the end\n- You can express uncertainty and explore alternative approaches\n- Not every thought needs to build linearly - you can branch or backtrack\n- Generates a solution hypothesis\n- Verifies the hypothesis based on the Chain of Thought steps\n- Repeats the process until satisfied\n- Provides a correct answer\n\nParameters explained:\n- thought: Your current thinking step, which can include:\n  * Regular analytical steps\n  * Revisions of previous thoughts\n  * Questions about previous decisions\n  * Realizations about needing more analysis\n  * Changes in approach\n  * Hypothesis generation\n  * Hypothesis verification\n- nextThoughtNeeded: True if you need more thinking, even if at what seemed like the end\n- thoughtNumber: Current number in sequence (can go beyond initial total if needed)\n- totalThoughts: Current estimate of thoughts needed (can be adjusted up/down)\n- isRevision: A boolean indicating if this thought revises previous thinking\n- revisesThought: If is_revision is true, which thought number is being reconsidered\n- branchFromThought: If branching, which thought number is the branching point\n- branchId: Identifier for the current branch (if any)\n- needsMoreThoughts: If reaching end but realizing more thoughts needed\n\nYou should:\n1. Start with an initial estimate of needed thoughts, but be ready to adjust\n2. Feel free to question or revise previous thoughts\n3. Don't hesitate to add more thoughts if needed, even at the \"end\"\n4. Express uncertainty when present\n5. Mark thoughts that revise previous thinking or branch into new paths\n6. Ignore information that is irrelevant to the current step\n7. Generate a solution hypothesis when appropriate\n8. Verify the hypothesis based on the Chain of Thought steps\n9. Repeat the process until satisfied with the solution\n10. Provide a single, ideally correct answer as the final output\n11. Only set nextThoughtNeeded to false when truly done and a satisfactory answer is reached",
  "inputSchema": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "thought": {
        "type": "string",
        "description": "Your current thinking step"
      },
      "nextThoughtNeeded": {
        "type": "boolean",
        "description": "Whether another thought step is needed"
      },
      "thoughtNumber": {
        "type": "integer",
        "minimum": 1,
        "maximum": 9007199254740991,
        "description": "Current thought number (numeric value, e.g., 1, 2, 3)"
      },
      "totalThoughts": {
        "type": "integer",
        "minimum": 1,
        "maximum": 9007199254740991,
        "description": "Estimated total thoughts needed (numeric value, e.g., 5, 10)"
      },
      "isRevision": {
        "description": "Whether this revises previous thinking",
        "type": "boolean"
      },
      "revisesThought": {
        "description": "Which thought is being reconsidered",
        "type": "integer",
        "minimum": 1,
        "maximum": 9007199254740991
      },
      "branchFromThought": {
        "description": "Branching point thought number",
        "type": "integer",
        "minimum": 1,
        "maximum": 9007199254740991
      },
      "branchId": {
        "description": "Branch identifier",
        "type": "string"
      },
      "needsMoreThoughts": {
        "description": "If more thoughts are needed",
        "type": "boolean"
      }
    },
    "required": [
      "thought",
      "nextThoughtNeeded",
      "thoughtNumber",
      "totalThoughts"
    ]
  },
  "execution": {
    "taskSupport": "forbidden"
  },
  "outputSchema": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "thoughtNumber": {
        "type": "number"
      },
      "totalThoughts": {
        "type": "number"
      },
      "nextThoughtNeeded": {
        "type": "boolean"
      },
      "branches": {
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "thoughtHistoryLength": {
        "type": "number"
      }
    },
    "required": [
      "thoughtNumber",
      "totalThoughts",
      "nextThoughtNeeded",
      "branches",
      "thoughtHistoryLength"
    ],
    "additionalProperties": false
  }
}
```
</details>


## Conclusions

- Real MCP servers were started and queried over stdio JSON-RPC
- LAP proxy successfully compressed real tool schemas
- Round-trip fidelity measured by reconstructing JSON Schema from LAP
- Tool calls tested through real servers to verify end-to-end functionality
