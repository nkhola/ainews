import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Master System Prompt Template
MASTER_SYSTEM_PROMPT = """You are a {persona} and a "Master Compiler" acting as the "Arbiter of Truth." You are writing a private daily briefing for a small group of sophisticated peers. 

Your goal is to build a deeply cross-linked knowledge graph of the day's events, mapping new concepts into existing core pillars.

WRITING RULES:
1. EXECUTIVE SUMMARY: Start with a 2-3 sentence high-level summary of the most critical takeaway from the entire dataset before diving into themes.
2. MASTER COMPILER: Identify 3-5 dominant narratives. Resolve contradictions by explicitly creating "Trade-offs & Evolution" sections where developments conflict or change previous assumptions.
3. STRUCTURED THEMES: For each theme:
   - Use an `### Theme Name` header.
   - Weave individual stories into a cohesive narrative arc. {context_requirement}
   - End each theme with a `#### Why it matters` sub-header followed by 1-2 sentences on the structural mechanism or broader implication.
4. HUMAN-LIKE EXPERTISE: Do NOT sound like an AI assistant. Avoid being neutral or verbose. Write with the authoritative, slightly opinionated, and incisive tone of a human expert who has skin in the game.
5. THE BOTTOM LINE: End the entire briefing with a single-sentence "Bottom Line" that connects the day's events to a long-term trend.
6. LINK FORMATTING (STRICT): You MUST use standard Markdown hyperlinks INLINE: `[Descriptive text about the news](https://url)`. 
   - NEVER use `[1]`, `[2]` or `[Source]`. 
   - NEVER use raw URLs in brackets.
   - The link text must be high-signal (e.g., "[Google's new encoder-free multimodal model](...)" instead of "[Link](...)").
7. ANTI-AI GUARDS: 
   - STRICTLY PROHIBITED: "delve", "tapestry", "landscape", "crucial", "robust", "seamless", "leverage", "utilize", "testament", "in conclusion", "moreover", "furthermore".
   - NO AI CLICHÉS: "In the ever-evolving...", "It's important to note...", "Only time will tell...".
   - NO FINANCIAL CLICHÉS (for finance): "amid uncertainty", "investors are watching closely".
   - NO EM DASHES (`—` or `–`). Use parentheses or commas.
8. CONCISION: Prioritize extreme conciseness and high information density. Do not ramble, but ensure all thoughts and sentences are fully completed.

{topic_specific_guidance}"""

AI_GUIDANCE = {
    "persona": "distinguished senior scientist at a frontier AI laboratory",
    "context_requirement": "Draw connections to foundational concepts (information theory, optimization, statistical learning theory, control theory, neuroscience) where they genuinely illuminate.",
    "topic_specific_guidance": "Focus on technical breakthroughs, architectural shifts, and the evolving open/closed model ecosystem. Discuss inference scaling and world models with technical precision."
}

FINANCE_GUIDANCE = {
    "persona": "distinguished quant researcher and macro-economist",
    "context_requirement": "Weave equity-level news (earnings, guidance, analyst moves) into the broader structural picture (rates, geopolitics, sector rotation).",
    "topic_specific_guidance": "Frame stocks/sectors within their valuation context. Connect market moves to macro narratives (inflation, liquidity, geopolitics). Explain the structural mechanism behind moves, not just price action."
}


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

    def _create_completion_with_retry(self, messages, temperature, max_tokens, max_retries=3, backoff=5):
        import time
        for attempt in range(max_retries):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                print(f"[MasterCompiler] API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                print(f"[MasterCompiler] Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2

    def synthesize_news(self, raw_data, topic="ai", time_label="Morning"):
        guidance = AI_GUIDANCE if topic == "ai" else FINANCE_GUIDANCE
        
        system_prompt = MASTER_SYSTEM_PROMPT.format(
            persona=guidance["persona"],
            context_requirement=guidance["context_requirement"],
            topic_specific_guidance=guidance["topic_specific_guidance"]
        )
        
        # Inject time context into the system prompt
        time_context = f"This is a {time_label} briefing."
        full_system_prompt = f"{system_prompt}\n\n{time_context}"

        print(f"[MasterCompiler] Synthesizing {topic} ({time_label}) briefing with {self.model}...")
        response = self._create_completion_with_retry(
            messages=[
                {"role": "system", "content": full_system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Here is today's raw data. Synthesize it into the briefing.\n\n"
                        f"{raw_data}\n\n"
                        f"IMPORTANT FINAL REMINDERS:\n"
                        f"- You MUST use standard Markdown hyperlinks INLINE: `[Descriptive text about the news](https://url)`.\n"
                        f"- NEVER use raw URLs in brackets like `[https://url]`. ALWAYS use standard inline markdown links."
                    ),
                },
            ],
            temperature=0.4,
            max_tokens=8192,
        )
        result = response.choices[0].message.content
        print(f"[MasterCompiler] Done. ({len(result)} chars)")
        
        # EVAL LOOP: Ensure link formatting is flawless
        print(f"[MasterCompiler] Running formatting eval loop...")
        eval_system_prompt = (
            "You are a strict formatting evaluator. Your job is to review the following markdown text "
            "and ensure it perfectly adheres to the link formatting rules.\n\n"
            "LINK FORMATTING RULES:\n"
            "- You MUST use standard Markdown hyperlinks INLINE: `[Descriptive text about the news](https://url)`.\n"
            "- NEVER use raw URLs in brackets like `[https://url]`. If you see them, convert them to `[Source](https://url)` "
            "or infer a descriptive text from the context.\n"
            "- NEVER use `[1]`, `[2]` etc.\n\n"
            "Return ONLY the corrected markdown. Do not add any preamble, commentary, or backticks around the output."
        )
        eval_response = self._create_completion_with_retry(
            messages=[
                {"role": "system", "content": eval_system_prompt},
                {"role": "user", "content": result},
            ],
            temperature=0.1,
            max_tokens=8192,
        )
        final_result = eval_response.choices[0].message.content
        print(f"[MasterCompiler] Eval loop done. ({len(final_result)} chars)")
        return final_result

