import re
import difflib

# Excerpt from the real valid cards
VALID_CARDS = {
    'abrasive', 'adaptive-strike', 'ascenders-bane', 
    'strike', 'defend', 'bash', 'cleave', 'iron-wave',
    'blood-for-blood'
}

CARD_PATTERN = re.compile(r'\[\[(.*?)\]\]')

def normalize_card_name(raw_name: str) -> str:
    name = raw_name.strip().lower()
    name = name.replace("'", "")
    name = re.sub(r'\s+', '-', name)
    return name

def test_message(text):
    matches = CARD_PATTERN.findall(text)
    results = []
    
    for match in matches:
        match_str = match.strip()
        is_upgraded = match_str.endswith('+')
        if is_upgraded:
            raw_name = match_str[:-1].strip()
        else:
            raw_name = match_str
        
        slug = normalize_card_name(raw_name)

        if slug not in VALID_CARDS:
            matches_found = difflib.get_close_matches(slug, VALID_CARDS, n=1, cutoff=0.6)
            if matches_found:
                slug = matches_found[0] # Corrected via fuzzy search
            else:
                slug = "NOT_FOUND"
                
        results.append((slug, is_upgraded))
        
    return results

print("=== Standard Tests ===")
print("Exact Match:", test_message("Check out [[ abrasive ]]"))
print("Upgraded Match:", test_message("Check out [[ abrasive+ ]]"))
print("Multiple Cards:", test_message("Multiple [[strike]] and [[defend+]]"))
print("Apostrophes and Spaces:", test_message("  [[ Ascender's Bane + ]]  "))

print("\n=== Fuzzy Matching Tests ===")
print("Typo (abrsive):", test_message("[[ abrsive ]]"))
print("Typo (Iron Wav):", test_message("[[ Iron Wav+ ]]"))
print("Typo (blood for blud):", test_message("[[ blood for blud ]]"))
print("Too Wrong (akdjfh):", test_message("[[ akdjfh ]]"))

print("\n=== No Brackets Tests ===")
print("Normal message:", test_message("Hello, how are you?"))
print("Message with single brackets:", test_message("Check out [ abrasive ]"))
print("Message without matching brackets:", test_message("Check out [[ abrasive"))
