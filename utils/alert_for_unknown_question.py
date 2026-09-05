from pathlib import Path

from playsound3 import playsound


def alert_for_unknown_answer():
    """Play a sound to get the user's attention when an answer is unknown."""
    playsound(Path(__file__).parent / "alert.mp3")


if __name__ == "__main__":
    alert_for_unknown_answer()
