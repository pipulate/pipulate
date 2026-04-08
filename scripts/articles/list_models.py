import llm

print("🔍 Querying ALL available models through the Universal Adapter...\n")

try:
    # llm.get_models() returns all models configured in the environment
    # across all installed plugins (e.g., llm-gemini, llm-anthropic, llm-ollama)
    for model in llm.get_models():
        print(f"✅ {model.model_id}")
except Exception as e:
    print(f"❌ Error listing models: {e}")
