#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║   RAMCOIN WALLET v8.0.0 — TITAN EDITION             ║
║   AES-256-GCM • PBKDF2-SHA512 • BIP39 мнемоника    ║
║   Офлайн-транзакции • Адресная книга • Авто-нонс   ║
╚══════════════════════════════════════════════════════╝
"""
import hashlib
import json
import os
import secrets
import sys
import time
import gc
from hashlib import pbkdf2_hmac
from collections import OrderedDict
from typing import Optional, Dict, List, Tuple
import urllib.request
import urllib.error
import traceback

from Crypto.Cipher import AES
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes

# ==================== КОНСТАНТЫ ====================
VERSION = "8.0.0"
NODE_URL = "http://127.0.0.1:5000"
COIN = 100_000_000
FIXED_NETWORK_FEE = int(0.001 * COIN)
DEFAULT_NODE = "http://127.0.0.1:5000"

NODES = [
    "http://127.0.0.1:5000",
    "http://90.188.115.169:5000",
]

WALLET_FILE = "ramcoin_wallet.json"
OFFLINE_TX_FILE = "ramcoin_offline_txs.json"
ADDRESS_BOOK_FILE = "ramcoin_address_book.json"

# ANSI
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RED = '\033[91m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'


# ==================== ШИФРОВАНИЕ КОШЕЛЬКА ====================
class WalletCrypto:
    SALT_SIZE = 32
    ITERATIONS = 600_000

    @staticmethod
    def encrypt(data: dict, password: str) -> str:
        salt = os.urandom(32)
        key = pbkdf2_hmac('sha512', password.encode(), salt, 600_000, dklen=32)
        cipher = AES.new(key, AES.MODE_GCM)
        ct_bytes, tag = cipher.encrypt_and_digest(json.dumps(data).encode())
        return (salt + cipher.nonce + tag + ct_bytes).hex()

    @staticmethod
    def decrypt(hex_data: str, password: str) -> Optional[dict]:
        try:
            raw = bytes.fromhex(hex_data)
            salt, nonce, tag, ct = raw[:32], raw[32:48], raw[48:64], raw[64:]
            key = pbkdf2_hmac('sha512', password.encode(), salt, 600_000, dklen=32)
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            return json.loads(cipher.decrypt_and_verify(ct, tag).decode())
        except Exception:
            return None


# ==================== ГЕНЕРАЦИЯ КЛЮЧЕЙ ====================
class KeyGenerator:
    """BIP39-подобная генерация ключей"""
    WORDLIST = [
        "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
        "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
        "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
        "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
        "advice", "aerobic", "affair", "afford", "afraid", "africa", "after", "again",
        "age", "agent", "agree", "ahead", "aim", "air", "airport", "aisle",
        "alarm", "album", "alcohol", "alert", "alien", "all", "alley", "allow",
        "almost", "alone", "alpha", "already", "also", "alter", "always", "amateur",
        "amazing", "among", "amount", "amused", "analyst", "anchor", "ancient", "anger",
        "angle", "angry", "animal", "ankle", "announce", "annual", "another", "answer",
        "antenna", "antique", "anxiety", "any", "apart", "apology", "appear", "apple",
        "approve", "april", "arch", "arctic", "area", "arena", "argue", "arm",
        "armed", "armor", "army", "around", "arrange", "arrest", "arrive", "arrow",
        "art", "artefact", "artist", "artwork", "ask", "aspect", "assault", "asset",
        "assist", "assume", "asthma", "athlete", "atom", "attack", "attend", "attitude",
        "attract", "auction", "audit", "august", "aunt", "author", "auto", "autumn",
        "average", "avocado", "avoid", "awake", "aware", "away", "awesome", "awful",
        "awkward", "axis", "baby", "bachelor", "bacon", "badge", "bag", "balance",
        "balcony", "ball", "bamboo", "banana", "banner", "bar", "barely", "bargain",
        "barrel", "base", "basic", "basket", "battle", "beach", "bean", "beauty",
        "because", "become", "beef", "before", "begin", "behave", "behind", "believe",
        "below", "belt", "bench", "benefit", "best", "betray", "better", "between",
        "beyond", "bicycle", "bid", "bike", "bind", "biology", "bird", "birth",
        "bitter", "black", "blade", "blame", "blanket", "blast", "bleak", "bless",
        "blind", "blood", "blossom", "blouse", "blue", "blur", "blush", "board",
        "boat", "body", "boil", "bomb", "bone", "bonus", "book", "boost",
        "border", "boring", "borrow", "boss", "bottom", "bounce", "box", "boy",
        "bracket", "brain", "brand", "brass", "brave", "bread", "breeze", "brick",
        "bridge", "brief", "bright", "bring", "brisk", "broccoli", "broken", "bronze",
        "broom", "brother", "brown", "brush", "bubble", "buddy", "budget", "buffalo",
        "build", "bulb", "bulk", "bullet", "bundle", "bunker", "burden", "burger",
        "burst", "bus", "business", "busy", "butter", "buyer", "buzz", "cabbage",
        "cabin", "cable", "cactus", "cage", "cake", "call", "calm", "camera",
        "camp", "can", "canal", "cancel", "candy", "cannon", "canoe", "canvas",
        "canyon", "capable", "capital", "captain", "car", "carbon", "card", "cargo",
        "carpet", "carry", "cart", "case", "cash", "casino", "castle", "casual",
        "cat", "catalog", "catch", "category", "cattle", "caught", "cause", "caution",
        "cave", "ceiling", "celery", "cement", "census", "century", "cereal", "certain",
        "chair", "chalk", "champion", "change", "chaos", "chapter", "charge", "chase",
        "chat", "cheap", "check", "cheese", "chef", "cherry", "chest", "chicken",
        "chief", "child", "chimney", "choice", "choose", "chronic", "chuckle", "chunk",
        "churn", "cigar", "cinnamon", "circle", "citizen", "city", "civil", "claim",
        "clap", "clarify", "claw", "clay", "clean", "clerk", "clever", "click",
        "client", "cliff", "climb", "clinic", "clip", "clock", "clog", "close",
        "cloth", "cloud", "clown", "club", "clump", "cluster", "clutch", "coach",
        "coast", "coconut", "code", "coffee", "coil", "coin", "collect", "color",
        "column", "combine", "come", "comfort", "comic", "common", "company", "concert",
        "conduct", "confirm", "congress", "connect", "consider", "control", "convince", "cook",
        "cool", "copper", "copy", "coral", "core", "corn", "correct", "cost",
        "cotton", "couch", "country", "couple", "course", "cousin", "cover", "coyote",
        "crack", "cradle", "craft", "cram", "crane", "crash", "crater", "crawl",
        "crazy", "cream", "credit", "creek", "crew", "cricket", "crime", "crisp",
        "critic", "crop", "cross", "crouch", "crowd", "crucial", "cruel", "cruise",
        "crumble", "crunch", "crush", "cry", "crystal", "cube", "culture", "cup",
        "cupboard", "curious", "current", "curtain", "curve", "cushion", "custom", "cute",
        "cycle", "dad", "damage", "damp", "dance", "danger", "daring", "dash",
        "daughter", "dawn", "day", "deal", "debate", "debris", "decade", "december",
        "decide", "decline", "decorate", "decrease", "deer", "defense", "define", "defy",
        "degree", "delay", "deliver", "demand", "demise", "denial", "dentist", "deny",
        "depart", "depend", "deposit", "depth", "deputy", "derive", "describe", "desert",
        "design", "desk", "despair", "destroy", "detail", "detect", "develop", "device",
        "devote", "diagram", "dial", "diamond", "diary", "dice", "diesel", "diet",
        "differ", "digital", "dignity", "dilemma", "dinner", "dinosaur", "direct", "dirt",
        "disagree", "discover", "disease", "dish", "dismiss", "disorder", "display", "distance",
        "divert", "divide", "divorce", "dizzy", "doctor", "document", "dog", "doll",
        "dolphin", "domain", "donate", "donkey", "donor", "door", "dose", "double",
        "dove", "draft", "dragon", "drama", "drastic", "draw", "dream", "dress",
        "drift", "drill", "drink", "drip", "drive", "drop", "drum", "dry",
        "duck", "dumb", "dune", "during", "dust", "dutch", "duty", "dwarf",
        "dynamic", "eager", "eagle", "early", "earn", "earth", "easily", "east",
        "easy", "echo", "ecology", "economy", "edge", "edit", "educate", "effort",
        "egg", "eight", "either", "elbow", "elder", "electric", "elegant", "element",
        "elephant", "elevator", "elite", "else", "embark", "embody", "embrace", "emerge",
        "emotion", "employ", "empower", "empty", "enable", "enact", "end", "endless",
        "endorse", "enemy", "energy", "enforce", "engage", "engine", "enhance", "enjoy",
        "enlist", "enough", "enrich", "enroll", "ensure", "enter", "entire", "entry",
        "envelope", "episode", "equal", "equip", "era", "erase", "erode", "erosion",
        "error", "erupt", "escape", "essay", "essence", "estate", "eternal", "ethics",
        "evidence", "evil", "evoke", "evolve", "exact", "example", "excess", "exchange",
        "excite", "exclude", "excuse", "execute", "exercise", "exhaust", "exhibit", "exile",
        "exist", "exit", "exotic", "expand", "expect", "expire", "explain", "expose",
        "express", "extend", "extra", "eye", "eyebrow", "fabric", "face", "faculty",
        "fade", "faint", "faith", "fall", "false", "fame", "family", "famous",
        "fan", "fancy", "fantasy", "farm", "fashion", "fat", "fatal", "father",
        "fatigue", "fault", "favorite", "feature", "february", "federal", "fee", "feed",
        "feel", "female", "fence", "festival", "fetch", "fever", "few", "fiber",
        "fiction", "field", "figure", "file", "film", "filter", "final", "find",
        "fine", "finger", "finish", "fire", "firm", "first", "fiscal", "fish",
        "fit", "fitness", "fix", "flag", "flame", "flash", "flat", "flavor",
        "flee", "flight", "flip", "float", "flock", "floor", "flower", "fluid",
        "flush", "fly", "foam", "focus", "fog", "foil", "fold", "follow",
        "food", "foot", "force", "forest", "forget", "fork", "fortune", "forum",
        "forward", "fossil", "foster", "found", "fox", "fragile", "frame", "frequent",
        "fresh", "friend", "fringe", "frog", "front", "frost", "frown", "frozen",
        "fruit", "fuel", "fun", "funny", "furnace", "fury", "future", "gadget",
        "gain", "galaxy", "gallery", "game", "gap", "garage", "garbage", "garden",
        "garlic", "garment", "gas", "gasp", "gate", "gather", "gauge", "gaze",
        "general", "genius", "genre", "gentle", "genuine", "gesture", "ghost", "giant",
        "gift", "giggle", "ginger", "giraffe", "girl", "give", "glad", "glance",
        "glare", "glass", "glide", "glimpse", "globe", "gloom", "glory", "glove",
        "glow", "glue", "goat", "goddess", "gold", "good", "goose", "gorilla",
        "gospel", "gossip", "govern", "gown", "grab", "grace", "grain", "grant",
        "grape", "grass", "gravity", "great", "green", "grid", "grief", "grit",
        "grocery", "group", "grow", "grunt", "guard", "guess", "guide", "guild",
        "guilt", "guitar", "gun", "gym", "habit", "hair", "half", "hammer",
        "hamster", "hand", "happy", "harbor", "hard", "harsh", "harvest", "hat",
        "have", "hawk", "hazard", "head", "health", "heart", "heavy", "hedgehog",
        "height", "hello", "helmet", "help", "hen", "hero", "hidden", "high",
        "hill", "hint", "hip", "hire", "history", "hobby", "hockey", "hold",
        "hole", "holiday", "hollow", "home", "honey", "hood", "hope", "horn",
        "horror", "horse", "hospital", "host", "hotel", "hour", "hover", "hub",
        "huge", "human", "humble", "humor", "hundred", "hungry", "hunt", "hurdle",
        "hurry", "hurt", "husband", "hybrid", "ice", "icon", "idea", "identify",
        "idle", "ignore", "ill", "illegal", "illness", "image", "imitate", "immense",
        "immune", "impact", "impose", "improve", "impulse", "inch", "include", "income",
        "increase", "index", "indicate", "indoor", "industry", "infant", "inflict", "inform",
        "inhale", "inherit", "initial", "inject", "injury", "inmate", "inner", "innocent",
        "input", "inquiry", "insane", "insect", "inside", "inspire", "install", "intact",
        "interest", "into", "invest", "invite", "involve", "iron", "island", "isolate",
        "issue", "item", "ivory", "jacket", "jaguar", "jar", "jazz", "jealous",
        "jeans", "jelly", "jewel", "job", "join", "joke", "journey", "joy",
        "judge", "juice", "jump", "jungle", "junior", "junk", "just", "kangaroo",
        "keen", "keep", "ketchup", "key", "kick", "kid", "kidney", "kind",
        "kingdom", "kiss", "kit", "kitchen", "kite", "kitten", "kiwi", "knee",
        "knife", "knock", "know", "lab", "label", "labor", "ladder", "lady",
        "lake", "lamp", "language", "laptop", "large", "later", "latin", "laugh",
        "laundry", "lava", "law", "lawn", "lawsuit", "layer", "lazy", "leader",
        "leaf", "learn", "leave", "lecture", "left", "leg", "legal", "legend",
        "leisure", "lemon", "lend", "length", "lens", "leopard", "lesson", "letter",
        "level", "liar", "liberty", "library", "license", "life", "lift", "light",
        "like", "limb", "limit", "link", "lion", "liquid", "list", "little",
        "live", "lizard", "load", "loan", "lobster", "local", "lock", "logic",
        "lonely", "long", "loop", "lottery", "loud", "lounge", "love", "loyal",
        "lucky", "luggage", "lumber", "lunar", "lunch", "luxury", "lyrics", "machine",
        "mad", "magic", "magnet", "maid", "mail", "main", "major", "make",
        "mammal", "man", "manage", "mandate", "mango", "mansion", "manual", "maple",
        "marble", "march", "margin", "marine", "market", "marriage", "mask", "mass",
        "master", "match", "material", "math", "matrix", "matter", "maximum", "maze",
        "meadow", "mean", "measure", "meat", "mechanic", "medal", "media", "melody",
        "melt", "member", "memory", "mention", "menu", "mercy", "merge", "merit",
        "merry", "mesh", "message", "metal", "method", "middle", "midnight", "milk",
        "million", "mimic", "mind", "minimum", "minor", "minute", "miracle", "mirror",
        "misery", "miss", "mistake", "mix", "mixed", "mixture", "mobile", "model",
        "modify", "mom", "moment", "monitor", "monkey", "monster", "month", "moon",
        "moral", "more", "morning", "mosquito", "mother", "motion", "motor", "mountain",
        "mouse", "move", "movie", "much", "muffin", "mule", "multiply", "muscle",
        "museum", "mushroom", "music", "must", "mutual", "myself", "mystery", "myth",
        "naive", "name", "napkin", "narrow", "nasty", "nation", "nature", "near",
        "neck", "need", "negative", "neglect", "neither", "nephew", "nerve", "nest",
        "net", "network", "neutral", "never", "news", "next", "nice", "night",
        "noble", "noise", "nominee", "noodle", "normal", "north", "nose", "notable",
        "note", "nothing", "notice", "novel", "now", "nuclear", "number", "nurse",
        "nut", "oak", "obey", "object", "oblige", "obscure", "observe", "obtain",
        "obvious", "occur", "ocean", "october", "odor", "off", "offer", "office",
        "often", "oil", "okay", "old", "olive", "olympic", "omit", "once",
        "one", "onion", "online", "only", "open", "opera", "opinion", "oppose",
        "option", "orange", "orbit", "orchard", "order", "ordinary", "organ", "orient",
        "original", "orphan", "ostrich", "other", "outdoor", "outer", "output", "outside",
        "oval", "oven", "over", "own", "owner", "oxygen", "oyster", "ozone",
        "pact", "paddle", "page", "pair", "palace", "palm", "panda", "panel",
        "panic", "panther", "paper", "parade", "parent", "park", "parrot", "party",
        "pass", "patch", "path", "patient", "patrol", "pattern", "pause", "pave",
        "payment", "peace", "peanut", "pear", "peasant", "pelican", "pen", "penalty",
        "pencil", "people", "pepper", "perfect", "permit", "person", "pet", "phone",
        "photo", "phrase", "physical", "piano", "picnic", "picture", "piece", "pig",
        "pigeon", "pill", "pilot", "pink", "pioneer", "pipe", "pistol", "pitch",
        "pizza", "place", "planet", "plastic", "plate", "play", "please", "pledge",
        "pluck", "plug", "plunge", "poem", "poet", "point", "polar", "pole",
        "police", "pond", "pony", "pool", "popular", "portion", "position", "possible",
        "post", "potato", "pottery", "poverty", "powder", "power", "practice", "praise",
        "predict", "prefer", "prepare", "present", "pretty", "prevent", "price", "pride",
        "primary", "print", "priority", "prison", "private", "prize", "problem", "process",
        "produce", "profit", "program", "project", "promote", "proof", "property", "prosper",
        "protect", "proud", "provide", "public", "pudding", "pull", "pulp", "pulse",
        "pumpkin", "punch", "pupil", "puppy", "purchase", "purity", "purpose", "purse",
        "push", "put", "puzzle", "pyramid", "quality", "quantum", "quarter", "question",
        "quick", "quit", "quiz", "quote", "rabbit", "raccoon", "race", "rack",
        "radar", "radio", "rail", "rain", "raise", "rally", "ramp", "ranch",
        "random", "range", "rapid", "rare", "rate", "rather", "raven", "raw",
        "razor", "ready", "real", "reason", "rebel", "rebuild", "recall", "receive",
        "recipe", "record", "recycle", "reduce", "reflect", "reform", "refuse", "region",
        "regret", "regular", "reject", "relax", "release", "relief", "rely", "remain",
        "remember", "remind", "remove", "render", "renew", "rent", "reopen", "repair",
        "repeat", "replace", "report", "require", "rescue", "resemble", "resist", "resource",
        "response", "result", "retire", "retreat", "return", "reunion", "reveal", "review",
        "reward", "rhythm", "rib", "ribbon", "rice", "rich", "ride", "ridge",
        "rifle", "right", "rigid", "ring", "riot", "ripple", "risk", "ritual",
        "rival", "river", "road", "roast", "robot", "robust", "rocket", "romance",
        "roof", "rookie", "room", "rose", "rotate", "rough", "round", "route",
        "royal", "rubber", "rude", "rug", "rule", "run", "runway", "rural",
        "sad", "saddle", "sadness", "safe", "sail", "salad", "salmon", "salon",
        "salt", "salute", "same", "sample", "sand", "satisfy", "satoshi", "sauce",
        "sausage", "save", "say", "scale", "scan", "scare", "scatter", "scene",
        "scheme", "school", "science", "scissors", "scorpion", "scout", "scrap", "screen",
        "script", "scrub", "sea", "search", "season", "seat", "second", "secret",
        "section", "security", "seed", "seek", "segment", "select", "sell", "seminar",
        "senior", "sense", "sentence", "series", "service", "session", "settle", "setup",
        "seven", "shadow", "shaft", "shallow", "share", "shed", "shell", "sheriff",
        "shield", "shift", "shine", "ship", "shiver", "shock", "shoe", "shoot",
        "shop", "short", "shoulder", "shove", "shrimp", "shrug", "shuffle", "shy",
        "sibling", "sick", "side", "siege", "sight", "sign", "silent", "silk",
        "silly", "silver", "similar", "simple", "since", "sing", "siren", "sister",
        "situate", "six", "size", "skate", "sketch", "ski", "skill", "skin",
        "skirt", "skull", "slab", "slam", "sleep", "slender", "slice", "slide",
        "slight", "slim", "slogan", "slot", "slow", "slush", "small", "smart",
        "smile", "smoke", "smooth", "snack", "snake", "snap", "sniff", "snow",
        "soap", "soccer", "social", "sock", "soda", "soft", "solar", "soldier",
        "solid", "solution", "solve", "someone", "song", "soon", "sorry", "sort",
        "soul", "sound", "soup", "source", "south", "space", "spare", "spatial",
        "spawn", "speak", "special", "speed", "spell", "spend", "sphere", "spice",
        "spider", "spike", "spin", "spirit", "split", "spoil", "sponsor", "spoon",
        "sport", "spot", "spray", "spread", "spring", "spy", "square", "squeeze",
        "squirrel", "stable", "stadium", "staff", "stage", "stairs", "stamp", "stand",
        "start", "state", "stay", "steak", "steel", "stem", "step", "stereo",
        "stick", "still", "sting", "stock", "stomach", "stone", "stool", "story",
        "stove", "strategy", "street", "strike", "strong", "struggle", "student", "stuff",
        "stumble", "style", "subject", "submit", "subway", "success", "such", "sudden",
        "suffer", "sugar", "suggest", "suit", "summer", "sun", "sunny", "sunset",
        "super", "supply", "supreme", "sure", "surface", "surge", "surprise", "surround",
        "survey", "suspect", "sustain", "swallow", "swamp", "swap", "swarm", "swear",
        "sweet", "swift", "swim", "swing", "switch", "sword", "symbol", "symptom",
        "syrup", "system", "table", "tackle", "tag", "tail", "talent", "talk",
        "tank", "tape", "target", "task", "taste", "tattoo", "taxi", "teach",
        "team", "tell", "ten", "tenant", "tennis", "tent", "term", "test",
        "text", "thank", "that", "theme", "then", "theory", "there", "they",
        "thing", "this", "thought", "three", "thrive", "throw", "thumb", "thunder",
        "ticket", "tide", "tiger", "tilt", "timber", "time", "tiny", "tip",
        "tired", "tissue", "title", "toast", "tobacco", "today", "toddler", "toe",
        "token", "tomato", "tomorrow", "tone", "tongue", "tonight", "tool", "tooth",
        "top", "topic", "topple", "torch", "tornado", "tortoise", "toss", "total",
        "tourist", "toward", "tower", "town", "toy", "track", "trade", "traffic",
        "tragic", "train", "transfer", "trap", "trash", "travel", "tray", "treat",
        "tree", "trend", "trial", "tribe", "trick", "trigger", "trim", "trip",
        "trophy", "trouble", "truck", "true", "truly", "trumpet", "trust", "truth",
        "try", "tube", "tuition", "tumble", "tuna", "tunnel", "turkey", "turn",
        "turtle", "twelve", "twenty", "twice", "twin", "twist", "two", "type",
        "typical", "ugly", "umbrella", "unable", "unaware", "uncle", "uncover", "under",
        "undo", "unfair", "unfold", "unhappy", "uniform", "unique", "unit", "universe",
        "unknown", "unlock", "until", "unusual", "unveil", "update", "upgrade", "uphold",
        "upon", "upper", "upset", "urban", "urge", "usage", "use", "used", "useful",
        "useless", "usual", "utility", "vacant", "vacuum", "vague", "valid", "valley",
        "valve", "van", "vanish", "vapor", "various", "vast", "vault", "vehicle",
        "velvet", "vendor", "venture", "venue", "verb", "verify", "version", "very",
        "vessel", "veteran", "viable", "vibrant", "vicious", "victory", "video", "view",
        "village", "vintage", "violin", "virtual", "virus", "visa", "visit", "visual",
        "vital", "vivid", "vocal", "voice", "void", "volcano", "volume", "vote",
        "voyage", "wage", "wagon", "wait", "walk", "wall", "walnut", "want",
        "warfare", "warm", "warrior", "wash", "wasp", "waste", "water", "wave",
        "way", "wealth", "weapon", "wear", "weasel", "weather", "web", "wedding",
        "weekend", "weird", "welcome", "west", "wet", "whale", "what", "wheat",
        "wheel", "when", "where", "whip", "whisper", "wide", "width", "wife",
        "wild", "will", "win", "window", "wine", "wing", "wink", "winner",
        "winter", "wire", "wisdom", "wise", "wish", "witness", "wolf", "woman",
        "wonder", "wood", "wool", "word", "work", "world", "worry", "worth",
        "wrap", "wreck", "wrestle", "wrist", "write", "wrong", "yard", "year",
        "yellow", "you", "young", "youth", "zebra", "zero", "zone", "zoo"
    ]

    @staticmethod
    def generate_mnemonic() -> str:
        return " ".join(secrets.choice(KeyGenerator.WORDLIST) for _ in range(12))

    @staticmethod
    def mnemonic_to_keys(mnemonic: str) -> Tuple[str, str]:
        clean = " ".join(mnemonic.strip().lower().split())
        seed = hashlib.pbkdf2_hmac('sha512', clean.encode(), b'ramcoin_seed_v2', 2048, dklen=64)
        seed_int = int.from_bytes(seed[:32], 'big')
        priv_key = ec.derive_private_key(seed_int, ec.SECP256K1())
        priv_hex = hex(priv_key.private_numbers().private_value)[2:].zfill(64)
        pub_bytes = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        return priv_hex, f"RAM_{pub_bytes.hex()}"


# ==================== ВАЛИДАЦИЯ ====================
def validate_address(address: str) -> Tuple[bool, str]:
    if not address.startswith("RAM_"):
        return False, "Адрес должен начинаться с 'RAM_'"
    if len(address) != 134:
        return False, f"Неверная длина ({len(address)} != 134)"
    try:
        pub_bytes = bytes.fromhex(address[4:])
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)
        return True, "✅ Валидный адрес"
    except Exception:
        return False, "Некорректный публичный ключ"


# ==================== АДРЕСНАЯ КНИГА ====================
class AddressBook:
    @staticmethod
    def load() -> Dict[str, str]:
        if os.path.exists(ADDRESS_BOOK_FILE):
            try:
                with open(ADDRESS_BOOK_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    @staticmethod
    def save(book: Dict[str, str]):
        with open(ADDRESS_BOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump(book, f, indent=2, ensure_ascii=False)

    @staticmethod
    def add(name: str, address: str):
        book = AddressBook.load()
        book[name] = address
        AddressBook.save(book)
        print(f"{GREEN}✅ {name} добавлен в адресную книгу{RESET}")

    @staticmethod
    def remove(name: str):
        book = AddressBook.load()
        if name in book:
            del book[name]
            AddressBook.save(book)
            print(f"{GREEN}✅ {name} удалён{RESET}")
        else:
            print(f"{RED}❌ {name} не найден{RESET}")

    @staticmethod
    def show():
        book = AddressBook.load()
        if book:
            print(f"\n{CYAN}📒 АДРЕСНАЯ КНИГА:{RESET}")
            for i, (name, addr) in enumerate(book.items(), 1):
                print(f"  {i}. {name}: {addr[:30]}...")
        else:
            print(f"{DIM}📒 Адресная книга пуста{RESET}")

    @staticmethod
    def find(name: str) -> Optional[str]:
        return AddressBook.load().get(name)


# ==================== СЕТЕВЫЕ ФУНКЦИИ ====================
class NetworkAPI:
    @staticmethod
    def find_node() -> str:
        for url in NODES:
            try:
                urllib.request.urlopen(f"{url}/health", timeout=2)
                return url
            except:
                pass
        return DEFAULT_NODE

    @staticmethod
    def get(path: str, node: str = None) -> Optional[dict]:
        url = f"{node or NODE_URL}{path}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read().decode())
        except:
            return None

    @staticmethod
    def post(path: str, data: dict, node: str = None) -> Optional[dict]:
        url = f"{node or NODE_URL}{path}"
        try:
            payload = json.dumps(data).encode()
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode())
            except:
                return {"status": "error", "reason": f"HTTP {e.code}"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}


# ==================== УПРАВЛЕНИЕ КОШЕЛЬКОМ ====================
class WalletManager:
    def __init__(self):
        self.node_url = NetworkAPI.find_node()
        self.wallet_data: Optional[dict] = None

    def create_wallet(self) -> Optional[dict]:
        print(f"\n{CYAN}{BOLD}🆕 СОЗДАНИЕ НОВОГО КОШЕЛЬКА{RESET}")
        mnemonic = KeyGenerator.generate_mnemonic()
        print(f"\n{YELLOW}⚠️  ЗАПИШИТЕ ЭТИ 12 СЛОВ (они не сохраняются!):{RESET}")
        print(f"{BOLD}📝 {mnemonic}{RESET}\n")
        input("Нажмите ENTER когда записали...")

        priv_hex, address = KeyGenerator.mnemonic_to_keys(mnemonic)

        while True:
            print(f"\n🔒 Придумайте пароль (мин. 8 символов):")
            pwd = input("👉 ").strip()
            if len(pwd) < 8:
                print(f"{RED}❌ Слишком короткий!{RESET}")
                continue
            if pwd != input("🔒 Повторите пароль: ").strip():
                print(f"{RED}❌ Пароли не совпадают!{RESET}")
                continue
            break

        wallet_data = {
            "address": address,
            "private_key_hex": priv_hex,
            "created_at": int(time.time()),
            "version": VERSION
        }
        encrypted = WalletCrypto.encrypt(wallet_data, pwd)
        wallet_file = {
            "type": "RAMCOIN_WALLET",
            "version": VERSION,
            "address": address,
            "crypto_data": encrypted,
            "kdf": "pbkdf2-sha512",
            "cipher": "aes-256-gcm"
        }
        with open(WALLET_FILE, 'w', encoding='utf-8') as f:
            json.dump(wallet_file, f, indent=2, ensure_ascii=False)

        print(f"\n{GREEN}{BOLD}✅ Кошелёк создан!{RESET}")
        print(f"📍 Адрес: {CYAN}{address}{RESET}")
        return wallet_data

    def load_wallet(self) -> Optional[dict]:
        if not os.path.exists(WALLET_FILE):
            print(f"{RED}❌ Файл кошелька не найден!{RESET}")
            return None

        try:
            with open(WALLET_FILE, 'r', encoding='utf-8') as f:
                wf = json.load(f)

            print(f"\n🔑 Кошелёк: {wf.get('address', 'Unknown')[:42]}...")
            for attempt in range(3):
                pwd = input(f"🔒 Пароль ({attempt + 1}/3): ").strip()
                if not pwd:
                    continue
                decrypted = WalletCrypto.decrypt(wf["crypto_data"], pwd)
                if decrypted:
                    print(f"{GREEN}✅ Кошелёк загружен!{RESET}")
                    return decrypted
                print(f"{RED}❌ Неверный пароль!{RESET}")

            return None
        except Exception as e:
            print(f"{RED}❌ Ошибка загрузки: {e}{RESET}")
            return None

    def get_balance(self, address: str) -> Tuple[Optional[int], Optional[int]]:
        data = NetworkAPI.get(f"/address/{address}", self.node_url)
        if data and "balance" in data:
            return int(data["balance"] * COIN), int(data.get("nonce", 0))
        return None, None

    def send_transaction(self, sender: str, priv_hex: str, recipient: str, amount_ram: float) -> bool:
        # Валидация
        valid, msg = validate_address(recipient)
        if not valid:
            print(f"{RED}❌ {msg}{RESET}")
            return False
        if sender == recipient:
            print(f"{RED}❌ Нельзя отправить самому себе!{RESET}")
            return False
        if amount_ram <= 0:
            print(f"{RED}❌ Сумма должна быть > 0!{RESET}")
            return False

        amount = int(round(amount_ram * COIN))
        fee = FIXED_NETWORK_FEE

        # Проверка баланса
        balance, nonce = self.get_balance(sender)
        if balance is None:
            print(f"{RED}❌ Нода недоступна!{RESET}")
            return False
        if balance < amount + fee:
            print(f"{RED}❌ Недостаточно средств!{RESET}")
            print(f"   Доступно: {balance / COIN:.8f} RAM")
            print(f"   Нужно: {(amount + fee) / COIN:.8f} RAM")
            return False

        # Создание и подпись транзакции
        tx_data = {
            "sender": sender,
            "recipient": recipient,
            "amount": amount,
            "fee": fee,
            "nonce": nonce,
            "timestamp": int(time.time())
        }

        try:
            priv_key = ec.derive_private_key(int(priv_hex, 16), ec.SECP256K1())
            signing = OrderedDict([
                ("amount", amount),
                ("fee", fee),
                ("nonce", nonce),
                ("recipient", recipient),
                ("sender", sender),
                ("timestamp", tx_data["timestamp"])
            ])
            signature = priv_key.sign(json.dumps(signing).encode(), ec.ECDSA(hashes.SHA256()))
            tx_data["signature"] = signature.hex()
        except Exception as e:
            print(f"{RED}❌ Ошибка подписи: {e}{RESET}")
            return False

        # Отправка
        print(f"\n📤 Отправка {amount_ram} RAM → {recipient[:30]}...")
        resp = NetworkAPI.post("/tx", tx_data, self.node_url)

        if resp and resp.get("status") == "ok":
            print(f"{GREEN}{BOLD}✅ Транзакция отправлена!{RESET}")
            print(f"   Сумма: {amount_ram} RAM")
            print(f"   Получатель: {recipient[:42]}...")
            return True
        else:
            reason = resp.get("reason", "неизвестная ошибка") if resp else "нет ответа"
            print(f"{RED}❌ Отклонено: {reason}{RESET}")
            return False


# ==================== ИНТЕРФЕЙС ====================
def main_menu(wm: WalletManager):
    wd = wm.wallet_data

    while True:
        print(f"\n{'='*55}")
        print(f"{CYAN}{BOLD}💼 RAMCOIN WALLET v{VERSION}{RESET}")
        print(f"{'='*55}")
        print(f"📍 {wd['address'][:42]}...")
        print(f"⛽ Комиссия сети: {FIXED_NETWORK_FEE / COIN} RAM")
        print(f"{'-'*55}")
        print(f"1. 💰 Проверить баланс")
        print(f"2. 📤 Отправить RAM")
        print(f"3. 📒 Адресная книга")
        print(f"4. 📋 Информация о кошельке")
        print(f"5. 🔒 Сменить пароль")
        print(f"6. 🚪 Выйти")
        print(f"{'-'*55}")

        choice = input("👉 ").strip()

        if choice == "1":
            balance, nonce = wm.get_balance(wd["address"])
            if balance is not None:
                print(f"\n💰 Баланс: {GREEN}{BOLD}{balance / COIN:,.8f} RAM{RESET}")
                print(f"🔢 Nonce: {nonce}")
            else:
                print(f"{YELLOW}⚠️ Нода недоступна{RESET}")

        elif choice == "2":
            print(f"\n{CYAN}📤 ОТПРАВКА RAM{RESET}")
            book = AddressBook.load()
            if book:
                AddressBook.show()
                print(f"  0. Ввести адрес вручную")
                try:
                    idx = int(input("\n👉 Выберите получателя: ").strip())
                    if 1 <= idx <= len(list(book.keys())):
                        recipient = list(book.values())[idx - 1]
                    else:
                        recipient = input("📍 Адрес (RAM_...): ").strip()
                except:
                    recipient = input("📍 Адрес (RAM_...): ").strip()
            else:
                recipient = input("📍 Адрес получателя (RAM_...): ").strip()

            try:
                amount = float(input("💎 Сумма (RAM): ").strip())
            except ValueError:
                print(f"{RED}❌ Введите число!{RESET}")
                continue

            # Подтверждение паролем
            with open(WALLET_FILE, 'r') as f:
                wf = json.load(f)
            pwd = input("🔒 Пароль для подтверждения: ").strip()
            if WalletCrypto.decrypt(wf["crypto_data"], pwd) is None:
                print(f"{RED}❌ Неверный пароль!{RESET}")
                continue

            wm.send_transaction(wd["address"], wd["private_key_hex"], recipient, amount)

        elif choice == "3":
            print(f"\n{CYAN}📒 АДРЕСНАЯ КНИГА{RESET}")
            print("1. Показать | 2. Добавить | 3. Удалить | 4. Назад")
            sub = input("👉 ").strip()
            if sub == "1":
                AddressBook.show()
            elif sub == "2":
                name = input("  Имя: ").strip()
                addr = input("  Адрес (RAM_...): ").strip()
                valid, msg = validate_address(addr)
                if valid:
                    AddressBook.add(name, addr)
                else:
                    print(f"{RED}❌ {msg}{RESET}")
            elif sub == "3":
                name = input("  Имя для удаления: ").strip()
                AddressBook.remove(name)

        elif choice == "4":
            print(f"\n{CYAN}{BOLD}📋 ИНФОРМАЦИЯ О КОШЕЛЬКЕ{RESET}")
            print(f"Версия: {wd.get('version', '?')}")
            print(f"Адрес: {wd['address']}")
            print(f"Приватный ключ: {wd.get('private_key_hex', 'скрыт')}")
            print(f"Создан: {time.ctime(wd.get('created_at', 0))}")
            print(f"Шифрование: AES-256-GCM + PBKDF2-SHA512 (600K итераций)")

        elif choice == "5":
            print(f"\n🔒 СМЕНА ПАРОЛЯ")
            with open(WALLET_FILE, 'r') as f:
                wf = json.load(f)
            old_pwd = input("Старый пароль: ").strip()
            decrypted = WalletCrypto.decrypt(wf["crypto_data"], old_pwd)
            if decrypted is None:
                print(f"{RED}❌ Неверный пароль!{RESET}")
                continue
            new_pwd = input("Новый пароль (мин. 8): ").strip()
            if len(new_pwd) < 8:
                print(f"{RED}❌ Слишком короткий!{RESET}")
                continue
            wf["crypto_data"] = WalletCrypto.encrypt(decrypted, new_pwd)
            with open(WALLET_FILE, 'w') as f:
                json.dump(wf, f, indent=2)
            print(f"{GREEN}✅ Пароль изменён!{RESET}")

        elif choice == "6":
            print(f"\n{GREEN}👋 До свидания!{RESET}")
            wd["private_key_hex"] = "0" * 64
            del wd
            gc.collect()
            break

        else:
            print(f"{RED}❌ Неверный выбор!{RESET}")


def main():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════╗
║   RAMCOIN WALLET v{VERSION}           ║
║   Titan Edition • Максимум защиты     ║
╚══════════════════════════════════════╝{RESET}
""")

    wm = WalletManager()

    if os.path.exists(WALLET_FILE):
        print("1. 📂 Загрузить существующий кошелёк")
        print("2. 🆕 Создать новый кошелёк")
        print("3. 🔄 Восстановить по мнемонике")
        print("4. 🚪 Выйти")
        choice = input("\n👉 ").strip()

        if choice == "1":
            wm.wallet_data = wm.load_wallet()
            if wm.wallet_data:
                main_menu(wm)
        elif choice == "2":
            wm.wallet_data = wm.create_wallet()
            if wm.wallet_data:
                main_menu(wm)
        elif choice == "3":
            print(f"\n{CYAN}🔄 ВОССТАНОВЛЕНИЕ ПО МНЕМОНИКЕ{RESET}")
            mnemonic = input("Введите 12 слов через пробел: ").strip()
            if len(mnemonic.split()) < 12:
                print(f"{RED}❌ Нужно ровно 12 слов!{RESET}")
                return
            priv_hex, address = KeyGenerator.mnemonic_to_keys(mnemonic)
            print(f"\n✅ Кошелёк восстановлен!")
            print(f"📍 Адрес: {address}")

            while True:
                pwd = input("\n🔒 Придумайте пароль (мин. 8): ").strip()
                if len(pwd) < 8:
                    print(f"{RED}❌ Слишком короткий!{RESET}")
                    continue
                if pwd != input("🔒 Повторите пароль: ").strip():
                    print(f"{RED}❌ Пароли не совпадают!{RESET}")
                    continue
                break

            wallet_data = {
                "address": address,
                "private_key_hex": priv_hex,
                "created_at": int(time.time()),
                "version": VERSION
            }
            encrypted = WalletCrypto.encrypt(wallet_data, pwd)
            wallet_file = {
                "type": "RAMCOIN_WALLET",
                "version": VERSION,
                "address": address,
                "crypto_data": encrypted
            }
            with open(WALLET_FILE, 'w', encoding='utf-8') as f:
                json.dump(wallet_file, f, indent=2)
            print(f"{GREEN}✅ Кошелёк сохранён!{RESET}")

            wm.wallet_data = wallet_data
            main_menu(wm)
    else:
        print(f"{YELLOW}🆕 Кошелёк не найден. Создаём новый...{RESET}")
        wm.wallet_data = wm.create_wallet()
        if wm.wallet_data:
            main_menu(wm)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{GREEN}👋 До свидания!{RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{RED}💥 Ошибка: {e}{RESET}")
        traceback.print_exc()
        sys.exit(1)