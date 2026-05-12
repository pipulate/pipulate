#!/usr/bin/env python3
import sys
import json
import requests
import argparse

DEFAULT_MODEL = "gemma4:latest"

# Add a global variable to store the conversation history
conversation_history = []

def get_best_llama_model(models):
    llama_models = [model for model in models if model.lower().startswith('llama')]
    return max(llama_models, key=lambda x: x.split(':')[0], default=models[0]) if llama_models else models[0]

def chat_with_ollama(input_text, prompt_template, model=DEFAULT_MODEL, timeout=90):
    # Set a fallback in case the API request fails early
    chosen_model = model if model else DEFAULT_MODEL
    
    try:
        models_response = requests.get("http://localhost:11434/api/tags", timeout=timeout)
        models_response.raise_for_status()
        
        models = [m['name'] for m in models_response.json()['models']]
        
        # Identify the target model requested
        target_model = model if model else DEFAULT_MODEL
        
        # 1. Try exact match (e.g., "gemma:latest" == "gemma:latest")
        if target_model in models:
            chosen_model = target_model
        else:
            # 2. Try partial match (e.g., "gemma4" matching "gemma4:latest")
            partial_matches = [m for m in models if m.startswith(target_model)]
            if partial_matches:
                chosen_model = partial_matches[0]
            else:
                # 3. Fall back to best llama model
                chosen_model = get_best_llama_model(models)
        
        # Add the new user message to the conversation history
        full_prompt = prompt_template.format(input_text=input_text)
        conversation_history.append({"role": "user", "content": full_prompt})

        # Send the entire conversation history
        chat_response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": chosen_model,
                "messages": conversation_history,
                "stream": False
            },
            timeout=timeout
        )
        chat_response.raise_for_status()
        
        # Get the assistant's reply and add it to the conversation history
        assistant_reply = chat_response.json()['message']['content'].strip()
        conversation_history.append({"role": "assistant", "content": assistant_reply})
        
        return assistant_reply, chosen_model
        
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}", chosen_model

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process text with Ollama LLM.")
    parser.add_argument("--prompt", required=True, help="Prompt template (use {input_text} as placeholder)")
    parser.add_argument("--format", choices=["markdown", "plain"], default="plain", help="Output format")
    parser.add_argument("--model", help=f"Specific model to use (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    input_text = sys.stdin.read().strip()
    
    # Unpack both the result and the model used
    result, used_model = chat_with_ollama(input_text, args.prompt, model=args.model)
    
    # Ensure single line output
    result = result.replace('\n', ' ').strip()
    result = ' '.join(result.split())  # Remove any double spaces
    
    if args.format == "markdown":
        result = f"## {result}"

    # Use a delimiter so init.lua can safely extract the model
    final_output = f"{result}\n__MODEL_DELIMITER__\n{used_model}"
    
    print(final_output, end='')
