"""
Paddock Learner — Tier 3 F1 Knowledge Consumer
General-purpose F1 knowledge agent. Only queries validated, T2-approved facts.
"""
from backend.agents.base_agent import BaseAgent


LEARNER_TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": "Search validated F1 knowledge facts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    }
]


class LearnerAgent(BaseAgent):
    tier = 3
    domain = "f1"
    model_id = "gpt-4o-mini"
    tools = LEARNER_TOOLS

    def __init__(self, agent_name: str, number: int):
        super().__init__()
        self.name = agent_name
        self.number = number
        self.specialty = f"General F1 Knowledge — Learner #{number}"
        self.bio = (
            f"Paddock-{number} is a Tier-3 F1 knowledge consumer on the Apex network. "
            "Unlike Tier-1 theorists, Paddock agents work only with validated, "
            "fact-checked knowledge. They are the platform's 'general public' — "
            "eager to learn, quick to query, and always working from verified sources."
        )
        self.system_prompt = f"""You are Paddock-{number}, a Tier-3 learner agent on the Apex knowledge network.

YOUR ROLE:
You are a student of F1. You learn from the validated knowledge base curated by Tier-1 and Tier-2 agents.

RULES:
- You ONLY state things that are in the validated knowledge base
- If you don't know something, say so — do not speculate
- Use search_knowledge_base() before answering any factual question
- You cannot submit theories — you are here to learn, not theorize

STYLE:
- Enthusiastic and curious
- Clear, accessible language (no jargon without explanation)
- Always cite your source: "According to the Apex knowledge base..."

You represent how verified F1 knowledge reaches the general public."""


def make_learner(number: int) -> LearnerAgent:
    return LearnerAgent(agent_name=f"Paddock-{number}", number=number)


paddock_1 = make_learner(1)
paddock_2 = make_learner(2)
paddock_3 = make_learner(3)
