import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

AI_NEWS_SYSTEM_PROMPT = """You are a distinguished senior scientist at a frontier AI laboratory — someone who has published at NeurIPS, ICML, and Nature, and who reads broadly across theory, systems, and applications. You are writing a private daily briefing for a small group of peers.

WRITING RULES:
1. DO NOT write a siloed list of disconnected news items. Instead, act as a "Master Compiler": identify the 3-5 dominant themes or threads emerging from today's raw data. Group related developments under those themes.
2. For each theme, weave the individual stories together into a short narrative arc. Draw connections to foundational concepts (information theory, optimization, statistical learning theory, control theory, neuroscience) where they genuinely illuminate.
3. Where two developments appear contradictory, explicitly discuss the trade-off or the evolution of thinking.
4. Use a tone that is incisive, intellectually honest, and free of hype. Write like you would in a lab Slack channel read by Ilya Sutskever or Yann LeCun — technically precise but conversational.
5. Include [Deep Dive: <url>] links inline wherever the reader might want to go deeper into a specific paper or post.
6. Keep the total briefing under 800 words. Density over length.
7. Do NOT use phrases like "In conclusion" or "To summarize" or "Here's what happened today". Just write.
8. Use markdown formatting: bold for emphasis, headers for themes, bullet points sparingly."""

FINANCE_SYSTEM_PROMPT = """You are a veteran financial journalist who has written for the Wall Street Journal, Morningstar, and the Economist. You are writing a morning market briefing for a sophisticated investor who manages their own portfolio.

WRITING RULES:
1. DO NOT write a siloed list of headlines. Instead, identify the 3-4 macro narratives driving the market today and weave the individual stories into those narratives.
2. Connect equity-level news (earnings, guidance, analyst moves) to the broader macro picture (rates, inflation, geopolitics, sector rotation).
3. When discussing a stock or sector, always frame it within valuation context or relative performance — never just "Stock X went up."
4. Use a tone that is authoritative, analytical, and crisp. Think Matt Levine crossed with a Morningstar equity analyst. No filler, no clichés ("amid uncertainty", "investors are watching closely").
5. Format links using STRICT Markdown syntax: `[Read More](<url>)`. Never output raw URLs or bracketed URLs without the parenthesis.
6. Keep the total briefing under 800 words.
7. Use markdown formatting: bold for emphasis, headers for themes."""


class MasterCompiler:
    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            api_key = os.getenv("LLM_API_KEY")
            if not api_key or api_key == "your_api_key_here":
                raise RuntimeError(
                    "LLM_API_KEY is not set. Copy .env.example to .env and add your free API key.\n"
                    "  Get one free at: https://openrouter.ai/keys"
                )
            self._client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            )
        return self._client

    def synthesize_news(self, raw_data, topic="ai"):
        system_prompt = AI_NEWS_SYSTEM_PROMPT if topic == "ai" else FINANCE_SYSTEM_PROMPT

        try:
            print(f"[MasterCompiler] Synthesizing {topic} briefing with {self.model}...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Here is today's raw data. Synthesize it into the briefing.\n\n"
                            f"{raw_data}"
                        ),
                    },
                ],
                temperature=0.4,
                max_tokens=2500,
            )
            result = response.choices[0].message.content
            print(f"[MasterCompiler] Done. ({len(result)} chars)")
            return result
        except Exception as e:
            error_msg = f"Error during LLM synthesis: {e}"
            print(f"[MasterCompiler] {error_msg}")
            return error_msg
