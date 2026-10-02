import secrets
import string
import sys
import traceback

# Core character sets using standard ASCII printable characters
CHAR_SETS = {
    "uppercase": string.ascii_uppercase,
    "lowercase": string.ascii_lowercase,
    "digits": string.digits,
    "symbols": "!@#$%^&*()_+-=[]{}|;:,.<>?",
}

DEFAULT_MIN_LENGTH = 8


def get_yes_no_input(prompt: str) -> bool:
    """Prompt user for y/n response with strict input validation."""
    while True:
        try:
            choice = input(prompt).strip().lower()
            if choice in ("y", "yes"):
                return True
            if choice in ("n", "no"):
                return False
            print("  Invalid choice. Please type 'y' or 'n'.")
        except (KeyboardInterrupt, EOFError):
            raise


def get_character_preferences() -> dict[str, bool]:
    """Get selected character pools and enforce selecting at least one."""
    print("\n--- Step 1: Choose Character Sets ---")
    while True:
        preferences = {
            "uppercase": get_yes_no_input("Include uppercase letters (A-Z)? (y/n): "),
            "lowercase": get_yes_no_input("Include lowercase letters (a-z)? (y/n): "),
            "digits": get_yes_no_input("Include digits (0-9)? (y/n): "),
            "symbols": get_yes_no_input("Include symbols (!@#...)? (y/n): "),
        }

        if any(preferences.values()):
            return preferences

        print("\n  Error: You must select at least one character type!\n")


def get_password_length(active_pools_count: int) -> int:
    """Prompt for length and enforce bounds based on pool count."""
    min_required = max(DEFAULT_MIN_LENGTH, active_pools_count)
    print("\n--- Step 2: Choose Password Length ---")
    while True:
        try:
            raw_input = input(f"Enter length (minimum {min_required}): ").strip()
            length = int(raw_input)
            if length < min_required:
                print(f"  Length must be at least {min_required} characters.")
                continue
            return length
        except ValueError:
            print("  Invalid input. Please enter a whole number.")


def generate_password(length: int, preferences: dict[str, bool]) -> str:
    """Generate a secure password with guaranteed variety across active pools."""
    selected_pools = [
        CHAR_SETS[key] for key, enabled in preferences.items() if enabled
    ]

    # Safety check: ensure length supports selected character types
    if length < len(selected_pools):
        raise ValueError(
            f"Length ({length}) must be greater than or equal to active pools ({len(selected_pools)})."
        )

    # 1. Guarantee variety: Pick at least one character from each selected pool
    password_chars = [secrets.choice(pool) for pool in selected_pools]

    # 2. Fill remaining character slots using combined allowed characters
    combined_pool = "".join(selected_pools)
    remaining_count = length - len(password_chars)

    for _ in range(remaining_count):
        password_chars.append(secrets.choice(combined_pool))

    # 3. Securely shuffle placement using CSPRNG
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


def main() -> None:
    """CLI entry point with persistence pause and detailed error reporting."""
    print("=" * 45)
    print("   Cryptographically Secure Password Generator")
    print("=" * 45)

    try:
        # Step 1: Gather options
        preferences = get_character_preferences()
        active_pools_count = sum(preferences.values())

        # Step 2: Get safe minimum length
        length = get_password_length(active_pools_count)

        # Step 3: Generate
        password = generate_password(length, preferences)

        # Step 4: Display password
        print("\n" + "=" * 45)
        print(f"Generated Password: {password}")
        print("=" * 45)

    except (KeyboardInterrupt, EOFError):
        print("\n\nOperation cancelled. Exiting gracefully.")
    except Exception as err:
        print("\n" + "!" * 45)
        print(f"CRASH DETECTED: {err}")
        print("Detailed error traceback:")
        traceback.print_exc()
        print("!" * 45)
    finally:
        # Prevents window from closing immediately when run via double-click
        print("\n")
        input("Press Enter to exit...")
        sys.exit(0)


if __name__ == "__main__":
    main()