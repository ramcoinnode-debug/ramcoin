#!/usr/bin/env python3
"""
RAMCOIN WALLET v7.1.0 — SECURITY & COMPATIBILITY FIX
"""
import urllib.request
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.request
import urllib.error
from hashlib import pbkdf2_hmac
from Crypto.Cipher import AES
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes

# ==================== КОНСТАНТЫ ====================
VERSION = "7.1.0"

NODES = [
    "http://127.0.0.1:5000",
    "http://90.188.115.169:5000",
]


def find_node():
    for url in NODES:
        try:
            urllib.request.urlopen(f"{url}/health", timeout=1)
            return url
        except:
            pass
    return "http://90.188.115.169:5000"


NODE_URL = find_node()
WALLET_FILE = "ramcoin_wallet.json"
OFFLINE_TX_FILE = "ramcoin_offline_txs.json"
ADDRESS_BOOK_FILE = "ramcoin_address_book.json"
COIN = 100_000_000
FIXED_NETWORK_FEE = int(0.001 * COIN)  # Изменено на int для совместимости
DEVELOPER_SHARE = 10
MINER_SHARE = 90

# ANSI
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RED = '\033[91m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'


# ==================== ШИФРОВАНИЕ ====================
class CryptoWallet:
    SALT_SIZE = 32
    ITERATIONS = 600_000

    @staticmethod
    def encrypt_data(data, password):
        salt = os.urandom(CryptoWallet.SALT_SIZE)
        key = pbkdf2_hmac('sha512', password.encode(), salt, CryptoWallet.ITERATIONS, dklen=32)
        cipher = AES.new(key, AES.MODE_GCM)
        ct_bytes, tag = cipher.encrypt_and_digest(data.encode())
        return (salt + cipher.nonce + tag + ct_bytes).hex()

    @staticmethod
    def decrypt_data(hex_data, password):
        try:
            raw = bytes.fromhex(hex_data)
            salt = raw[:32]
            nonce = raw[32:48]
            tag = raw[48:64]
            ct = raw[64:]
            key = pbkdf2_hmac('sha512', password.encode(), salt, CryptoWallet.ITERATIONS, dklen=32)
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ct, tag).decode()
        except Exception:
            return None


# ==================== ГЕНЕРАЦИЯ КЛЮЧЕЙ ====================
class KeyGenerator:
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
        "together", "toilet", "token", "tomato", "tomorrow", "tone", "tongue", "tonight",
        "tool", "tooth", "top", "topic", "topple", "torch", "tornado", "tortoise",
        "toss", "total", "tourist", "toward", "tower", "town", "toy", "track",
        "trade", "traffic", "tragic", "train", "transfer", "trap", "trash", "travel",
        "tray", "treat", "tree", "trend", "trial", "tribe", "trick", "trigger",
        "trim", "trip", "trophy", "trouble", "truck", "true", "truly", "trumpet",
        "trust", "truth", "try", "tube", "tuition", "tumble", "tuna", "tunnel",
        "turkey", "turn", "turtle", "twelve", "twenty", "twice", "twin", "twist",
        "two", "type", "typical", "ugly", "umbrella", "unable", "unaware", "uncle",
        "uncover", "under", "undo", "unfair", "unfold", "unhappy", "uniform", "unique",
        "unit", "universe", "unknown", "unlock", "until", "unusual", "unveil", "update",
        "upgrade", "uphold", "upon", "upper", "upset", "urban", "urge", "usage",
        "use", "used", "useful", "useless", "usual", "utility", "vacant", "vacuum",
        "vague", "valid", "valley", "valve", "van", "vanish", "vapor", "various",
        "vast", "vault", "vehicle", "velvet", "vendor", "venture", "venue", "verb",
        "verify", "version", "very", "vessel", "veteran", "viable", "vibrant", "vicious",
        "victory", "video", "view", "village", "vintage", "violin", "virtual", "virus",
        "visa", "visit", "visual", "vital", "vivid", "vocal", "voice", "void",
        "volcano", "volume", "vote", "voyage", "wage", "wagon", "wait", "walk",
        "wall", "walnut", "want", "warfare", "warm", "warrior", "wash", "wasp",
        "waste", "water", "wave", "way", "wealth", "weapon", "wear", "weasel",
        "weather", "web", "wedding", "weekend", "weird", "welcome", "west", "wet",
        "whale", "what", "wheat", "wheel", "when", "where", "whip", "whisper",
        "wide", "width", "wife", "wild", "will", "win", "window", "wine",
        "wing", "wink", "winner", "winter", "wire", "wisdom", "wise", "wish",
        "witness", "wolf", "woman", "wonder", "wood", "wool", "word", "work",
        "world", "worry", "worth", "wrap", "wreck", "wrestle", "wrist", "write",
        "wrong", "yard", "year", "yellow", "you", "young", "youth", "zebra",
        "zero", "zone", "zoo"
    ]

    @staticmethod
    def generate_mnemonic():
        return " ".join(secrets.choice(KeyGenerator.WORDLIST) for _ in range(12))

    @staticmethod
    def get_keys(mnemonic):
        clean = " ".join(mnemonic.strip().lower().split())
        seed = hashlib.pbkdf2_hmac('sha512', clean.encode(), b'ramcoin_seed_derivation', 2048, dklen=64)
        seed_int = int.from_bytes(seed[:32], 'big')
        priv_key = ec.derive_private_key(seed_int, ec.SECP256K1())
        priv_hex = hex(priv_key.private_numbers().private_value)[2:].zfill(64)
        pub_key = priv_key.public_key()
        pub_bytes = pub_key.public_bytes(encoding=serialization.Encoding.X962,
                                         format=serialization.PublicFormat.UncompressedPoint)
        address = f"RAM_{pub_bytes.hex()}"
        return priv_hex, address


