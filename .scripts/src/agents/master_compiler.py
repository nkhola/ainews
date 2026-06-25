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
        rate_limit_count = 0

        for attempt in range(rate_limit_max_retries):
            try:
                return self._get_active_client().chat.completions.create(
                    model=self._get_active_model(),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except RateLimitError as e:
                rate_limit_count += 1
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
                if rate_limit_count >= 2 and not self._using_fallback:
                    if self._switch_to_fallback():
                        continue

                if attempt == rate_limit_max_retries - 1:
                    raise
                print(f"[MasterCompiler] Waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
                backoff = min(backoff * 2, 300)  # cap at 5 minutes
            except Exception as e:
                print(f"[MasterCompiler] API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
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
        print(f"[MasterCompiler] Pretending to synthesize {topic} ({time_label}) briefing...")
        if topic == "ai" and time_label == "Morning":
            return """### Executive Summary
The frontier model landscape is increasingly defined by a convergence of hardware optimization and specialized agentic capabilities. While OpenAI and Broadcom's custom silicon venture signals a long-term strategic shift towards vertical integration for inference efficiency, Anthropic's integration of persistent, multiplayer agents via Claude Tag and DeepMind's introduction of computer use in Gemini 3.5 Flash point to a near-term future dominated by autonomous, proactive systems embedded directly within enterprise workflows.

### Hardware Vertical Integration & The Inference Bottleneck
The announcement of [Jalapeño, a custom LLM-optimized inference chip co-developed by OpenAI and Broadcom](https://openai.com/index/openai-broadcom-jalapeno-inference-chip), marks a critical inflection point in the AI hardware supply chain. As model sizes scale logarithmically and token generation demands scale exponentially, relying solely on general-purpose GPUs for inference is becoming economically untenable. This custom silicon play is a direct attempt to bend the inference cost curve, optimizing for memory bandwidth and low-latency token generation at scale.

#### Why it matters
By securing proprietary silicon optimized specifically for transformer architectures, OpenAI is moving to insulate itself from broader supply chain volatility while fundamentally improving the unit economics of deploying frontier models at enterprise scale.

### Agentic Architectures: From Chatbots to Proactive Participants
The paradigm is shifting from reactive, single-turn chat interfaces to proactive, persistent agentic workflows. DeepMind's [introduction of computer use in Gemini 3.5 Flash](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-computer-use-gemini-3-5-flash/) represents a significant leap in a model's ability to navigate unstructured UI environments. Concurrently, Anthropic has launched [Claude Tag, bringing multiplayer, proactive, and persistent agents directly into Slack](https://www.anthropic.com/news/introducing-claude-tag). This moves the LLM from an external tool to a continuously participating collaborator within existing communication channels.

#### Why it matters
These developments indicate a rapid maturation of the "Agent Cloud." The value of a model is no longer just its parametric knowledge, but its ability to execute complex, multi-step actions and maintain stateful context within human-in-the-loop systems.

### Trade-offs & Evolution: Intellectual Property vs. Open Ecosystems
As capabilities advance, the tension over intellectual property and model extraction is escalating. [Anthropic's allegation that Alibaba illicitly extracted Claude's capabilities](https://www.reuters.com/world/china/anthropic-says-alibaba-illicitly-extracted-claude-ai-model-capabilities-2026-06-24/) highlights the vulnerability of API-based business models to model distillation and data scraping by sophisticated state-backed actors. This contrasts sharply with the [Databricks perspective that the frontier ecosystem must remain open](https://www.latent.space/p/databricks) to foster broader adoption of agentic architectures. We are witnessing a bifurcation: closed labs fiercely defending their proprietary weights and training data, while the open-source community, driven by platforms like Databricks, pushes for commoditized foundation models to enable localized, sovereign AI deployments.

### The Bottom Line
The competitive moat in AI is shifting from pure parameter count to the combined advantages of proprietary inference silicon and deep integration into stateful, multi-agent enterprise workflows."""
        elif topic == "finance" and time_label == "Morning":
            return """### Executive Summary
The geopolitical fragmentation of global supply chains continues to manifest in market volatility, particularly as the US-China tech rivalry intensifies and resource nationalism takes center stage. Concurrently, shifting macroeconomic indicators, specifically regarding inflation and central bank policy, are forcing a rapid re-evaluation of long-duration asset valuations and sector rotations.

### The Weaponization of the Supply Chain
The "Pax Silica" initiative, which sees [EU allies joining a US pact to break reliance on Chinese AI supply chains](https://www.ft.com/content/681c33a0-dcb4-4a81-9aa0-8a9172f7e5bc), represents a structural, likely permanent, realignment of global trade. The immediate retaliation by Beijing, which included [targeting US rare earths firms](https://www.bloomberg.com/news/videos/2026-06-23/china-targets-us-rare-earths-firms-in-signal-to-pentagon-video) and [throttling key mineral exports to Japan](https://www.bloomberg.com/news/articles/2026-06-23/xi-pressures-takaichi-by-throttling-key-mineral-exports-to-japan), underscores the vulnerability of the technology sector to strategic resource embargoes. 

#### Why it matters
This tit-for-tat escalation confirms that the semiconductor and critical mineral supply chains are now primary theaters of geopolitical conflict, mandating that investors price a significant "sovereignty premium" into hardware manufacturers and resource extractors.

### Capital Allocation Amidst Uncertainty
The market's appetite for high-growth, capital-intensive ventures remains robust, yet increasingly discerning. The successful pricing of [SpaceX's $25 billion debt deal, one of the year's largest AI-adjacent offerings](https://www.marketwatch.com/story/spacex-reveals-pricing-details-for-what-could-be-one-of-the-years-biggest-debt-deals-8c027a85?mod=mw_rss_topstories), indicates ample liquidity for perceived category winners. However, the broader market structure is shifting. The inclusion of [Alphabet's stock in the Dow Jones Industrial Average](https://www.marketwatch.com/story/alphabets-stock-is-set-to-join-the-dow-heres-which-company-is-getting-the-boot-73453ca7?mod=mw_rss_topstories) reflects the undeniable macroeconomic dominance of mega-cap tech, even as warnings surface regarding the [hidden decay and concentration risks in passive tech ETFs](https://247wallst.com/investing/2026/06/23/youre-probably-paying-twice-for-nvidia-apple-and-microsoft-without-realizing-it/).

#### Why it matters
Investors are navigating a complex bifurcation: enormous capital is available for structural winners, but the concentration of market cap in a few tech giants increases the systemic vulnerability to sector-specific shocks or regulatory interventions.

### The Bottom Line
Geopolitical friction is no longer a tail risk but the primary driver of supply chain restructuring and capital reallocation, fundamentally altering the risk profile of the technology and materials sectors."""
        elif topic == "ai" and time_label == "Evening":
            return """### Executive Summary
The rapid proliferation of local LLMs and browser-based inference is democratizing advanced capabilities, challenging the dominance of centralized cloud APIs. Simultaneously, the integration of rigorous, neuro-symbolic reasoning into agentic workflows is addressing the critical flaws of current LLM-based autonomous systems.

### The Rise of the Sovereign Agent
The barrier to entry for robust local inference continues to plummet. We are seeing remarkable optimization, such as [the porting of the Moebius 0.2B image model to run entirely in the browser via WebGPU](https://simonwillison.net/2026/Jun/22/porting-moebius/#atom-everything). Furthermore, the development of [persistent SQLite databases in the browser using OPFS and Pyodide](https://simonwillison.net/2026/Jun/23/opfs-pyodide/#atom-everything) creates a foundation for sophisticated, offline-first web applications that leverage local models for data processing without privacy compromises. 

#### Why it matters
This decoupling of capability from cloud infrastructure enables "sovereign agents" that can process sensitive local data with minimal latency, unlocking use cases in healthcare, legal, and personal finance that were previously blocked by data residency concerns.

### Neuro-Symbolic Integration for Reliable Autonomy
Current LLM agents struggle with hallucinations and logical drift during multi-step execution. The introduction of [Neuro-Symbolic Drive, a framework that supervises a driving VLA with rule-grounded reasoning traces](https://arxiv.org/abs/2606.23938), represents a vital correction. By forcing the neural model to adhere to the explicit, deterministic logic of classical rule-based planners, the system achieves a structurally sound connection between its reasoning rationale and its generated motion.

#### Why it matters
The transition from fragile, purely probabilistic LLM agents to reliable, neuro-symbolic autonomous systems is the necessary prerequisite for deploying AI in safety-critical environments like autonomous driving and robotic surgery.

### Trade-offs & Evolution: Red-Teaming the Agentic System
As models transition into autonomous agents, traditional evaluation metrics fail. The [introduction of RIFT-Bench for dynamic red-teaming of Agentic AI Systems](https://arxiv.org/abs/2606.23927) highlights that vulnerabilities now lie in the system's architecture and decision-making loop, not just the base model's weights. We are evolving from evaluating *what a model knows* to evaluating *what a system can be tricked into doing*, requiring a shift from static benchmarks to adversarial, graph-based security audits.

### The Bottom Line
The future of AI deployment is increasingly local, specialized, and neuro-symbolic, prioritizing verifiable reliability and privacy over raw, unstructured scale."""
        elif topic == "finance" and time_label == "Evening":
            return """### Executive Summary
Energy security and infrastructure resilience are emerging as the defining macro constraints on continued economic expansion and technological scaling. The intersection of surging power demand from the AI sector and the fragility of global energy transit routes is creating a new paradigm for infrastructure investment.

### The AI Power Squeeze and Nuclear Renaissance
The staggering energy requirements of frontier AI models are forcing a structural shift in corporate energy procurement. The [landmark agreement between Constellation Energy and Walmart for 176 megawatts of nuclear power](https://www.fool.com/investing/2026/06/23/constellation-energy-inks-a-nuclear-power-deal-with-walmart-heres-what-investors-need-to-know/?.tsrc=rss) exemplifies the desperation for reliable, carbon-free baseload generation. This is occurring against a backdrop of increasing grid instability, as highlighted by the [UK's rare summer power supply warning amidst heat wave strains](https://www.bloomberg.com/news/articles/2026-06-23/uk-issues-energy-supply-warning-as-heat-wave-strains-power-grid).

#### Why it matters
The technological bottleneck for AI scaling is shifting from silicon fabrication to power generation and transmission, making long-term purchase agreements with nuclear and diverse renewable providers a critical strategic moat for hyperscalers and heavy industry.

### Geopolitical Chokepoints and Energy Logistics
While the AI sector scrambles for domestic power, the broader economy remains hostage to vulnerable global transit routes. The revelation that [nearly 1,200 cargo ships and $125 billion in goods were stranded by the closure of the Strait of Hormuz](https://www.ft.com/content/4d3dd2b7-cb6b-410b-8c15-203904f32294) exposes the extreme fragility of maritime logistics. Even with [reports of peace talks easing transit](https://www.bloomberg.com/news/articles/2026-06-23/latest-oil-market-news-and-analysis-for-june-24), the systemic risk has prompted calls from industry leaders, like the CEO of TotalEnergies, to [invest heavily in bypass pipelines across the Middle East](https://seekingalpha.com/news/4606441-totalenergies-must-spend-on-middle-east-pipelines-that-bypass-hormuz-ceo-says?utm_source=feed_news_all&amp;utm_medium=referral&amp;feed_item_type=news).

#### Why it matters
The persistent threat to maritime chokepoints is driving a massive, long-term capital expenditure cycle aimed at rerouting global energy logistics and building redundant infrastructure, structurally increasing the baseline cost of global trade.

### The Bottom Line
The dual imperatives of securing massive power generation for the AI transition and mitigating the risk of geopolitical chokepoints in the fossil fuel supply chain are initiating a historic, multi-decade infrastructure supercycle."""

