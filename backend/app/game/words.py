import random

WORDS = [
    "apple", "banana", "bicycle", "castle", "cat", "dog", "elephant", "guitar", "house", "island",
    "jellyfish", "kangaroo", "lighthouse", "mountain", "notebook", "octopus", "pizza", "rainbow",
    "rocket", "sandwich", "snowman", "spider", "sunflower", "telescope", "umbrella", "volcano",
    "waterfall", "zebra", "airplane", "backpack", "balloon", "bridge", "butterfly", "cactus",
    "camera", "candle", "carrot", "chair", "clock", "cloud", "cookie", "crown", "diamond",
    "dolphin", "dragon", "drum", "eagle", "envelope", "fireworks", "flamingo", "football",
    "fountain", "giraffe", "glasses", "hammer", "hamburger", "helicopter", "igloo", "key",
    "kite", "ladder", "lemon", "lion", "magnet", "mushroom", "owl", "paintbrush", "parrot",
    "penguin", "pineapple", "pirate", "pumpkin", "robot", "sailboat", "scissors", "skateboard",
    "snail", "spaceship", "strawberry", "submarine", "sword", "tent", "tiger", "tornado",
    "train", "treasure", "turtle", "unicorn", "violin", "whale", "windmill", "wizard",
    "ice cream", "hot air balloon", "traffic light", "teddy bear", "palm tree", "fire truck",
    "birthday cake", "light bulb", "roller coaster", "solar system",
]


def pick_word(used: set[str]) -> str:
    pool = [w for w in WORDS if w not in used] or WORDS
    return random.choice(pool)
