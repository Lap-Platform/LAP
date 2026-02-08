# OpenAI API API Documentation

Base URL: https://api.openai.com/v1

Version: 2.0.0

## Authentication

Bearer bearer

## POST /chat/completions

Create chat completion

### Required Parameters

- **model** (str):  - ID of the model to use (e.g. gpt-4o, gpt-4o-mini)
- **messages** ([map]):  - A list of messages comprising the conversation so far

### Optional Parameters

- **temperature** (num):  - Sampling temperature between 0 and 2. Higher values make output more random.
- **top_p** (num):  - Nucleus sampling parameter. We generally recommend altering this or temperature but not both.
- **n** (int):  - How many chat completion choices to generate for each input message
- **stream** (bool):  - If set, partial message deltas will be sent as server-sent events
- **max_tokens** (int):  - The maximum number of tokens that can be generated in the chat completion
- **stop** (str):  - Up to 4 sequences where the API will stop generating further tokens
- **presence_penalty** (num):  - Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far.
- **frequency_penalty** (num):  - Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far.
- **tools** ([map]):  - A list of tools the model may call. Currently only functions are supported.
- **tool_choice** (str):  - Controls which (if any) tool is called by the model (auto, none, required, or object)
- **response_format** (map):  - An object specifying the format that the model must output (e.g. json_object, json_schema)
- **seed** (int):  - If specified, system will make a best effort to sample deterministically
- **user** (str):  - A unique identifier representing your end-user for abuse monitoring

## POST /embeddings

Create embeddings

### Required Parameters

- **model** (str):  - ID of the model to use (e.g. text-embedding-3-small, text-embedding-3-large)
- **input** (str):  - Input text to embed. Can be a string or array of strings.

### Optional Parameters

- **encoding_format** (str):  - The format to return the embeddings in
- **dimensions** (int):  - The number of dimensions the resulting output embeddings should have (only for v3 models)
- **user** (str):  - A unique identifier representing your end-user

## GET /models

List models

## GET /models/{model}

Retrieve model

### Required Parameters

- **model** (str):  - The ID of the model to retrieve

## POST /images/generations

Create image

### Required Parameters

- **prompt** (str):  - A text description of the desired image(s). Maximum 4000 characters.

### Optional Parameters

- **model** (str):  - The model to use for image generation (dall-e-2 or dall-e-3)
- **n** (int):  - The number of images to generate (1-10 for dall-e-2, only 1 for dall-e-3)
- **size** (str):  - The size of the generated images
- **quality** (str):  - The quality of the image (only for dall-e-3)
- **response_format** (str):  - The format in which generated images are returned
- **style** (str):  - The style of the generated images (only for dall-e-3)
- **user** (str):  - A unique identifier representing your end-user
