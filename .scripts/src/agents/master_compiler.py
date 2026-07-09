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
            if "/" not in self.model:
                self.model = f"google/{self.model}"
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

    def synthesize_audio_script(self, briefing_text, date_line, time_label):
        """Rewrite a written briefing as a spoken-word narration script.

        The written briefing is optimized for reading (headings, links,
        dense notation). This produces an audio-native rendition of the
        same content: a welcome, spoken transitions instead of headings,
        numbers written the way a person says them, and a sign-off.
        Returns plain text ready for TTS.
        """
        greeting = "Good morning" if time_label == "Morning" else "Good evening"
        system_prompt = f"""You are the broadcast writer for The Post-Human Briefing, a daily AI and markets news program. Convert the written briefing below into a script for a single news reader.

THIS IS NOT A SUMMARY. Preserve every theme, story, company, number, and conclusion from the written briefing. The script should carry the same information at roughly the same length; only the packaging changes from written to spoken.

STRUCTURE:
1. Open with exactly this pattern: "{greeting}. It's {date_line}, and this is The Post-Human Briefing." Then one sentence naming the most important thread of the day.
2. Render the Artificial Intelligence section, then the Markets and Macro section. Introduce each with a short spoken transition ("We begin with artificial intelligence." / "Turning to markets and the macro picture.").
3. Replace every heading with a natural spoken transition ("First...", "Next...", "One more development worth your attention...").
4. Keep each section's "why it matters" and "bottom line" content, phrased as a reader would say it ("Here's why that matters." / "The bottom line:").
5. Close with: "That's the briefing. Back {'this evening' if time_label == 'Morning' else 'tomorrow morning'}." and nothing after it.

SPOKEN-WORD RULES:
- Plain text only: no markdown, no headings, no bullets, no URLs, no citations, no stage directions, no bracketed notes, no speaker labels.
- Write numbers and symbols the way a newsreader says them: "3.2 billion dollars", "up four percent", "the S and P 500". Leave company names and common acronyms exactly as normally written ("Nvidia", "AI", "API", "GPU"); never insert hyphens or spaces to phoneticize them.
- Even, neutral register throughout: no hype, no editorializing beyond what the briefing itself says, no exclamation marks.
- Medium-length sentences that breathe. A comma where a reader would pause.
- Never mention that this was written, generated, or converted; never refer to "the briefing says"."""

        print(f"[MasterCompiler] Writing audio script ({time_label}, {date_line}) with {self._get_active_model()}...")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is today's written briefing. Write the narration script.\n\n{briefing_text}"},
        ]
        result = self._generate_with_continuation(messages, temperature=0.3)
        print(f"[MasterCompiler] Audio script done. ({len(result)} chars)")
        return result

    def synthesize_podcast_script(self, briefings_text, week_range):
        """Turn a week of briefings into a two-host conversational podcast script.

        Returns the raw script text. The first two lines are `TITLE:` and
        `DESCRIPTION:` metadata; every line after that is a dialogue turn
        prefixed with `HOST:` or `ANALYST:`.
        """
        system_prompt = f"""You are the head writer for "The Post-Human Debrief", the weekly podcast from Post-Human Engineering. You write natural, intelligent two-voice conversations at the level of the best human-made shows in this space: the analytical depth of a great research podcast, the warmth and rhythm of great public radio, zero filler.

THE TWO HOSTS (they address each other by name):
- HOST: Charon. The anchor. Male voice. Dry, precise, allergic to hype. Frames each story, keeps momentum, asks the exact question a smart listener is silently asking. Occasionally deadpan funny.
- ANALYST: Kore. The analyst. Female voice. Mechanism-first and quantitative. Explains how things actually work, challenges lazy narratives (including Charon's framing when it deserves it), and connects AI developments to market structure. Has skin in the game and says so.
They are AI voices produced by an autonomous pipeline and do not pretend otherwise, but they never make it a routine: at most one light self-aware touch per episode.

INPUT: the full text of every daily briefing published during the week of {week_range}.

YOUR JOB: distill the week into a single 25-35 minute conversation (roughly 4,500-6,000 words of dialogue) that a busy professional listens to instead of reading fourteen briefings, and enjoys enough to come back next week.

STRUCTURE:
1. Cold open, mid-thought: Charon leads with the single most consequential number or fact of the week, no greeting first. THEN the welcome: "From Post-Human Engineering, this is The Post-Human Debrief for the week of {week_range}. I'm Charon." / "And I'm Kore." Then a two-line map of where the episode is going.
2. Four to six segments, each built around one dominant narrative of the week. Weave AI and markets together where they genuinely connect; never alternate mechanically.
3. Every segment must answer three listener questions: what actually happened (specifics), why the obvious take is incomplete, and what would change our mind. Charon frames, Kore unpacks the mechanism, they push on the "so what" together.
4. Include, somewhere natural: one sustained genuine disagreement carried across several turns and resolved by naming the evidence that would settle it; one "number of the week" where Kore makes a single figure viscerally understandable; and at least one callback connecting a later segment to an earlier one.
5. Closing: each host names the one thing they are watching next week. Charon signs off with exactly: "That's the Debrief. We'll see you when the week has settled."

CONVERSATION CRAFT:
- Sound like two colleagues who respect each other and have done this for years. Mix short reactive turns ("Right.", "Which is the part that worries me.") with longer explanatory ones. No turn longer than about 120 words.
- Specific numbers, names, and dates from the briefings. No vague summarizing. When the week's data is genuinely ambiguous, say so plainly instead of manufacturing confidence.
- ANTI-AI GUARDS, STRICTLY PROHIBITED: "delve", "tapestry", "landscape", "crucial", "robust", "seamless", "leverage", "utilize", "testament", "game-changer", "at the end of the day", "let's dive in", "welcome back", "In the ever-evolving...", "It's important to note...". No em dashes.
- This is audio: no markdown, no links, no bullet lists, no headers inside the dialogue. Say numbers the way a person would ("three point two billion dollars", "the S and P 500"); keep common acronyms as written ("AI", "GPU", "Nvidia").
- Do NOT include stage directions, sound effects, music cues, or bracketed notes of any kind. Words only.

OUTPUT FORMAT (STRICT):
Line 1: TITLE: <a sharp episode title, max 60 characters, no quotes>
Line 2: DESCRIPTION: <one 25-40 word sentence describing the episode>
Then the dialogue. Every turn on its own line, prefixed with exactly `HOST: ` or `ANALYST: `. No other prefixes, no blank commentary, nothing outside this format."""

        print(f"[MasterCompiler] Writing podcast script for week of {week_range} with {self._get_active_model()}...")
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Here are all the daily briefings for the week of {week_range}. "
                    f"Write the episode.\n\n{briefings_text}"
                ),
            },
        ]
        result = self._generate_with_continuation(messages, temperature=0.6)
        print(f"[MasterCompiler] Podcast script done. ({len(result)} chars)")
        return result

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

