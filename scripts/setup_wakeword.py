"""
Setup "Hey Wendy" Wake Word for Sherpa-ONNX KWS

This script:
1. Analyzes the model's tokens.txt to find BPE tokens
2. Generates the correct keyword encoding for "Hey Wendy"
3. Creates a custom keywords.txt file

Sherpa-ONNX KWS Keyword Format:
- Keywords are expressed as space-separated BPE token IDs
- Format: "token_id1 token_id2 token_id3 :keyword_name @threshold"
- The ▁ character (Unicode \u2581) represents word boundaries in BPE

Example from default keywords.txt:
  ▁HE LL O ▁WORLD :helloworld @0.5
  ▁HEY ▁SIRI :heysiri @0.5
"""

import os
import structlog
from pathlib import Path

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

def load_tokens(tokens_file: str) -> dict:
    """Load tokens.txt and return token -> id mapping"""
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


def find_token_sequence(text: str, token_to_id: dict) -> list:
    """
    Find the BPE token sequence for a given text.
    This is a greedy approach - tries to match longest tokens first.
    """
    # Normalize text
    text = text.upper()
    
    # BPE tokenization strategy for Gigaspeech model:
    # - ▁ (U+2581) marks word start
    # - Tokens can be full words or subwords
    
    words = text.split()
    all_tokens = []
    
    for i, word in enumerate(words):
        word_with_prefix = "▁" + word  # Add word boundary marker
        
        # Try to find the word as a single token first
        if word_with_prefix in token_to_id:
            all_tokens.append(word_with_prefix)
            continue
        
        # Otherwise, try to tokenize character by character with prefix on first
        pos = 0
        first_char = True
        word_tokens = []
        
        while pos < len(word):
            found = False
            # Try longest match first (greedy)
            for end in range(len(word), pos, -1):
                subword = word[pos:end]
                if first_char:
                    candidate = "▁" + subword
                else:
                    candidate = subword
                
                if candidate in token_to_id:
                    word_tokens.append(candidate)
                    pos = end
                    first_char = False
                    found = True
                    break
            
            if not found:
                # Try single character
                char = word[pos]
                if first_char:
                    candidate = "▁" + char
                else:
                    candidate = char
                
                if candidate in token_to_id:
                    word_tokens.append(candidate)
                elif char in token_to_id:
                    word_tokens.append(char)
                else:
                    logger.warning(f"Token not found for character: '{char}' in word '{word}'")
                    word_tokens.append(f"<UNK:{char}>")
                
                pos += 1
                first_char = False
        
        all_tokens.extend(word_tokens)
    
    return all_tokens


def search_similar_tokens(pattern: str, token_to_id: dict, limit: int = 20) -> list:
    """Search for tokens containing the pattern"""
    matches = []
    pattern_upper = pattern.upper()
    
    for token in token_to_id.keys():
        if pattern_upper in token.upper():
            matches.append((token, token_to_id[token]))
    
    return sorted(matches, key=lambda x: len(x[0]))[:limit]


