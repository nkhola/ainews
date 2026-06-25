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
        self.vertex_project_id = os.getenv("VERTEX_PROJECT_ID")
        self.vertex_location = os.getenv("VERTEX_LOCATION") or "global"
        
        if self.vertex_project_id:
            self.model = os.getenv("LLM_MODEL") or "google/gemini-3.5-flash"
        else:
            self.model = os.getenv("LLM_MODEL") or "deepseek/deepseek-chat"
            
        self._client = None
        self._using_fallback = False

        # Fallback configuration (OpenRouter free tier by default)
        self.fallback_model = os.getenv("LLM_FALLBACK_MODEL") or "meta-llama/llama-3.3-70b-instruct:free"
        self.fallback_base_url = os.getenv("LLM_FALLBACK_BASE_URL") or "https://openrouter.ai/api/v1"
        self.fallback_api_key = os.getenv("LLM_FALLBACK_API_KEY") or os.getenv("LLM_API_KEY")
        self._fallback_client = None

    @property
    def client(self):
        if self._client is None:
            if self.vertex_project_id:
                try:
                    import google.auth
                    from google.auth.transport.requests import Request
                    # MUST specify scopes, otherwise generateAccessToken returns 400 Invalid Argument
                    credentials, project_id = google.auth.default(
                        scopes=['https://www.googleapis.com/auth/cloud-platform']
                    )
                    credentials.refresh(Request())
                    
                    hostname = "aiplatform.googleapis.com" if self.vertex_location == "global" else f"{self.vertex_location}-aiplatform.googleapis.com"
                    base_url = f"https://{hostname}/v1beta1/projects/{self.vertex_project_id}/locations/{self.vertex_location}/endpoints/openapi"
                    
                    self._client = OpenAI(
                        api_key=credentials.token,
                        base_url=base_url,
                    )
                    print(f"[MasterCompiler] Initialized Vertex AI client for project {self.vertex_project_id} in {self.vertex_location}")
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize Vertex AI client: {e}. Make sure google-auth is installed and GCP credentials are set.")
            else:
                api_key = os.getenv("LLM_API_KEY")
                if not api_key or api_key == "your_api_key_here":
                    raise RuntimeError(
                        "LLM_API_KEY is not set. Copy .env.example to .env and add your free API key.\n"
                        "  Get one free at: https://openrouter.ai/keys"
                    )
                self._client = OpenAI(
                    api_key=api_key,
                    base_url=os.getenv("LLM_BASE_URL") or "https://openrouter.ai/api/v1",
                )
        return self._client

    @property
    def fallback_client(self):
        if self._fallback_client is None:
            if not self.fallback_api_key:
                return None
            self._fallback_client = OpenAI(
                api_key=self.fallback_api_key,
                base_url=self.fallback_base_url,
            )
        return self._fallback_client

    def _switch_to_fallback(self):
        """Switch to fallback LLM provider."""
        if self._using_fallback or self.fallback_client is None:
            return False
        self._using_fallback = True
        print(f"[MasterCompiler] ⚠ Switching to fallback model: {self.fallback_model} via {self.fallback_base_url}")
        return True

    def _get_active_client(self):
        return self.fallback_client if self._using_fallback else self.client

    def _get_active_model(self):
        return self.fallback_model if self._using_fallback else self.model

    def _create_completion_with_retry(self, messages, temperature, max_tokens, max_retries=3, backoff=5):
        import time
        import random
        import re as _re
        from openai import RateLimitError

        # Rate limit errors get more retries and longer backoff
        rate_limit_max_retries = max(max_retries, 5)
        consecutive_errors = 0

        for attempt in range(rate_limit_max_retries):
            try:
                res = self._get_active_client().chat.completions.create(
                    model=self._get_active_model(),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                consecutive_errors = 0
                return res
            except RateLimitError as e:
                consecutive_errors += 1
                err_str = str(e)
                is_quota_exhausted = "quota" in err_str.lower() or "exceeded" in err_str.lower()

                # If quota is fully exhausted (not just a burst limit), try fallback immediately
                if is_quota_exhausted and not self._using_fallback:
                    print(f"[MasterCompiler] Quota exhausted on primary model: {e}")
                    if self._switch_to_fallback():
                        continue  # retry immediately with fallback

                # Parse server-suggested retry delay if available
                wait_time = backoff
                delay_match = _re.search(r'retry\s*(?:in|after)\s*([\d.]+)\s*s', err_str, _re.IGNORECASE)
                if delay_match:
                    wait_time = max(float(delay_match.group(1)), backoff) + random.uniform(1, 5)
                else:
                    wait_time = max(60, backoff) + random.uniform(1, 10)

                print(f"[MasterCompiler] Rate limited (attempt {attempt + 1}/{rate_limit_max_retries}): {e}")

                # After 2 consecutive rate limits, try fallback before exhausting retries
                if consecutive_errors >= 2 and not self._using_fallback:
                    if self._switch_to_fallback():
                        continue

                if attempt == rate_limit_max_retries - 1:
                    raise
                print(f"[MasterCompiler] Waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
                backoff = min(backoff * 2, 300)  # cap at 5 minutes
            except Exception as e:
                consecutive_errors += 1
                print(f"[MasterCompiler] API call failed (attempt {attempt + 1}/{rate_limit_max_retries}): {e}")
                
                # FOOL PROOF FIX: switch to fallback on ANY repeated error, not just rate limits!
                if consecutive_errors >= 2 and not self._using_fallback:
                    print(f"[MasterCompiler] Persistent errors detected. Switching to fallback...")
                    if self._switch_to_fallback():
                        continue
                        
                if attempt == rate_limit_max_retries - 1:
                    raise
                jitter = random.uniform(0, backoff * 0.1)
                print(f"[MasterCompiler] Retrying in {backoff + jitter:.1f} seconds...")
                time.sleep(backoff + jitter)
                backoff *= 2

    def _generate_with_continuation(self, messages, temperature):
        """Generates content and automatically handles truncation by asking the model to continue."""
        current_messages = list(messages)
        full_result = ""
        
        while True:
            response = self._create_completion_with_retry(
                messages=current_messages,
                temperature=temperature,
                max_tokens=8192,
            )
            
            chunk = response.choices[0].message.content
            full_result += chunk
            finish_reason = response.choices[0].finish_reason
            
            # Heuristic check: some APIs don't return 'length' reliably
            chunk_stripped = chunk.strip()
            # If it doesn't end with a common terminating character, it might be truncated
            heuristic_truncated = not chunk_stripped.endswith((".", "!", "?", ">", '"', "'", "*", "`"))
            
            is_truncated = (finish_reason == "length") or (finish_reason == "stop" and heuristic_truncated)
            
            # Log the state to a persistent log file
            log_path = os.path.join(os.path.dirname(__file__), "../../../generation.log")
            with open(log_path, "a") as f:
                import datetime
                timestamp = datetime.datetime.now().isoformat()
                f.write(f"[{timestamp}] Model: {self._get_active_model()} | Finish Reason: {finish_reason} | Heuristic Truncated: {heuristic_truncated} | Action: {'CONTINUING' if is_truncated else 'DONE'}\n")
            
            if not is_truncated:
                break
                
            print(f"[MasterCompiler] Truncation detected (finish_reason={finish_reason}, heuristic={heuristic_truncated}). Continuing generation...")
            current_messages.append({"role": "assistant", "content": chunk})
            current_messages.append({
                "role": "user", 
                "content": "Your previous response was truncated. Please continue exactly where you left off. Do not repeat anything from your previous response, just output the very next characters to seamlessly continue the text."
            })
            
        return full_result

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

        print(f"[MasterCompiler] Synthesizing {topic} ({time_label}) briefing with {self._get_active_model()}...")
        
        messages = [
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
        ]
        
        result = self._generate_with_continuation(messages, temperature=0.4)
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
        
        eval_messages = [
            {"role": "system", "content": eval_system_prompt},
            {"role": "user", "content": result},
        ]
        
        final_result = self._generate_with_continuation(eval_messages, temperature=0.1)
        print(f"[MasterCompiler] Eval loop done. ({len(final_result)} chars)")
        return final_result

