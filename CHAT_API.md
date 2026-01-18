12# Chat Proxy API (ModelScope DeepSeek)

This document summarizes the new chat endpoint used by the front-end (Ant Design X) to proxy ModelScope DeepSeek models and persist turns into ChromaDB.

## Endpoint
- `POST /api/chat/completions`

## Request body
```jsonc
{
  "conversation_id": "string",          // Conversation/group id (e.g., tab key)
  "model": "deepseek-ai/DeepSeek-R1-0528", // Optional; falls back to APP_MODEL_DEFAULT
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi!" }
  ],
  // Optional generation params (all defaulted from APP_MODEL_* envs if omitted)
  "api_key": "optional key to override server default",
  "temperature": 0.3,
  "top_p": 0.95,
  "presence_penalty": 0,
  "frequency_penalty": 0,
  "max_tokens": 512,
  "stream": false
}
```

## Successful response
```jsonc
{
  "conversation_id": "string",
  "model": "deepseek-ai/DeepSeek-R1-0528",
  "content": "Final assistant message",
  "reasoning": "Optional reasoning_content (DeepSeek R1)",
  "raw": { /* passthrough ModelScope payload */ }
}
```

- For DeepSeek-R1-0528, the `reasoning` field surfaces `message.reasoning_content` (deep thinking) when ModelScope provides it.
- The endpoint also writes a document into ChromaDB (`conversation_id`, `model`, request `messages`, reply, optional `reasoning`). Storage is best-effort; failures are logged but do not block the response.

## Errors
- `502`: Upstream ModelScope call failed (non-2xx or malformed response).
- `500`: Unexpected internal error.

## Environment variables (backend)
- `APP_MODELSCOPE_API_BASE` (default: `https://api-inference.modelscope.cn/v1`)
- `APP_MODELSCOPE_API_KEY`
- `APP_MODEL_DEFAULT` (default: `deepseek-ai/DeepSeek-V3.2`)
- `APP_MODEL_TEMPERATURE_DEFAULT` (default: `0.3`)
- `APP_MODEL_TOP_P_DEFAULT` (default: `0.95`)
- `APP_MODEL_PRESENCE_PENALTY_DEFAULT` (default: `0`)
- `APP_MODEL_FREQUENCY_PENALTY_DEFAULT` (default: `0`)
- `APP_MODEL_MAX_TOKENS_DEFAULT` (default: `None`, skips sending)
- `APP_MODEL_STREAM_DEFAULT` (default: `false`)
