"""
Unified LLM interface — supports Gemini (default) and Anthropic.
All agent nodes use this module instead of calling SDKs directly.
"""

from __future__ import annotations
import json
import time
from config import AI_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL, ANTHROPIC_API_KEY, CLAUDE_MODEL


def _gemini_call_with_retry(fn, max_retries: int = 5):
    """Retry a Gemini API call on 429 rate-limit errors with exponential backoff."""
    from google.api_core.exceptions import ResourceExhausted
    delay = 60  # start at 60s (daily quota exhaustion needs longer waits)
    for attempt in range(max_retries):
        try:
            return fn()
        except ResourceExhausted as e:
            # Extract suggested retry delay from error if available
            msg = str(e)
            if "retry_delay" in msg:
                try:
                    import re
                    secs = int(re.search(r"seconds:\s*(\d+)", msg).group(1))
                    delay = secs + 5
                except Exception:
                    pass
            if attempt < max_retries - 1:
                print(f"[llm] Rate limit hit — waiting {delay}s before retry ({attempt+1}/{max_retries})...")
                time.sleep(delay)
                delay = min(delay * 2, 300)  # cap at 5 min
            else:
                raise


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

def _build_gemini_tool_schemas(tool_schemas: list[dict]) -> list[dict]:
    """
    Convert Anthropic-style tool schemas to Gemini dict format.
    Uses plain Python dicts (no protos) to avoid MapComposite issues.
    """
    TYPE_MAP = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT",
    }

    def convert_schema(schema: dict) -> dict:
        t = schema.get("type", "string")
        result: dict = {"type": TYPE_MAP.get(t, "STRING")}

        if "description" in schema:
            result["description"] = schema["description"]

        if "enum" in schema:
            result["enum"] = schema["enum"]

        if t == "object":
            props = schema.get("properties", {})
            if props:
                result["properties"] = {k: convert_schema(v) for k, v in props.items()}
            if "required" in schema:
                result["required"] = schema["required"]

        if t == "array" and "items" in schema:
            result["items"] = convert_schema(schema["items"])

        return result

    function_declarations = []
    for tool in tool_schemas:
        decl = {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": convert_schema(tool["input_schema"]),
        }
        function_declarations.append(decl)

    return [{"function_declarations": function_declarations}]


class GeminiClient:
    def __init__(self):
        import google.generativeai as genai
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set. Add it to your .env file.")
        genai.configure(api_key=GEMINI_API_KEY)
        self._genai = genai

    def complete(self, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
        """Simple text completion (no tools)."""
        model = self._genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
        )
        history, last = self._convert_messages(messages)
        chat = model.start_chat(history=history)
        response = _gemini_call_with_retry(lambda: chat.send_message(last))
        return response.text

    def tool_loop(
        self,
        system: str,
        messages: list[dict],
        tool_schemas: list[dict],
        dispatcher,
        max_iterations: int = 10,
    ) -> tuple[list[dict], list[dict]]:
        """
        Run a tool-calling loop with Gemini function calling.
        Returns (updated_messages, executed_trades).
        """
        import google.generativeai.protos as protos

        gemini_tools = _build_gemini_tool_schemas(tool_schemas)
        model = self._genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            tools=gemini_tools,
        )

        history, last_text = self._convert_messages(messages)
        chat = model.start_chat(history=history)
        response = _gemini_call_with_retry(lambda: chat.send_message(last_text))

        trades_executed = []

        for _ in range(max_iterations):
            # Collect any function calls
            fn_calls = [p.function_call for p in response.parts if p.function_call.name]
            if not fn_calls:
                break

            # Execute each tool call and collect responses
            tool_responses = []
            for fn in fn_calls:
                tool_name = fn.name
                tool_input = dict(fn.args)
                print(f"[decide] Tool call: {tool_name}({json.dumps(tool_input, default=str)[:120]})")

                result_str = dispatcher(tool_name, tool_input)

                if tool_name == "execute_trade":
                    result_obj = json.loads(result_str)
                    if result_obj.get("success"):
                        trades_executed.append(result_obj)

                # Use protos.Part with FunctionResponse
                tool_responses.append(
                    protos.Part(
                        function_response=protos.FunctionResponse(
                            name=tool_name,
                            response={"result": result_str},
                        )
                    )
                )

            response = _gemini_call_with_retry(
                lambda r=tool_responses: chat.send_message(
                    protos.Content(role="user", parts=r)
                )
            )

        return messages, trades_executed

    def _convert_messages(self, messages: list[dict]) -> tuple[list, str]:
        """Split messages into history + last user message for Gemini chat."""
        import google.generativeai as genai

        history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]
            if isinstance(content, str):
                history.append({"role": role, "parts": [content]})
            # Skip tool-result messages in history (Gemini handles them via chat state)

        last = messages[-1]["content"] if messages else ""
        if isinstance(last, list):
            # Fallback: join text parts
            last = " ".join(p.get("text", "") for p in last if isinstance(p, dict))
        return history, last


# ---------------------------------------------------------------------------
# Anthropic client (wrapper)
# ---------------------------------------------------------------------------

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

    def tool_loop(
        self,
        system: str,
        messages: list[dict],
        tool_schemas: list[dict],
        dispatcher,
        max_iterations: int = 10,
    ) -> tuple[list[dict], list[dict]]:
        trades_executed = []
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
                result_str = dispatcher(block.name, block.input)
                if block.name == "execute_trade":
                    obj = json.loads(result_str)
                    if obj.get("success"):
                        trades_executed.append(obj)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
            msgs.append({"role": "user", "content": tool_results})

        return msgs, trades_executed


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_llm_client():
    """Return the configured LLM client (Gemini or Anthropic)."""
    if AI_PROVIDER == "anthropic":
        return AnthropicClient()
    return GeminiClient()
