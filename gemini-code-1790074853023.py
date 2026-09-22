import string
import secrets
import sys

# Define character pools
LOWERCASE = string.ascii_lowercase
UPPERCASE = string.ascii_uppercase
DIGITS = string.digits
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

def generate_password(
    length: int = 12, 
    use_upper: bool = True, 
    use_digits: bool = True, 
    use_special: bool = True
) -> str:
    """
    Generates a cryptographically secure random password based on user choices.
    Guarantees at least one character from each selected character pool.
    """
    if length < 8:
        raise ValueError("Password length must be at least 8 characters.")

    # 1. Build the selected pools and guarantee initial characters
    pools = [LOWERCASE]  # Lowercase is always included
    guaranteed_chars = [secrets.choice(LOWERCASE)]

    if use_upper:
        pools.append(UPPERCASE)
        guaranteed_chars.append(secrets.choice(UPPERCASE))
    if use_digits:
        pools.append(DIGITS)
        guaranteed_chars.append(secrets.choice(DIGITS))
    if use_special:
        pools.append(SPECIAL_CHARS)
        guaranteed_chars.append(secrets.choice(SPECIAL_CHARS))

    # Combine all selected pools into one aggregate string for remaining characters
    combined_pool = "".join(pools)

    # 2. Fill the remaining length from the combined pool
    remaining_length = length - len(guaranteed_chars)
    random_padding = [secrets.choice(combined_pool) for _ in range(remaining_length)]

    # 3. Combine guaranteed characters with padding
    password_list = guaranteed_chars + random_padding

    # 4. Cryptographically shuffle to prevent predictable character placement
    # secrets.SystemRandom() provides CS-PRNG shuffling capabilities
    secrets.SystemRandom().shuffle(password_list)

    return "".join(password_list)


def evaluate_password_strength(password: str) -> tuple[int, str, list[str]]:
    """
    Evaluates password strength based on 5 security criteria.
    Returns: (score, visual_rating, actionable_feedback_list)
    """
    score = 0
    feedback = []

    # Check 1: Length
    if len(password) >= 12:
        score += 1
    else:
        feedback.append("Increase length to at least 12 characters.")

    # Check 2: Lowercase
    if any(c in LOWERCASE for c in password):
        score += 1
    else:
        feedback.append("Add at least one lowercase letter.")

    # Check 3: Uppercase
    if any(c in UPPERCASE for c in password):
        score += 1
    else:
        feedback.append("Add at least one uppercase letter.")

    # Check 4: Digits
    if any(c in DIGITS for c in password):
        score += 1
    else:
        feedback.append("Add at least one numeric digit.")

    # Check 5: Special Symbols
    if any(c in SPECIAL_CHARS for c in password):
        score += 1
    else:
        feedback.append("Add at least one special character (e.g., !@#$%).")

    # Map score to visual rating label
    if score <= 2:
        rating = "Weak"
    elif score <= 4:
        rating = "Moderate"
    else:
        rating = "Strong"

    return score, rating, feedback


# --- CLI Helpers & Input Handlers ---

def get_yes_no(prompt: str) -> bool:
    """Helper function to cleanly handle boolean CLI prompts."""
    while True:
        response = input(prompt).strip().lower()
        if response in ['y', 'yes', '']:
            return True
        elif response in ['n', 'no']:
            return False
        print("Invalid input. Please enter 'y' for Yes or 'n' for No.")


def handle_generation():
    """Interactive handler for generating passwords."""
    print("\n--- Password Generator ---")
    
    # Handle password length safely
    while True:
        try:
            length_input = input("Enter password length (default 12, min 8): ").strip()
            if not length_input:
                length = 12
            else:
                length = int(length_input)
            
            if length < 8:
                print("Length must be at least 8. Please try again.")
                continue
            break
        except ValueError:
            print("Invalid input! Please enter a valid integer.")

    # Get user preferences
    use_upper = get_yes_no("Include Uppercase letters? (Y/n): ")
    use_digits = get_yes_no("Include Digits? (Y/n): ")
    use_special = get_yes_no("Include Special Characters? (Y/n): ")

    # Generate password
    password = generate_password(length, use_upper, use_digits, use_special)
    print(f"\nGenerated Password: {password}")
    
    # Auto-evaluate generated password
    score, rating, _ = evaluate_password_strength(password)
    print(f"Password Strength:  {rating} ({score}/5)")


def handle_strength_check():
    """Interactive handler for testing password strength."""
    print("\n--- Password Strength Checker ---")
    password = input("Enter a password to evaluate: ")
    
    if not password:
        print("Password cannot be empty!")
        return

    score, rating, feedback = evaluate_password_strength(password)
    
    print(f"\nStrength Rating: {rating}")
    print(f"Score:           {score}/5")
    
    if feedback:
        print("\nSuggestions to improve:")
        for tip in feedback:
            print(f"  - {tip}")
    else:
        print("Great job! Your password meets all security criteria.")


def main():
    """Main application loop."""
    print("=======================================")
    print(" SECURE PASSWORD TOOL (CS-PRNG Powered)")
    print("=======================================")
    
    while True:
        print("\nSelect an option:")
        print("1. Generate a new password")
        print("2. Check strength of a password")
        print("3. Exit")
        
        choice = input("Choice (1-3): ").strip()
        
        if choice == '1':
            handle_generation()
        elif choice == '2':
            handle_strength_check()
        elif choice == '3':
            print("\nExiting utility. Stay safe!")
            sys.exit(0)
        else:
            print("Invalid choice! Please enter 1, 2, or 3.")


if __name__ == "__main__":
    main()