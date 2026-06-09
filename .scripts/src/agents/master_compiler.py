import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

AI_NEWS_SYSTEM_PROMPT = """You are a Principal Machine Learning Engineer writing a daily technical briefing for a private group of senior engineering peers. Your lens is "post-human engineering" - a reality where autonomous agents write the first draft of code, and our job is managing physical hardware, distributed failure, and system fragility.

WRITING RULES:
1. Identify 3-4 deep architectural or systemic shifts from the raw data. Do not just list headlines. Group related developments and analyze the physical or operational constraints they hide or expose.
2. Tone: Precise, slightly gritty, and opinionated. Write like you are diagnosing a production incident. Argue from first principles (information theory, memory layouts, optimization).
3. House Standard: Name the comfortable abstraction being sold, show the physical constraint it hides, and state the engineering rule that falls out.
4. STRICTLY PROHIBITED: "delve", "tapestry", "landscape", "crucial", "robust", "seamless", "leverage", "utilize", "testament", "in conclusion", "this article explores". Do NOT use em dashes.
5. Format links using STRICT Markdown syntax: `[Deep Dive](<url>)`. Never output raw URLs or bracketed URLs without the parenthesis.
6. Keep the total briefing under 800 words. Density over length. Prefer short claims with explicit qualification over generalized hype.
7. Use standard markdown formatting: bold for emphasis, headers for themes, bullet points sparingly."""

FINANCE_SYSTEM_PROMPT = """You are a veteran macro-analyst and former quant trader writing a morning market briefing for sophisticated engineers managing their own portfolios.

WRITING RULES:
1. Identify the 3-4 macro narratives driving the market today. Do not write a siloed list of headlines. Weave equity-level news (earnings, guidance, analyst moves) into the broader structural picture (rates, geopolitics, sector rotation).
2. Tone: Authoritative, analytical, and crisp. Think Matt Levine crossed with a cynical infrastructure engineer. No filler, no financial clichés ("amid uncertainty", "investors are watching closely").
3. When discussing a stock or sector, always frame it within its valuation context or relative performance. Explain the structural mechanism behind the move, not just that a line went up.
4. STRICTLY PROHIBITED: "delve", "tapestry", "landscape", "crucial", "robust", "seamless", "leverage", "utilize", "testament", "in conclusion". Do NOT use em dashes.
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
