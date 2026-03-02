# OpenAI Chat Completions API Documentation

Source: https://platform.openai.com/docs/api-reference/chat/create (fetched 2026-02-08)

## Create chat completion

`POST https://api.openai.com/v1/chat/completions`

Creates a model response for the given chat conversation. Learn more in the text generation, vision, and audio guides.

### Request body

- **messages** (array, Required): A list of messages comprising the conversation so far. Depending on the model you use, different message types (modalities) are supported, like text, images, and audio.
- **model** (string, Required): Model ID used to generate the response, like gpt-4o or o3. OpenAI offers a wide range of models with different capabilities, performance characteristics, and price points.
- **audio** (object or null, Optional): Parameters for audio output. Required when audio output is requested with modalities: ["audio"].
- **frequency_penalty** (number or null, Optional, Default: 0): Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far.
- **logit_bias** (map, Optional, Default: null): Modify the likelihood of specified tokens appearing in the completion.
- **logprobs** (boolean or null, Optional, Default: false): Whether to return log probabilities of the output tokens or not.
- **max_completion_tokens** (integer or null, Optional): An upper bound for the number of tokens that can be generated for a completion, including visible output tokens and reasoning tokens.
- **metadata** (map, Optional): Set of 16 key-value pairs that can be attached to an object.
- **modalities** (array, Optional): Output types that you would like the model to generate. Default: ["text"].
- **n** (integer or null, Optional, Default: 1): How many chat completion choices to generate for each input message.
- **parallel_tool_calls** (boolean, Optional, Default: true)
- **prediction** (object, Optional): Configuration for a Predicted Output, which can greatly improve response times when large parts of the model response are known ahead of time.
- **presence_penalty** (number or null, Optional, Default: 0): Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far.
- **reasoning_effort** (string, Optional, Default: medium): Constrains effort on reasoning for reasoning models. Supported values: none, minimal, low, medium, high, xhigh.
- **response_format** (object, Optional): An object specifying the format that the model must output. Setting to { "type": "json_schema", "json_schema": {...} } enables Structured Outputs.
- **seed** (integer or null, Optional, Deprecated): If specified, system will make a best effort to sample deterministically.
- **service_tier** (string, Optional, Default: auto): Specifies the processing type used for serving the request.
- **stop** (string/array/null, Optional, Default: null): Up to 4 sequences where the API will stop generating further tokens.
- **store** (boolean or null, Optional, Default: false): Whether or not to store the output of this chat completion request.
- **stream** (boolean or null, Optional, Default: false)
- **stream_options** (object, Optional, Default: null): Options for streaming response.
- **temperature** (number, Optional, Default: 1): What sampling temperature to use, between 0 and 2.
- **tool_choice** (string or object, Optional): Controls which (if any) tool is called by the model.
- **tools** (array, Optional)
- **top_logprobs** (integer, Optional): An integer between 0 and 20 specifying the number of most likely tokens to return at each token position.
- **top_p** (number, Optional, Default: 1): An alternative to sampling with temperature, called nucleus sampling.
- **verbosity** (string, Optional, Default: medium): Constrains the verbosity of the model's response. Supported values: low, medium, high.
- **web_search_options** (object, Optional): This tool searches the web for relevant results to use in a response.

## Get chat completion

`GET /v1/chat/completions/{completion_id}`

Get a stored chat completion. Only Chat Completions created with store=true will be returned.

### Path parameters
- **completion_id** (string, Required): The ID of the chat completion to retrieve.

## Get chat messages

`GET /v1/chat/completions/{completion_id}/messages`

Get the messages in a stored chat completion.

### Path parameters
- **completion_id** (string, Required): The ID of the chat completion to retrieve messages from.

### Query parameters
- **after** (string, Optional): Identifier for the last message from the previous pagination request.
- **limit** (integer, Optional, Default: 20): Number of messages to retrieve.
- **order** (string, Optional, Default: asc): Sort order for messages by timestamp.

## List Chat Completions

`GET /v1/chat/completions`

List stored Chat Completions. Only Chat Completions created with store=true will be returned.

### Query parameters
- **after** (string, Optional): Identifier for the last chat completion from the previous pagination request.
- **limit** (integer, Optional, Default: 20): Number of Chat Completions to retrieve.
- **metadata** (object or null, Optional): A list of metadata keys to filter the Chat Completions by.
- **model** (string, Optional): The model used to generate the Chat Completions.
- **order** (string, Optional, Default: asc): Sort order for Chat Completions by timestamp.

## Update chat completion

`POST /v1/chat/completions/{completion_id}`

Modify a stored chat completion. Only Chat Completions created with store=true can be modified.

### Path parameters
- **completion_id** (string, Required): The ID of the chat completion to update.

### Request body
- **metadata** (map, Required): Set of 16 key-value pairs that can be attached to an object.

## Delete chat completion

`DELETE /v1/chat/completions/{completion_id}`

Delete a stored chat completion. Only Chat Completions created with store=true can be deleted.

### Path parameters
- **completion_id** (string, Required): The ID of the chat completion to delete.
