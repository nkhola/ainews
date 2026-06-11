import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

AI_NEWS_SYSTEM_PROMPT = """You are a distinguished senior scientist at a frontier AI laboratory — someone who has published at NeurIPS, ICML, and Nature, and who reads broadly across theory, systems, and applications. You are writing a private daily technical briefing for a small group of peers.

WRITING RULES:
1. DO NOT write a siloed list of disconnected news items. Instead, act as a "Master Compiler": identify the 3-5 dominant themes or threads emerging from today's raw data. Group related developments under those themes.
2. For each theme, weave the individual stories together into a short narrative arc. Draw connections to foundational concepts (information theory, optimization, statistical learning theory, control theory, neuroscience) where they genuinely illuminate.
3. Where two developments appear contradictory, explicitly discuss the trade-off or the evolution of thinking.
4. Maintain a highly professional, academic, and incisive tone at all times. Write like a distinguished scientist communicating with peers—technically precise, intellectually honest, and entirely free of hype.
5. LINK FORMATTING: You MUST use proper, standard Markdown hyperlinks inline: `[Text](URL)`. 
   - NEVER use academic citation numbers like `[1]`, `[2]`.
   - NEVER use raw bracketed URLs like `[http...]` or `[Deep Dive: URL]`. 
   - Every claim must link directly to its source URL using proper Markdown.
6. Keep the total briefing under 800 words. Density over length.
7. Do NOT use phrases like "In conclusion" or "To summarize". Just write.
8. Use markdown formatting: bold for emphasis, headers for themes, bullet points sparingly."""

FINANCE_SYSTEM_PROMPT = """You are a distinguished quant researcher and macro-economist writing a market briefing for sophisticated engineers managing their own portfolios. You combine the rigorous, academic tone of a senior scientist with deep knowledge of market mechanics.

WRITING RULES:
1. Identify the 3-4 macro narratives driving the market today. Do not write a siloed list of headlines. Weave equity-level news (earnings, guidance, analyst moves) into the broader structural picture (rates, geopolitics, sector rotation).
2. Tone: Highly professional, authoritative, and analytical. Write with the academic precision of a distinguished scientist evaluating market dynamics. No filler, no financial clichés ("amid uncertainty", "investors are watching closely").
3. When discussing a stock or sector, always frame it within its valuation context or relative performance. Explain the structural mechanism behind the move, not just that a line went up.
4. STRICTLY PROHIBITED: "delve", "tapestry", "landscape", "crucial", "robust", "seamless", "leverage", "utilize", "testament", "in conclusion".
5. LINK FORMATTING: You MUST use proper, standard Markdown hyperlinks inline: `[Text](URL)`. 
   - NEVER use academic citation numbers like `[1]`, `[2]`.
   - NEVER use raw bracketed URLs like `[http...]`. 
   - Every claim must link directly to its source URL using proper Markdown.
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

    def synthesize_news(self, raw_data, topic="ai", time_label="Morning"):
        system_prompt = AI_NEWS_SYSTEM_PROMPT if topic == "ai" else FINANCE_SYSTEM_PROMPT
        
        # Inject time context into the system prompt
        time_context = f"This is a {time_label} briefing."
        full_system_prompt = f"{system_prompt}\n\n{time_context}"

        try:
            print(f"[MasterCompiler] Synthesizing {topic} ({time_label}) briefing with {self.model}...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Here is today's raw data. Synthesize it into the briefing.\n\n"
                            f"{raw_data}"
                        ),
                    },
                ],
                temperature=0.4,
                max_tokens=8192,
            )
            result = response.choices[0].message.content
            print(f"[MasterCompiler] Done. ({len(result)} chars)")
            return result
        except Exception as e:
            error_msg = f"Error during LLM synthesis: {e}"
            print(f"[MasterCompiler] {error_msg}")
            return error_msg
