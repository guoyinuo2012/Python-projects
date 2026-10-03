import random

# Game constants
VALID_CHOICES = ("rock", "paper", "scissors")
WINNING_COMBINATIONS = {
    "rock": "scissors",
    "paper": "rock",
    "scissors": "paper",
}


def get_user_choice() -> str:
    """Prompt the user for input and return a validated choice."""
    while True:
        try:
            user_input = (
                input("\nEnter rock, paper, or scissors (or 'quit' to exit): ")
                .strip()
                .lower()
            )

            if user_input == "quit":
                return "quit"

            if user_input in VALID_CHOICES:
                return user_input

            raise ValueError(
                f"Invalid choice '{user_input}'. Please choose rock, paper, or scissors."
            )

        except ValueError as err:
            print(f"Error: {err}")


def get_computer_choice() -> str:
    """Randomly select and return a choice for the computer."""
    return random.choice(VALID_CHOICES)


def determine_winner(user: str, computer: str) -> str:
    """Determine the outcome of the round.

    Returns:
        'user' if the user wins,
        'computer' if the computer wins,
        'tie' if both choices match.
    """
    if user == computer:
        return "tie"

    if WINNING_COMBINATIONS[user] == computer:
        return "user"

    return "computer"


def print_round_result(user: str, computer: str, outcome: str) -> None:
    """Print the selections and result for the round."""
    print(f"\nYou chose: {user.capitalize()}")
    print(f"Computer chose: {computer.capitalize()}")

    if outcome == "tie":
        print("It's a tie!")
    elif outcome == "user":
        print(f"You win! {user.capitalize()} beats {computer}.")
    else:
        print(f"Computer wins! {computer.capitalize()} beats {user}.")


def play_game() -> None:
    """Main game loop managing score and repeated play."""
    print("=" * 40)
    print("   WELCOME TO ROCK, PAPER, SCISSORS   ")
    print("=" * 40)

    scores = {"user": 0, "computer": 0, "ties": 0}

    while True:
        user_choice = get_user_choice()

        if user_choice == "quit":
            print("\nThanks for playing!")
            print(
                f"Final Scores -> You: {scores['user']} | "
                f"Computer: {scores['computer']} | Ties: {scores['ties']}"
            )
            break

        computer_choice = get_computer_choice()
        outcome = determine_winner(user_choice, computer_choice)

        if outcome == "tie":
            scores["ties"] += 1
        else:
            scores[outcome] += 1

        print_round_result(user_choice, computer_choice, outcome)
        print(
            f"Scoreboard -> You: {scores['user']} | "
            f"Computer: {scores['computer']} | Ties: {scores['ties']}"
        )


if __name__ == "__main__":
    play_game()
