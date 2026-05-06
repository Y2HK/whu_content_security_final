import hashlib

EMOTIONS = [
    "happy",
    "neutral",
    "surprise",
    "sad",
    "angry",
    "fear",
    "disgust",
]


def analyze_emotion(seed_text: str) -> str:
    index = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest(), 16) % len(EMOTIONS)
    return EMOTIONS[index]
