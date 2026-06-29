import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.master_compiler import MasterCompiler

def summarize_news(raw_data, time_label, dry_run=False):
    if dry_run:
        print("[DRY-RUN] Mocking LLM synthesis...")
        return {
            "ai_md": "### Mock AI News\\n\\nThis is a mock summary of AI news.",
            "fin_md": "### Mock Finance News\\n\\nThis is a mock summary of Finance news."
        }
    compiler = MasterCompiler()
    
    print("Synthesizing AI News...")
    ai_md = compiler.synthesize_news(raw_data["ai"], topic="ai", time_label=time_label)
    
    print("Synthesizing Finance News...")
    fin_md = compiler.synthesize_news(raw_data["finance"], topic="finance", time_label=time_label)
    
    return {
        "ai_md": ai_md,
        "fin_md": fin_md
    }
