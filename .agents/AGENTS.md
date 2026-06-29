
## Coding & Infrastructure Lessons Learned

- **Regex Raw Strings**: When using Python raw strings (`r"..."`) for regular expressions, never double-escape backslashes (e.g. use `r"\d{4}"`, NOT `r"\d{4}"`). The double backslash searches for a literal backslash.
- **Canary Deployments & Branch Checkouts**: When executing scripts on a separate branch (like a canary test) and switching back to `main` (`git checkout main`), locally modified tracked files will cause checkout conflicts or erroneously bring unfinished state into `main`. Always isolate artifacts (e.g. `/tmp/`), run `git checkout --force main`, and copy them back.
- **Text-to-Speech Prompt Steering**: When chunking large bodies of text for TTS APIs (e.g., Gemini TTS) by splitting on punctuation (`.`, `!`, `?`), do not prepend instructional steering tags (like `[professional news anchor. dynamic pacing.]`) beforehand. The chunking regex will split the tag mid-sentence, causing malformed syntax errors (`400 Bad Request`). Always split the raw text first, and then safely prepend the steering tag to each individual chunk before calling the API.

