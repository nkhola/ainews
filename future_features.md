# Future Features for The Post-Human Briefing™

## 1. Weekly Two-Host Conversational Podcast
- **Description:** Feed a full week of daily briefings (7-14 files) into the LLM to generate a single 30-45 minute conversational script (NPR style) featuring two distinct Gemini voices (e.g., Puck as anchor, Kore as analyst).
- **Cost Estimate (Vertex AI Gemini 2.5 Flash TTS):**
  - Audio output is billed at 25 tokens per second.
  - A 45-minute podcast = 2,700 seconds.
  - 2,700 seconds * 25 tokens/sec = 67,500 output tokens.
  - At $10.00 per 1M output tokens, the audio generation cost is roughly **$0.68 per 45-minute podcast**.
- **Feasibility:** Extremely feasible. The primary challenge is context window size for the LLM to process a week of briefings, but Gemini 1.5 Pro/Flash handles up to 1M/2M tokens effortlessly.

## 2. Personalized Email Newsletters
- **Description:** Allow users to subscribe with specific topics of interest (e.g., "Robotics", "Options Trading").
- **Mechanism:** A scheduled GitHub Action runs daily, taking the scraped data and using the LLM to filter and format a personalized email template. It uses a service like SendGrid or Resend to deliver the text and MP3 directly to inboxes.

## 3. The AI Wiki & Knowledge Weaving (Tabled for now)
- **Description:** Use the `MasterCompiler` agent to extract persistent entities from the daily news and build an interlinked Wikipedia-style knowledge graph. Automatically updates "Trade-offs & Evolution" sections as stories develop over time.

## Completed Features

### 1. Automated Canary Deployments & CI/CD
- **Description:** Implemented GitHub actions for running tests on a canary deployment and automatically promoting to production if tests pass. This ensures safe continuous delivery of AI-generated assets and code changes.

### 2. Architectural Modularization & State Capture
- **Description:** Broke down the 800-line monolithic `generate_site.py` script into discrete modules within `.scripts/pipeline/` (`crawler.py`, `summarizer.py`, `html_builder.py`, `tts_generator.py`).
- **State Capture:** Implemented local state capturing (saving raw crawler JSON data and LLM summaries). The orchestrator `pipeline.py` automatically loads these artifacts if available, drastically reducing redundant calls to expensive APIs (Vertex AI) when re-running the pipeline on the same day.
- **Dry-run Execution:** Added a `--dry-run` flag to `pipeline.py` which mocks LLM and TTS requests to allow safe, fast local testing without consuming AI quotas.
