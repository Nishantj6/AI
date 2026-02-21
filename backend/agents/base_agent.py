"""
BaseAgent — shared logic for all Apex AI agents.
Handles OpenAI API calls, tool use, and streaming.
"""
import json
import asyncio
from typing import AsyncIterator, Any, Optional, Callable
from openai import AsyncOpenAI
from backend.config import get_settings

settings = get_settings()


# Tool definitions available to all agents (Anthropic input_schema format — converted below)
KNOWLEDGE_TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the Apex knowledge base for validated F1 facts and theories. "
            "Use this to ground your arguments in confirmed data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence score (0.0–1.0)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "cite_fact",
        "description": "Cite a specific knowledge fact by ID to support your argument.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact_id": {"type": "integer", "description": "ID of the knowledge fact"},
            },
            "required": ["fact_id"],
        },
    },
    {
        "name": "submit_theory",
        "description": (
            "Submit a formal theory or prediction to the knowledge cascade for T2 validation. "
            "Only use this when you have a well-reasoned, evidence-backed claim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short theory title"},
                "content": {"type": "string", "description": "Full theory explanation"},
                "evidence": {"type": "string", "description": "Supporting evidence"},
                "confidence": {
                    "type": "number",
                    "description": "Your confidence level (0.0–1.0)",
                },
            },
            "required": ["title", "content", "confidence"],
        },
    },
]

VALIDATOR_TOOLS = [
    {
        "name": "validate_theory",
        "description": "Mark a theory as validated or flag it as anomalous.",
        "input_schema": {
            "type": "object",
            "properties": {
                "theory_id": {"type": "integer"},
                "verdict": {
                    "type": "string",
                    "enum": ["validated", "anomaly", "rejected"],
                },
                "reasoning": {"type": "string"},
            },
            "required": ["theory_id", "verdict", "reasoning"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": "Search the validated knowledge base to cross-check a theory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
]


def _to_openai_tools(tools: list) -> list:
    """Convert internal tool format (Anthropic-style) to OpenAI function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


class BaseAgent:
    """
    Wraps an OpenAI model call with Apex-specific tooling.
    Subclasses provide name, system_prompt, model_id, and tier.
    """

    name: str = "base"
    tier: int = 0
    domain: str = "f1"
    specialty: str = ""
    model_id: str = "gpt-4o"
    bio: str = ""
    system_prompt: str = ""
    tools: list = KNOWLEDGE_TOOLS

    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    def get_model(self) -> str:
        return self.model_id

    async def respond(
        self,
        messages: list,
        knowledge_lookup: Optional[Callable] = None,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        """
        Stream a response. Yields text chunks as they arrive.
        Handles tool calls by dispatching to the appropriate tool handler.
        """
        system = self.system_prompt
        if extra_context:
            system += f"\n\n--- CURRENT CONTEXT ---\n{extra_context}"

        oai_messages = [{"role": "system", "content": system}] + list(messages)
        oai_tools = _to_openai_tools(self.tools)

        # Agentic tool-use loop with streaming
        while True:
            tool_calls_map: dict[int, dict] = {}
            collected_text: list[str] = []
            finish_reason = None

            stream = await self._client.chat.completions.create(
                model=self.get_model(),
                messages=oai_messages,
                tools=oai_tools if oai_tools else None,
                stream=True,
            )

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue

                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                # Stream text content
                if delta.content:
                    collected_text.append(delta.content)
                    yield delta.content

                # Accumulate tool call deltas
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_delta.id:
                            tool_calls_map[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_map[idx]["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_map[idx]["arguments"] += tc_delta.function.arguments

            if finish_reason != "tool_calls" or not tool_calls_map:
                break

            # Build the assistant message with tool_calls
            tool_calls_list = [
                {
                    "id": tool_calls_map[idx]["id"],
                    "type": "function",
                    "function": {
                        "name": tool_calls_map[idx]["name"],
                        "arguments": tool_calls_map[idx]["arguments"],
                    },
                }
                for idx in sorted(tool_calls_map.keys())
            ]

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "tool_calls": tool_calls_list,
            }
            if collected_text:
                assistant_msg["content"] = "".join(collected_text)
            oai_messages.append(assistant_msg)

            # Execute each tool call and append results
            for tc in tool_calls_list:
                name = tc["function"]["name"]
                try:
                    inp = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    inp = {}
                result = await self._execute_tool_by_name(name, inp, knowledge_lookup)
                oai_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

    async def respond_full(
        self,
        messages: list,
        knowledge_lookup: Optional[Callable] = None,
        extra_context: str = "",
    ) -> str:
        """Collect full streamed response into a string."""
        chunks = []
        async for chunk in self.respond(messages, knowledge_lookup, extra_context):
            chunks.append(chunk)
        return "".join(chunks)

    async def _execute_tool_by_name(
        self, name: str, inp: dict, knowledge_lookup: Optional[Callable]
    ) -> str:
        if name == "search_knowledge_base" and knowledge_lookup:
            results = await knowledge_lookup(inp.get("query", ""), inp.get("min_confidence", 0.5))
            return json.dumps(results, indent=2)

        if name == "submit_theory":
            return json.dumps({
                "status": "queued",
                "message": f"Theory '{inp.get('title')}' queued for T2 validation.",
                "confidence": inp.get("confidence"),
            })

        if name == "cite_fact":
            return json.dumps({"status": "cited", "fact_id": inp.get("fact_id")})

        if name == "validate_theory":
            return json.dumps({
                "status": "recorded",
                "verdict": inp.get("verdict"),
                "theory_id": inp.get("theory_id"),
            })

        return json.dumps({"error": f"Unknown tool: {name}"})

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "tier": self.tier,
            "domain": self.domain,
            "specialty": self.specialty,
            "model_id": self.model_id,
            "bio": self.bio,
            "system_prompt": self.system_prompt,
        }
