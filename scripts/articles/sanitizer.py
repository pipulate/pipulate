import re
from pathlib import Path

# Paths
SECRETS_FILE = Path.home() / "repos/nixos/secrets.nix"
ARTICLE_FILE = Path(__file__).parent / "article.txt"

# Safe IPs that don't need redaction (localhost, common DNS, etc.)
SAFE_IPS = {'127.0.0.1', '0.0.0.0', '8.8.8.8', '1.1.1.1'}

def get_secrets_map():
    """Parses secrets.nix for key-value pairs to redact."""
    secrets_map = {}
    if not SECRETS_FILE.exists():
        print(f"⚠️  Secrets file not found at {SECRETS_FILE}. Skipping nix-based redaction.")
        return secrets_map

    content = SECRETS_FILE.read_text()
    
    # Extract patterns: key = value; or key = "value";
    matches = re.findall(r'(\w+)\s*=\s*"?([^";\s]+)"?;', content)
    
    for key, value in matches:
        # Only redact keys that imply sensitive data
        if any(x in key.lower() for x in ['id', 'ip', 'password', 'token', 'secret']):
            # Convert camelCase to [SNAKE_CASE_PLACEHOLDER]
            label = f"[{re.sub(r'(?<!^)(?=[A-Z])', '_', key).upper()}]"
            secrets_map[value] = label
            
    return secrets_map

def sanitize_article():
    """Reads article.txt, applies redactions, and saves back."""
    if not ARTICLE_FILE.exists():
        print(f"⚠️  {ARTICLE_FILE.name} not found.")
        return

    secrets = get_secrets_map()
    content = ARTICLE_FILE.read_text()
    original_content = content

    # --- PASS 1: Defined Secrets ---
    if secrets:
        for value, label in secrets.items():
            # Guard: Don't redact very short strings (e.g., "0", "1", "80") 
            # that might appear naturally in prose or code.
            if len(value) > 3 and value in content:
                content = content.replace(value, label)

    # --- PASS 2: Regex Safety Net (Dynamic IPs) ---
    def ip_replacer(match):
        ip = match.group(0)
        if ip in SAFE_IPS:
            return ip
        return "[REDACTED_IP]"

    # Matches standard IPv4 addresses (e.g., 192.168.10.100)
    ip_pattern = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
    content = ip_pattern.sub(ip_replacer, content)

    # --- CHECK AND SAVE ---
    if content != original_content:
        ARTICLE_FILE.write_text(content)
        print(f"✅ Article sanitized! (Secrets and loose IP addresses redacted)")
    else:
        print(f"ℹ️  No secrets or exposed IP addresses found. Article is already clean.")

if __name__ == "__main__":
    sanitize_article()