def create_keywords_file(output_path: str, keywords: list):
    """
    Create keywords.txt file.
    
    Each keyword entry format:
    token1 token2 token3 :keyword_name @threshold
    
    Args:
        keywords: List of tuples (token_sequence, name, threshold)
                  e.g., (["▁HEY", "▁WEN", "DY"], "heywendy", 0.5)
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for token_seq, name, threshold in keywords:
            tokens_str = " ".join(token_seq)
            line = f"{tokens_str} :{name} @{threshold}\n"
            f.write(line)
            logger.info(f"Added keyword: {line.strip()}")


def main():
    # Paths
    model_dir = os.path.join(os.path.expanduser("~"), ".wendy", "models", "sherpa_kws")
    model_path = os.path.join(model_dir, "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01")
    tokens_file = os.path.join(model_path, "tokens.txt")
    keywords_output = os.path.join(model_path, "keywords_wendy.txt")
    
    # Check if model exists
    if not os.path.exists(tokens_file):
        logger.error(f"Tokens file not found: {tokens_file}")
        logger.info("Please run the voice verification script first to download the model:")
        logger.info("  python scripts/verify_voice.py")
        return
    
    logger.info("=" * 60)
    logger.info("Sherpa-ONNX Wake Word Setup for 'Hey Wendy'")
    logger.info("=" * 60)
    
    # Load tokens
    logger.info(f"Loading tokens from: {tokens_file}")
    token_to_id, id_to_token = load_tokens(tokens_file)
    logger.info(f"Loaded {len(token_to_id)} tokens")
    
    # Search for relevant tokens
    logger.info("\n" + "=" * 60)
    logger.info("Searching for 'HEY' related tokens:")
    logger.info("=" * 60)
    hey_tokens = search_similar_tokens("HEY", token_to_id)
    for token, tid in hey_tokens:
        logger.info(f"  '{token}' -> {tid}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Searching for 'WEN' related tokens:")
    logger.info("=" * 60)
    wen_tokens = search_similar_tokens("WEN", token_to_id)
    for token, tid in wen_tokens:
        logger.info(f"  '{token}' -> {tid}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Searching for 'WENDY' related tokens:")
    logger.info("=" * 60)
    wendy_tokens = search_similar_tokens("WENDY", token_to_id)
    for token, tid in wendy_tokens:
        logger.info(f"  '{token}' -> {tid}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Searching for 'DY' related tokens:")
    logger.info("=" * 60)
    dy_tokens = search_similar_tokens("DY", token_to_id)
    for token, tid in dy_tokens:
        logger.info(f"  '{token}' -> {tid}")
    
    # Try automatic tokenization
    logger.info("\n" + "=" * 60)
    logger.info("Attempting automatic tokenization of 'HEY WENDY':")
    logger.info("=" * 60)
    auto_tokens = find_token_sequence("HEY WENDY", token_to_id)
    logger.info(f"Auto tokens: {auto_tokens}")
    
    # Check if all tokens are valid
    valid_tokens = []
    all_valid = True
    for token in auto_tokens:
        if token in token_to_id:
            valid_tokens.append(token)
            logger.info(f"  ✓ '{token}' -> {token_to_id[token]}")
        else:
            all_valid = False
            logger.warning(f"  ✗ '{token}' NOT FOUND")
    
    # Also try some manual variations
    logger.info("\n" + "=" * 60)
    logger.info("Manual tokenization attempts:")
    logger.info("=" * 60)
    
    manual_attempts = [
        # Common BPE patterns for "Hey Wendy"
        ["▁HEY", "▁WEN", "DY"],
        ["▁HE", "Y", "▁WEN", "DY"],
        ["▁HE", "Y", "▁WEND", "Y"],
        ["▁HEY", "▁WENDY"],
        ["▁HE", "Y", "▁W", "EN", "DY"],
        ["▁H", "EY", "▁W", "EN", "D", "Y"],
    ]
    
    best_sequence = None
    for attempt in manual_attempts:
        all_found = True
        tokens_info = []
        for token in attempt:
            if token in token_to_id:
                tokens_info.append(f"'{token}'={token_to_id[token]}")
            else:
                tokens_info.append(f"'{token}'=NOT_FOUND")
                all_found = False
        
        status = "✓" if all_found else "✗"
        logger.info(f"  {status} {attempt}")
        logger.info(f"      -> {tokens_info}")
        
        if all_found and best_sequence is None:
            best_sequence = attempt
    
    # Create keywords file with the best sequence found
    logger.info("\n" + "=" * 60)
    logger.info("Creating keywords file:")
    logger.info("=" * 60)
    
    # Determine the best keyword sequence
    if all_valid and auto_tokens:
        keyword_tokens = valid_tokens
        logger.info(f"Using auto-detected tokens: {keyword_tokens}")
    elif best_sequence:
        keyword_tokens = best_sequence
        logger.info(f"Using manual sequence: {keyword_tokens}")
    else:
        # Fallback - try character by character
        logger.warning("Could not find optimal tokenization, trying character approach")
        keyword_tokens = []
        for i, char in enumerate("HEYWENDY"):
            if i == 0:
                candidate = "▁" + char
            elif char == "W":  # Start of new word
                candidate = "▁" + char
            else:
                candidate = char
            
            if candidate in token_to_id:
                keyword_tokens.append(candidate)
            elif char in token_to_id:
                keyword_tokens.append(char)
            else:
                logger.error(f"Cannot find token for '{char}'")
    
    # Also add some alternative wake words for testing
    keywords = [
        # Primary: Hey Wendy
        (keyword_tokens, "heywendy", 0.5),
    ]
    
    # Add fallback keywords if the primary might not work well
    # Check if common test words exist
    hello_world_tokens = []
    for token in ["▁HELLO", "▁WORLD"]:
        if token in token_to_id:
            hello_world_tokens.append(token)
    
    if len(hello_world_tokens) == 2:
        keywords.append((hello_world_tokens, "helloworld", 0.5))
    
    # Check for "OK WENDY" as alternative
    ok_wendy = []
    for token in ["▁OK", "▁WEN", "DY"]:
        if token in token_to_id:
            ok_wendy.append(token)
        elif token == "▁WEN":
            # Try alternatives
            if "▁WEND" in token_to_id:
                ok_wendy.append("▁WEND")
    
    if len(ok_wendy) >= 2:
        keywords.append((ok_wendy + (["Y"] if "Y" in token_to_id else []), "okwendy", 0.5))
    
    create_keywords_file(keywords_output, keywords)
    
    logger.info("\n" + "=" * 60)
    logger.info("SETUP COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Keywords file created: {keywords_output}")
    logger.info("")
    logger.info("To use 'Hey Wendy', update wakeword.py to use this file:")
    logger.info(f'  self.keywords_file = "{keywords_output}"')
    logger.info("")
    logger.info("You may need to tune the threshold (@0.5) based on testing:")
    logger.info("  - Lower threshold (0.3-0.4): More sensitive, more false positives")
    logger.info("  - Higher threshold (0.6-0.8): Less sensitive, fewer false positives")
    logger.info("")
    logger.info("Test the wake word by saying 'Hey Wendy' clearly!")
    
    return keywords_output


if __name__ == "__main__":
    main()
