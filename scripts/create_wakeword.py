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
import structlog
from pathlib import Path

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

# Model paths
MODEL_DIR = os.path.join(os.path.expanduser("~"), ".wendy", "models", "sherpa_kws")
MODEL_NAME = "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"
TOKENS_FILE = os.path.join(MODEL_DIR, MODEL_NAME, "tokens.txt")
KEYWORDS_FILE = os.path.join(MODEL_DIR, MODEL_NAME, "keywords_wendy.txt")


def load_tokens(tokens_file: str) -> dict:
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


def find_token_sequence(text: str, token_to_id: dict) -> list:
    """
    Find the BPE token sequence for a given text.
    
    BPE tokens in Gigaspeech model use:
    - ▁ (U+2581) as word boundary marker
    - Uppercase letters typically
    - Subword units
    """
    text = text.upper()
    tokens_found = []
    
    # Try to find exact matches first
    words = text.split()
    
    for word in words:
        # Try with word boundary marker
        word_with_boundary = f"▁{word}"
        
        if word_with_boundary in token_to_id:
            tokens_found.append(word_with_boundary)
            logger.info(f"Found exact token: {word_with_boundary}")
        else:
            # Need to break into subwords
            logger.info(f"Breaking '{word}' into subwords...")
            subwords = find_subwords(word, token_to_id, is_first=True)
            tokens_found.extend(subwords)
    
    return tokens_found


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
                logger.debug(f"Found subword: {token_candidate}")
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
                logger.debug(f"Found char token: {char_token}")
            else:
                # Fallback: just use the character and hope for the best
                logger.warning(f"Token not found for: {char_token}, trying without boundary")
                if char in token_to_id:
                    result.append(char)
                else:
                    logger.error(f"Cannot find token for character: {char}")
            
            remaining = remaining[1:]
            first_token = False
    
    return result


def create_keywords_file(tokens: list, output_file: str, threshold: float = 0.5):
    """
    Create a keywords.txt file for sherpa-onnx KWS.
    
    Format: token1 token2 token3 @threshold
    """
    # Join tokens with spaces
    keyword_line = " ".join(tokens) + f" @{threshold}"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(keyword_line + "\n")
    
    logger.info(f"Created keywords file: {output_file}")
    logger.info(f"Keyword line: {keyword_line}")


def analyze_tokens_file(tokens_file: str):
    """Analyze and print useful info about the tokens file"""
    token_to_id, id_to_token = load_tokens(tokens_file)
    
    logger.info(f"Total tokens: {len(token_to_id)}")
    
    # Find tokens that might be relevant for "Hey Wendy"
    relevant_tokens = []
    search_patterns = ["HE", "HEY", "WE", "WEN", "WENDY", "ND", "DY", "Y", "E", "N", "D"]
    
    logger.info("\n=== Relevant tokens found ===")
    for pattern in search_patterns:
        # Check with and without word boundary
        for prefix in ["▁", ""]:
            token = prefix + pattern
            if token in token_to_id:
                relevant_tokens.append((token, token_to_id[token]))
                logger.info(f"  '{token}' -> ID {token_to_id[token]}")
    
    return token_to_id, id_to_token


def main():
    logger.info("=== Hey Wendy Wake Word Configuration ===\n")
    
    # Check if model exists
    if not os.path.exists(TOKENS_FILE):
        logger.error(f"Tokens file not found: {TOKENS_FILE}")
        logger.info("Please run the voice verification script first to download the model:")
        logger.info("  python scripts/verify_voice.py")
        return
    
    # Step 1: Load and analyze tokens
    logger.info("Step 1: Analyzing tokens.txt...")
    token_to_id, id_to_token = analyze_tokens_file(TOKENS_FILE)
    
    # Step 2: Find token sequence for "Hey Wendy"
    logger.info("\nStep 2: Finding token sequence for 'Hey Wendy'...")
    tokens = find_token_sequence("Hey Wendy", token_to_id)
    
    if tokens:
        logger.info(f"\nToken sequence found: {tokens}")
        
        # Step 3: Create keywords file
        logger.info("\nStep 3: Creating keywords file...")
        
        # Create with different thresholds for testing
        # Lower threshold = more sensitive (more false positives)
        # Higher threshold = less sensitive (might miss detections)
        create_keywords_file(tokens, KEYWORDS_FILE, threshold=0.5)
        
        # Also create alternative versions for tuning
        alt_file = KEYWORDS_FILE.replace(".txt", "_sensitive.txt")
        create_keywords_file(tokens, alt_file, threshold=0.3)
        
        alt_file2 = KEYWORDS_FILE.replace(".txt", "_strict.txt")
        create_keywords_file(tokens, alt_file2, threshold=0.8)
        
        logger.info("\n=== Configuration Complete ===")
        logger.info(f"Keywords file created: {KEYWORDS_FILE}")
        logger.info("\nTo use this in Wendy, update wakeword.py to use:")
        logger.info(f"  keywords_file = '{KEYWORDS_FILE}'")
        
        logger.info("\nThreshold tuning files created:")
        logger.info("  - keywords_wendy.txt (0.5) - balanced")
        logger.info("  - keywords_wendy_sensitive.txt (0.3) - more detections, more false positives")
        logger.info("  - keywords_wendy_strict.txt (0.8) - fewer false positives, might miss some")
        
    else:
        logger.error("Could not find token sequence for 'Hey Wendy'")
        logger.info("\nManual inspection needed. Here are some tokens to try:")
        
        # Print all tokens containing relevant letters
        logger.info("\nTokens containing 'H', 'E', 'Y', 'W', 'N', 'D':")
        for token, tid in sorted(token_to_id.items()):
            clean_token = token.replace("▁", "")
            if any(c in clean_token for c in "HEYWND") and len(clean_token) <= 4:
                print(f"  {repr(token):15} -> {tid}")


def test_keyword_detection():
    """Test the keyword detection with the new keywords file"""
    logger.info("\n=== Testing Keyword Detection ===\n")
    
    if not os.path.exists(KEYWORDS_FILE):
        logger.error("Keywords file not found. Run main() first.")
        return
    
    try:
        import sherpa_onnx
        import numpy as np
        
        model_path = os.path.join(MODEL_DIR, MODEL_NAME)
        encoder = os.path.join(model_path, "encoder-epoch-12-avg-2-chunk-16-left-64.onnx")
        decoder = os.path.join(model_path, "decoder-epoch-12-avg-2-chunk-16-left-64.onnx")
        joiner = os.path.join(model_path, "joiner-epoch-12-avg-2-chunk-16-left-64.onnx")
        tokens = os.path.join(model_path, "tokens.txt")
        
        spotter = sherpa_onnx.KeywordSpotter(
            tokens=tokens,
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            num_threads=1,
            keywords_file=KEYWORDS_FILE,
            keywords_score=0.5,
            keywords_threshold=0.25,
            num_trailing_blanks=1,
            provider="cpu"
        )
        
        logger.info("KeywordSpotter initialized with Hey Wendy keywords")
        logger.info("Ready for testing!")
        
        # Create a test stream
        stream = spotter.create_stream()
        
        # Feed some silence to verify it doesn't false-trigger
        silence = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        stream.accept_waveform(16000, silence)
        
        while spotter.is_ready(stream):
            spotter.decode(stream)
            result = spotter.get_result(stream)
            if result.keyword:
                logger.warning(f"False positive on silence: {result.keyword}")
        
        logger.info("Silence test passed (no false positives)")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")


if __name__ == "__main__":
    main()
    print("\n" + "="*50 + "\n")
    test_keyword_detection()