# ==================== ВАЛИДАЦИЯ ====================
def validate_address(address):
    if not address.startswith("RAM_"): return False, "Адрес должен начинаться с 'RAM_'"
    pub_hex = address[4:]
    if len(pub_hex) != 130: return False, f"Неверная длина"
    try:
        pub_bytes = bytes.fromhex(pub_hex)
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)
        return True, "Валидный адрес"
    except:
        return False, "Некорректный ключ"


# ==================== АДРЕСНАЯ КНИГА ====================
class AddressBook:
    @staticmethod
    def load():
        if os.path.exists(ADDRESS_BOOK_FILE):
            try:
                with open(ADDRESS_BOOK_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    @staticmethod
    def save(book):
        with open(ADDRESS_BOOK_FILE, "w", encoding="utf-8") as f: json.dump(book, f, indent=4)

    @staticmethod
    def add(name, address):
        book = AddressBook.load();
        book[name] = address;
        AddressBook.save(book)
        print(f"✅ {name} добавлен")

    @staticmethod
    def remove(name):
        book = AddressBook.load()
        if name in book:
            del book[name]; AddressBook.save(book); print(f"✅ {name} удалён")
        else:
            print(f"❌ {name} не найден")

    @staticmethod
    def list_all():
        book = AddressBook.load()
        if book:
            print("\n📒 АДРЕСНАЯ КНИГА:")
            for name, addr in book.items(): print(f"  {name}: {addr[:30]}...")
        else:
            print("📒 Адресная книга пуста")

    @staticmethod
    def find(name):
        return AddressBook.load().get(name, None)


# ==================== СЕТЕВЫЕ ФУНКЦИИ ====================
def api_get(path):
    try:
        req = urllib.request.Request(f"{NODE_URL}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode())
    except:
        return None


def api_post(path, data):
    try:
        req = urllib.request.Request(f"{NODE_URL}{path}", data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except:
            return {"status": "error", "reason": f"HTTP {e.code}"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def get_balance(address):
    data = api_get(f"/address/{address}")
    if data and "balance" in data: return int(data["balance"] * COIN), int(data.get("nonce", 0))
    return None, None


def get_pending_transactions():
    return api_get("/pending") or []


def get_pending_weight(address):
    weight = 0
    for tx in get_pending_transactions():
        if tx.get("sender") == address: weight += int(tx.get("amount", 0)) + FIXED_NETWORK_FEE
    return weight


def get_transaction_history(address):
    data = api_get(f"/address/{address}")
    if data and "transactions" in data: return data["transactions"]
    return []


# ==================== ОФЛАЙН ТРАНЗАКЦИИ ====================
def push_offline_transaction(tx):
    txs = []
    if os.path.exists(OFFLINE_TX_FILE):
        try:
            with open(OFFLINE_TX_FILE, "r", encoding="utf-8") as f:
                txs = json.load(f)
        except:
            txs = []
    txs.append(tx)
    with open(OFFLINE_TX_FILE, "w", encoding="utf-8") as f:
        json.dump(txs, f, indent=4)


def sync_offline_transactions():
    if not os.path.exists(OFFLINE_TX_FILE): return
    try:
        with open(OFFLINE_TX_FILE, "r", encoding="utf-8") as f:
            txs = json.load(f)
    except:
        return
    if not txs: return
    print(f"\n⏳ Отложенных TX: {len(txs)}. Отправка...")
    successful = []
    for tx in txs:
        resp = api_post("/tx", tx)
        if resp and resp.get("status") == "ok":
            print(f"  ✅ TX (nonce: {tx.get('nonce')}) доставлена"); successful.append(tx)
        else:
            print(f"  ❌ TX (nonce: {tx.get('nonce')}) — {resp.get('reason', '?') if resp else 'no response'}"); break
    remaining = [t for t in txs if t not in successful]
    with open(OFFLINE_TX_FILE, "w", encoding="utf-8") as f:
        json.dump(remaining, f, indent=4)


# ==================== УПРАВЛЕНИЕ КОШЕЛЬКОМ ====================
# Исправлено: мнемоника больше не сохраняется
def save_wallet_file(address, private_key, last_balance=0, last_nonce=0, password=None):
    if not password:
        while True:
            print("\n🔒 Придумайте пароль (мин. 8 символов):")
            password = input("👉 ").strip()
            if len(password) < 8: print("❌ Слишком короткий!"); continue
            if password != input("🔒 Повторите пароль: ").strip(): print("❌ Пароли не совпадают!"); continue
            break
    wallet_data = {"address": address, "private_key_hex": private_key,
                   "last_balance": int(last_balance), "last_nonce": int(last_nonce),
                   "created_at": int(time.time()), "version": VERSION}
    encrypted = CryptoWallet.encrypt_data(json.dumps(wallet_data), password)
    wallet_file_content = {"type": "RAMCOIN_WALLET", "version": VERSION, "address": address,
                           "crypto_data": encrypted, "kdf": "pbkdf2-sha512", "cipher": "aes-256-gcm"}
    with open(WALLET_FILE, "w", encoding="utf-8") as f:
        json.dump(wallet_file_content, f, indent=4)
    return wallet_data


def create_new_wallet():
    print(f"\n{CYAN}🆕 СОЗДАНИЕ КОШЕЛЬКА{RESET}")
    mnemonic = KeyGenerator.generate_mnemonic()
    print(f"{YELLOW}⚠️  ЗАПИШИТЕ 12 СЛОВ (они не сохраняются!):{RESET}\n📝 {BOLD}{mnemonic}{RESET}\n")
    input("Нажмите ENTER когда запишете...")
    priv_hex, address = KeyGenerator.get_keys(mnemonic)
    print(f"\n✅ Кошелёк создан!\n📍 Адрес: {address}")
    return save_wallet_file(address, priv_hex)


def restore_wallet_by_mnemonic():
    print(f"\n{CYAN}📦 ВОССТАНОВЛЕНИЕ{RESET}")
    mnemonic = input("Введите 12 слов через пробел: ").strip()
    if len(mnemonic.split()) < 12: print("❌ Нужно 12 слов!"); return None
    priv_hex, address = KeyGenerator.get_keys(mnemonic)
    print(f"\n🔑 Кошелёк восстановлен!\n📍 Адрес: {address}")
    return save_wallet_file(address, priv_hex)


def load_wallet():
    if not os.path.exists(WALLET_FILE): print("❌ Файл кошелька не найден!"); return None
    try:
        with open(WALLET_FILE, "r", encoding="utf-8") as f:
            wallet_file = json.load(f)
        print(f"\n🔑 Загрузка: {wallet_file.get('address', 'Unknown')[:30]}...")
        password = input("🔒 Пароль: ").strip()
        decrypted = CryptoWallet.decrypt_data(wallet_file["crypto_data"], password)
        if decrypted is None: print("❌ Неверный пароль!"); return None
        wallet_data = json.loads(decrypted)
        print(f"✅ Кошелёк загружен!");
        return wallet_data
    except Exception as e:
        print(f"❌ Ошибка: {e}"); return None


# ==================== ТРАНЗАКЦИИ ====================
# Глобальный трекер использованных nonce (очищается при перезапуске)
used_nonces = {}


def send_transaction(sender_address, private_key_hex, recipient, amount_ram, wallet_data=None):
    is_valid, err_msg = validate_address(recipient)
    if not is_valid: print(f"❌ {err_msg}"); return False
    if sender_address == recipient: print("❌ Нельзя отправить самому себе!"); return False
    if amount_ram <= 0: print("❌ Сумма должна быть больше нуля!"); return False

    amount = int(round(amount_ram * COIN))
    fee = FIXED_NETWORK_FEE

    live_balance, network_nonce = get_balance(sender_address)

    if live_balance is not None:
        is_online = True
    else:
        live_balance = int(wallet_data.get("last_balance", 0)) if wallet_data else 0
        network_nonce = int(wallet_data.get("last_nonce", 0)) if wallet_data else 0
        is_online = False
        print("⚠️ Нода недоступна. Работаем офлайн.")

    # Исправлено: безопасный выбор nonce
    local_nonce = network_nonce
    if sender_address in used_nonces:
        local_nonce = max(local_nonce, used_nonces[sender_address] + 1)

    pending_weight = get_pending_weight(sender_address) if is_online else 0
    available = live_balance - pending_weight

    if available < (amount + fee):
        print(f"❌ Недостаточно средств!")
        print(f"   Доступно: {available / COIN:.8f} RAM")
        print(f"   Требуется: {(amount + fee) / COIN:.8f} RAM")
        return False

    tx_data = {"sender": sender_address, "recipient": recipient, "amount": amount,
               "fee": fee, "nonce": local_nonce, "timestamp": int(time.time())}

    try:
        priv_int = int(private_key_hex, 16)
        priv_key = ec.derive_private_key(priv_int, ec.SECP256K1())
        # Исправлено: типы данных int для совместимости
        signing_data = {"sender": tx_data["sender"], "recipient": tx_data["recipient"],
                        "amount": int(tx_data["amount"]), "fee": int(tx_data["fee"]),
                        "nonce": int(tx_data["nonce"]), "timestamp": int(tx_data["timestamp"])}
        tx_data["signature"] = priv_key.sign(json.dumps(signing_data, sort_keys=True).encode(),
                                             ec.ECDSA(hashes.SHA256())).hex()
    except Exception as e:
        print(f"❌ Ошибка подписи: {e}"); return False

    if is_online:
        resp = api_post("/tx", tx_data)
        if resp and resp.get("status") == "ok":
            print(f"\n✅ Транзакция отправлена!")
            print(f"   📤 {amount_ram} RAM → {recipient[:30]}...")
            used_nonces[sender_address] = local_nonce  # Запоминаем использованный nonce
            return True
        else:
            print(f"❌ Нода отклонила: {resp.get('reason', '?') if resp else 'no response'}")
            return False

    print("📴 Сохраняем офлайн...")
    push_offline_transaction(tx_data)
    used_nonces[sender_address] = local_nonce
    print(f"✅ TX сохранена (nonce: {local_nonce})")
    return True


def check_balance(address):
    print(f"\n💰 Проверка баланса...")
    balance, nonce = get_balance(address)
    if balance is not None:
        print(f"📍 Адрес: {address[:30]}...")
        print(f"💰 Баланс: {balance / COIN:.8f} RAM")
        print(f"🔢 Nonce: {nonce}")
        pending = get_pending_transactions()
        my_pending = [tx for tx in pending if tx.get("sender") == address]
        if my_pending:
            pending_sum = sum(int(tx.get("amount", 0)) + FIXED_NETWORK_FEE for tx in my_pending)
            print(f"⏳ В мемпуле: {pending_sum / COIN:.8f} RAM ({len(my_pending)} TX)")
            print(f"💎 Доступно: {(balance - pending_sum) / COIN:.8f} RAM")
    else:
        print("⚠️ Нода недоступна.")


# ==================== ИНТЕРФЕЙС ====================
def wallet_menu(wallet_data):
    while True:
        print("\n" + "=" * 55)
        print(f"{CYAN}💼 КОШЕЛЁК RAMCOIN v{VERSION}{RESET}")
        print("=" * 55)
        print(f"📍 {wallet_data['address'][:40]}...")
        print(f"⛽ Комиссия: {FIXED_NETWORK_FEE / COIN} RAM")
        print("-" * 55)
        print("1. 💰 Проверить баланс")
        print("2. 📤 Отправить RAM")
        print("3. 📜 История транзакций")
        print("4. 📒 Адресная книга")
        print("5. 🔄 Синхронизировать офлайн-TX")
        print("6. 📋 Информация")
        print("7. 🔒 Сменить пароль")
        print("8. 🚪 Выйти")
        print("-" * 55)
        choice = input("👉 ").strip()

        if choice == "1":
            check_balance(wallet_data["address"])

        elif choice == "2":
            print(f"\n📤 ОТПРАВКА RAM")
            book = AddressBook.load()
            if book:
                print("\n📒 Адресная книга:")
                items = list(book.items())
                for i, (name, addr) in enumerate(items, 1): print(f"  {i}. {name}: {addr[:30]}...")
                print(f"  0. Ввести вручную")
                try:
                    idx = int(input("\n👉 Получатель: ").strip())
                    recipient = items[idx - 1][1] if 1 <= idx <= len(items) else input("📍 Адрес (RAM_...): ").strip()
                except:
                    recipient = input("📍 Адрес (RAM_...): ").strip()
            else:
                recipient = input("📍 Адрес (RAM_...): ").strip()
            try:
                amount = float(input("💎 Сумма RAM: ").strip())
            except ValueError:
                print("❌ Введите число!"); continue

            # Безопасность: запрашиваем пароль для каждой отправки
            with open(WALLET_FILE, "r", encoding="utf-8") as f:
                wf = json.load(f)
            password = input("🔒 Пароль для подтверждения: ").strip()
            if CryptoWallet.decrypt_data(wf["crypto_data"], password) is None:
                print("❌ Неверный пароль!");
                continue

            send_transaction(wallet_data["address"], wallet_data["private_key_hex"], recipient, amount, wallet_data)

        elif choice == "3":
            print("\n📜 ИСТОРИЯ ТРАНЗАКЦИЙ")
            history = get_transaction_history(wallet_data["address"])
            if history:
                for tx in history[:20]:
                    direction = "📥" if tx.get("recipient") == wallet_data["address"] else "📤"
                    amount = int(tx.get("amount", 0)) / COIN
                    print(f"  {direction} Блок #{tx.get('block_index', '?')} | {amount:.4f} RAM")
            else:
                print("  Нет транзакций")

        elif choice == "4":
            print("\n📒 АДРЕСНАЯ КНИГА\n1. Показать | 2. Добавить | 3. Удалить | 4. Назад")
            sub = input("👉 ").strip()
            if sub == "1":
                AddressBook.list_all()
            elif sub == "2":
                name = input("  Имя: ").strip();
                addr = input("  Адрес (RAM_...): ").strip()
                ok, err = validate_address(addr)
                if ok:
                    AddressBook.add(name, addr)
                else:
                    print(f"❌ {err}")
            elif sub == "3":
                AddressBook.remove(input("  Имя: ").strip())

        elif choice == "5":
            sync_offline_transactions()

        elif choice == "6":
            print(f"\n📋 ИНФОРМАЦИЯ")
            print(f"Версия: {wallet_data.get('version', '?')}")
            print(f"Адрес: {wallet_data['address']}")
            print(f"Создан: {time.ctime(wallet_data.get('created_at', 0))}")
            print(f"Шифрование: AES-256-GCM + PBKDF2-SHA512")

        elif choice == "7":
            print("\n🔒 СМЕНА ПАРОЛЯ")
            old_pw = input("Старый пароль: ").strip()
            with open(WALLET_FILE, "r") as f:
                wf = json.load(f)
            decrypted = CryptoWallet.decrypt_data(wf["crypto_data"], old_pw)
            if decrypted is None: print("❌ Неверный пароль!"); continue
            new_pw = input("Новый пароль (мин. 8): ").strip()
            if len(new_pw) < 8: print("❌ Короткий!"); continue
            wf["crypto_data"] = CryptoWallet.encrypt_data(decrypted, new_pw)
            with open(WALLET_FILE, "w") as f:
                json.dump(wf, f, indent=4)
            print("✅ Пароль изменён!")

        elif choice == "8":
            print(f"\n👋 До свидания!")
            # Очищаем конфиденциальные данные
            wallet_data["private_key_hex"] = "0" * 64
            del wallet_data
            import gc
            gc.collect()
            break

        else:
            print("❌ Неверный выбор!")


def main():
    print(f"\n{CYAN}🚀 RAMCOIN WALLET v{VERSION}{RESET}")
    print(f"⛽ Комиссия: {FIXED_NETWORK_FEE / COIN} RAM")
    if os.path.exists(WALLET_FILE):
        print("1. 📂 Загрузить кошелёк\n2. 🆕 Создать новый\n3. 🔄 Восстановить по фразе\n4. 🚪 Выйти")
        choice = input("\n👉 ").strip()
        if choice == "1":
            wallet = load_wallet()
            if wallet: wallet_menu(wallet)
        elif choice == "2":
            wallet = create_new_wallet()
            if wallet: wallet_menu(wallet)
        elif choice == "3":
            wallet = restore_wallet_by_mnemonic()
            if wallet: wallet_menu(wallet)
    else:
        print("🆕 Создание нового кошелька...")
        wallet = create_new_wallet()
        if wallet: wallet_menu(wallet)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n👋 До свидания!"); sys.exit(0)