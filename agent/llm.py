"""Unified LLM interface supporting Gemini and Anthropic."""

from __future__ import annotations

import json
import time

from config import AI_PROVIDER, ANTHROPIC_API_KEY, CLAUDE_MODEL, GEMINI_API_KEY, GEMINI_MODEL


def _gemini_call_with_retry(fn, max_retries: int = 5):
    from google.api_core.exceptions import ResourceExhausted

    delay = 60
    for attempt in range(max_retries):
        try:
            return fn()
        except ResourceExhausted as exc:
            msg = str(exc)
            if "retry_delay" in msg:
                try:
                    import re

                    delay = int(re.search(r"seconds:\s*(\d+)", msg).group(1)) + 5
                except Exception:
                    pass
            if attempt < max_retries - 1:
                print(f"[llm] Rate limit hit, waiting {delay}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(delay)
                delay = min(delay * 2, 300)
            else:
                raise


def _build_gemini_tool_schemas(tool_schemas: list[dict]) -> list[dict]:
    type_map = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT",
    }

    def convert_schema(schema: dict) -> dict:
        schema_type = schema.get("type", "string")
        result: dict = {"type": type_map.get(schema_type, "STRING")}
        if "description" in schema:
            result["description"] = schema["description"]
        if "enum" in schema:
            result["enum"] = schema["enum"]
        if schema_type == "object":
            props = schema.get("properties", {})
            if props:
                result["properties"] = {k: convert_schema(v) for k, v in props.items()}
            if "required" in schema:
                result["required"] = schema["required"]
        if schema_type == "array" and "items" in schema:
            result["items"] = convert_schema(schema["items"])
        return result

    return [
        {
            "function_declarations": [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": convert_schema(tool["input_schema"]),
                }
                for tool in tool_schemas
            ]
        }
    ]


class GeminiClient:
    def __init__(self):
        import google.generativeai as genai

        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set. Add it to your .env file.")
        genai.configure(api_key=GEMINI_API_KEY)
        self._genai = genai

    def complete(self, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
        model = self._genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=system)
        history, last = self._convert_messages(messages)
        chat = model.start_chat(history=history)
        response = _gemini_call_with_retry(lambda: chat.send_message(last))
        return response.text

    def tool_loop(self, system: str, messages: list[dict], tool_schemas: list[dict], dispatcher, max_iterations: int = 10):
        import google.generativeai.protos as protos

        model = self._genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            tools=_build_gemini_tool_schemas(tool_schemas),
        )
        history, last_text = self._convert_messages(messages)
        chat = model.start_chat(history=history)
        response = _gemini_call_with_retry(lambda: chat.send_message(last_text))
        trades_executed = []
        tool_calls = 0

        for _ in range(max_iterations):
            fn_calls = [part.function_call for part in response.parts if part.function_call.name]
            if not fn_calls:
                break
            tool_responses = []
            for fn in fn_calls:
                tool_calls += 1
                result_str = dispatcher(fn.name, dict(fn.args))
                if fn.name == "execute_trade":
                    result = json.loads(result_str)
                    if result.get("success"):
                        trades_executed.append(result)
                tool_responses.append(
                    protos.Part(
                        function_response=protos.FunctionResponse(name=fn.name, response={"result": result_str})
                    )
                )
            response = _gemini_call_with_retry(lambda r=tool_responses: chat.send_message(protos.Content(role="user", parts=r)))

        return messages, trades_executed, {"tool_calls": tool_calls}

    def _convert_messages(self, messages: list[dict]) -> tuple[list, str]:
        history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            if isinstance(msg["content"], str):
                history.append({"role": role, "parts": [msg["content"]]})
        last = messages[-1]["content"] if messages else ""
        if isinstance(last, list):
            last = " ".join(part.get("text", "") for part in last if isinstance(part, dict))
        return history, last


class AnthropicClient:
    def __init__(self):
        import anthropic

        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set.")
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def complete(self, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
        response = self._client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    def tool_loop(self, system: str, messages: list[dict], tool_schemas: list[dict], dispatcher, max_iterations: int = 10):
        trades_executed = []
        tool_calls = 0
        msgs = list(messages)

        for _ in range(max_iterations):
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=system,
                tools=tool_schemas,
                messages=msgs,
            )
            msgs.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tool_calls += 1
                result_str = dispatcher(block.name, block.input)
                if block.name == "execute_trade":
                    result = json.loads(result_str)
                    if result.get("success"):
                        trades_executed.append(result)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_str})
            msgs.append({"role": "user", "content": tool_results})

        return msgs, trades_executed, {"tool_calls": tool_calls}


def get_llm_client():
    if AI_PROVIDER == "anthropic":
        return AnthropicClient()
    return GeminiClient()
