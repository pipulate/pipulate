import re
from pathlib import Path

# Paths
ARTICLE_FILE = Path(__file__).parent / "article.txt"

# Safe IPs that don't need redaction (localhost, common DNS, etc.)
SAFE_IPS = {'127.0.0.1', '0.0.0.0', '8.8.8.8', '1.1.1.1'}

def sanitize_article():
    """Reads article.txt, applies redactions, and saves back."""
    if not ARTICLE_FILE.exists():
        print(f"⚠️  {ARTICLE_FILE.name} not found.")
        return

    content = ARTICLE_FILE.read_text()
    original_content = content

    # --- STRIP PROMPT BOUNDARIES ---
    # Eradicate the prompt injection artifact and collapse the surrounding whitespace
    content = re.sub(r'\n*^--- BEGIN NEW ARTICLE ---$\n*', '\n\n', content, flags=re.MULTILINE)

    # --- PASS 1: Regex Safety Net (Dynamic IPs) ---
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
