"""
Script to create "Hey Wendy" wake word configuration for Sherpa-ONNX KWS.

This script:
1. Reads the tokens.txt from the KWS model
2. Finds the BPE tokens needed for "Hey Wendy"
3. Creates a keywords.txt file with the proper format

Usage:
    python scripts/create_wakeword.py
"""

import os
import sys
import traceback

# Model paths
MODEL_DIR = os.path.join(os.path.expanduser("~"), ".wendy", "models", "sherpa_kws")
MODEL_NAME = "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"
TOKENS_FILE = os.path.join(MODEL_DIR, MODEL_NAME, "tokens.txt")
KEYWORDS_FILE = os.path.join(MODEL_DIR, MODEL_NAME, "keywords_wendy.txt")


def load_tokens(tokens_file: str) -> tuple:
    """Load tokens.txt and return a mapping of token -> id and id -> token"""
    token_to_id = {}
    id_to_token = {}
    
    with open(tokens_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                token = parts[0]
                token_id = int(parts[1])
                token_to_id[token] = token_id
                id_to_token[token_id] = token
    
    return token_to_id, id_to_token


def find_subwords(word: str, token_to_id: dict, is_first: bool = False) -> list:
    """
    Greedily find subword tokens for a word.
    Uses longest-match-first strategy.
    """
    result = []
    remaining = word
    first_token = is_first
    
    while remaining:
        found = False
        # Try longest possible match first
        for length in range(len(remaining), 0, -1):
            candidate = remaining[:length]
            
            # Add word boundary for first token
            if first_token:
                token_candidate = f"▁{candidate}"
            else:
                token_candidate = candidate
            
            if token_candidate in token_to_id:
                result.append(token_candidate)
                remaining = remaining[length:]
                first_token = False
                found = True
                print(f"    Found subword: {token_candidate}")
                break
        
        if not found:
            # Try single character
            char = remaining[0]
            if first_token:
                char_token = f"▁{char}"
            else:
                char_token = char
            
            if char_token in token_to_id:
                result.append(char_token)
                print(f"    Found char token: {char_token}")
            else:
                # Fallback: try without boundary
                if char in token_to_id:
                    result.append(char)
                    print(f"    Found char (no boundary): {char}")
                else:
                    print(f"    WARNING: Cannot find token for: {char}")
            
            remaining = remaining[1:]
            first_token = False
    
    return result


def find_token_sequence(text: str, token_to_id: dict) -> list:
    """Find the BPE token sequence for a given text."""
    text = text.upper()
    tokens_found = []
    
    words = text.split()
    
    for word in words:
        print(f"\n  Processing word: '{word}'")
        
        # Try with word boundary marker
        word_with_boundary = f"▁{word}"
        
        if word_with_boundary in token_to_id:
            tokens_found.append(word_with_boundary)
            print(f"    Found exact token: {word_with_boundary}")
        else:
            # Need to break into subwords
            print(f"    Breaking into subwords...")
            subwords = find_subwords(word, token_to_id, is_first=True)
            tokens_found.extend(subwords)
    
    return tokens_found


def create_keywords_file(tokens: list, output_file: str, threshold: float = 0.5):
    """Create a keywords.txt file for sherpa-onnx KWS."""
    keyword_line = " ".join(tokens) + f" @{threshold}"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(keyword_line + "\n")
    
    print(f"  Created: {output_file}")
    print(f"  Content: {keyword_line}")


def main():
    print("=" * 60)
    print("       HEY WENDY WAKE WORD CONFIGURATION")
    print("=" * 60)
    print()
    
    # Check if model exists
    print(f"Looking for tokens file at:")
    print(f"  {TOKENS_FILE}")
    print()
    
    if not os.path.exists(TOKENS_FILE):
        print("ERROR: Tokens file not found!")
        print()
        print("The KWS model needs to be downloaded first.")
        print("Please run: python scripts/verify_voice.py")
        print()
        
        # Check what exists
        print("Checking model directory...")
        if os.path.exists(MODEL_DIR):
            print(f"  Model dir exists: {MODEL_DIR}")
            for item in os.listdir(MODEL_DIR):
                print(f"    - {item}")
        else:
            print(f"  Model dir does NOT exist: {MODEL_DIR}")
        
        return False
    
    print("Tokens file found!")
    print()
    
    # Step 1: Load tokens
    print("Step 1: Loading tokens...")
    token_to_id, id_to_token = load_tokens(TOKENS_FILE)
    print(f"  Loaded {len(token_to_id)} tokens")
    print()
    
    # Show some relevant tokens
    print("Step 2: Searching for relevant tokens...")
    search_patterns = ["HEY", "HE", "WEN", "WENDY", "WE", "EN", "ND", "DY", "Y"]
    print("  Looking for tokens related to 'Hey Wendy':")
    
    found_any = False
    for pattern in search_patterns:
        for prefix in ["▁", ""]:
            token = prefix + pattern
            if token in token_to_id:
                print(f"    '{token}' -> ID {token_to_id[token]}")
                found_any = True
    
    if not found_any:
        print("    No exact matches found, will use character-level tokens")
    print()
    
    # Step 3: Find token sequence
    print("Step 3: Building token sequence for 'Hey Wendy'...")
    tokens = find_token_sequence("Hey Wendy", token_to_id)
    print()
    
    if not tokens:
        print("ERROR: Could not build token sequence!")
        return False
    
    print(f"  Token sequence: {tokens}")
    print()
    
    # Step 4: Create keywords files
    print("Step 4: Creating keywords files...")
    
    # Main file
    create_keywords_file(tokens, KEYWORDS_FILE, threshold=0.5)
    
    # Sensitive version
    sensitive_file = KEYWORDS_FILE.replace(".txt", "_sensitive.txt")
    create_keywords_file(tokens, sensitive_file, threshold=0.3)
    
    # Strict version
    strict_file = KEYWORDS_FILE.replace(".txt", "_strict.txt")
    create_keywords_file(tokens, strict_file, threshold=0.8)
    
    print()
    print("=" * 60)
    print("                    COMPLETE!")
    print("=" * 60)
    print()
    print("Keywords files created:")
    print(f"  - {os.path.basename(KEYWORDS_FILE)} (threshold 0.5 - balanced)")
    print(f"  - {os.path.basename(sensitive_file)} (threshold 0.3 - sensitive)")
    print(f"  - {os.path.basename(strict_file)} (threshold 0.8 - strict)")
    print()
    print("The wakeword service will automatically use keywords_wendy.txt")
    print("Restart the API server to apply changes.")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print()
        print("=" * 60)
        print("                    ERROR!")
        print("=" * 60)
        print()
        print(f"Exception: {type(e).__name__}: {e}")
        print()
        print("Full traceback:")
        traceback.print_exc()
        sys.exit(1)
