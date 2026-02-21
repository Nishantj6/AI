"""
BaseAgent — shared logic for all Apex AI agents.
Handles Claude API calls, tool use, and streaming.
"""
import json
import asyncio
from typing import AsyncIterator, Any, Optional, Callable
import anthropic
from backend.config import get_settings

settings = get_settings()


# Tool definitions available to all agents
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


class BaseAgent:
    """
    Wraps a Claude model call with Apex-specific tooling.
    Subclasses provide name, system_prompt, model_id, and tier.
    """

    name: str = "base"
    tier: int = 0
    domain: str = "f1"
    specialty: str = ""
    model_id: str = "claude-opus-4-6"
    bio: str = ""
    system_prompt: str = ""
    tools: list = KNOWLEDGE_TOOLS

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    def get_thinking_config(self) -> Optional[dict]:
        if self.tier == 1:
            return {"type": "adaptive"}
        return None

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
        Handles tool calls by dispatching to knowledge_lookup.
        """
        system = self.system_prompt
        if extra_context:
            system += f"\n\n--- CURRENT CONTEXT ---\n{extra_context}"

        thinking = self.get_thinking_config()
        create_kwargs: dict[str, Any] = {
            "model": self.get_model(),
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
            "tools": self.tools,
        }
        if thinking:
            create_kwargs["thinking"] = thinking

        # Agentic tool-use loop with streaming
        while True:
            collected_text = []
            tool_calls = []
            stop_reason = None

            async with self._client.messages.stream(**create_kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            chunk = event.delta.text
                            collected_text.append(chunk)
                            yield chunk
                    elif event.type == "content_block_stop":
                        pass

                final = await stream.get_final_message()
                stop_reason = final.stop_reason

                # Collect any tool use blocks from the final message
                for block in final.content:
                    if block.type == "tool_use":
                        tool_calls.append(block)

            if stop_reason != "tool_use" or not tool_calls:
                break

            # Execute tool calls
            tool_results = []
            for tc in tool_calls:
                result = await self._execute_tool(tc, knowledge_lookup)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result,
                })

            # Append assistant turn + tool results for next iteration
            create_kwargs["messages"] = list(create_kwargs["messages"]) + [
                {"role": "assistant", "content": final.content},
                {"role": "user", "content": tool_results},
            ]
            # Clear thinking for subsequent turns (avoid double-thinking)
            create_kwargs.pop("thinking", None)

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

    async def _execute_tool(self, tool_use, knowledge_lookup: Optional[Callable]) -> str:
        name = tool_use.name
        inp = tool_use.input if isinstance(tool_use.input, dict) else json.loads(tool_use.input)

        if name == "search_knowledge_base" and knowledge_lookup:
            results = await knowledge_lookup(inp.get("query", ""), inp.get("min_confidence", 0.5))
            return json.dumps(results, indent=2)

        if name == "submit_theory":
            # Return a receipt — actual persistence happens in the debate engine
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
