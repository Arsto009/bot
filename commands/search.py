import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters

from services.storage import load_data
from commands.menu_extra import edit_sessions
from commands.devpanel import sessions as dev_sessions
from commands.admin import text_add_sessions


search_result_messages = {}


# =========================
# NORMALIZATION
# =========================

def normalize_digits(text: str) -> str:
    if not text:
        return ""

    eastern = "٠١٢٣٤٥٦٧٨٩"
    western = "0123456789"
    return text.translate(str.maketrans(eastern, western))


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = normalize_digits(text).lower().strip()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "گ": "ك",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    text = text.replace("،", ",")
    text = text.replace("٫", ".")
    text = text.replace("×", "x")
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"[^\w\s,\.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# =========================
# WORD MAPS
# =========================

UNIT_WORDS = {
    "صفر": 0,
    "واحد": 1,
    "واحده": 1,
    "وحده": 1,
    "اثنين": 2,
    "اثنان": 2,
    "اثنيين": 2,
    "اثنينن": 2,
    "ثنين": 2,
    "اثناني": 2,
    "ثلاث": 3,
    "ثلاثه": 3,
    "ثلاثة": 3,
    "ثلات": 3,
    "ثلاته": 3,
    "ثلاتة": 3,
    "تلاث": 3,
    "تلاثه": 3,
    "تلاثة": 3,
    "تلث": 3,
    "اربع": 4,
    "اربعه": 4,
    "اربعة": 4,
    "اربعه": 4,
    "اربعهه": 4,
    "خمس": 5,
    "خمسه": 5,
    "خمسة": 5,
    "ست": 6,
    "سته": 6,
    "ستة": 6,
    "سبع": 7,
    "سبعه": 7,
    "سبعة": 7,
    "ثمان": 8,
    "ثمانيه": 8,
    "ثمانية": 8,
    "تسع": 9,
    "تسعه": 9,
    "تسعة": 9,
    "عشر": 10,
    "عشرة": 10,
}

THOUSAND_WORDS = {
    "ميت": 100,
    "ميه": 100,
    "مئه": 100,
    "مئة": 100,
    "ميتين": 200,
    "مئتين": 200,
    "ماتين": 200,
    "ثلاثميه": 300,
    "ثلاثمية": 300,
    "ثلاثمئه": 300,
    "ثلاثمئة": 300,
    "اربعميه": 400,
    "اربعمية": 400,
    "اربعمية": 400,
    "اربعمئه": 400,
    "خمسميه": 500,
    "خمسمية": 500,
    "خمسميت": 500,
    "خمسمئه": 500,
    "ستميه": 600,
    "ستمية": 600,
    "ستمئه": 600,
    "سبعميه": 700,
    "سبعمية": 700,
    "سبعمئه": 700,
    "ثمانميه": 800,
    "ثمانمية": 800,
    "ثمانمئه": 800,
    "تسعميه": 900,
    "تسعمية": 900,
    "تسعمئه": 900,
}

TENS_WORDS = {
    "عشرين": 20,
    "ثلاثين": 30,
    "اربعين": 40,
    "أربعين": 40,
    "خمسين": 50,
    "خمسون": 50,
    "ستين": 60,
    "سبعين": 70,
    "ثمانين": 80,
    "تسعين": 90,
}

MILLION_TOKENS = {
    "مليون", "ملايين", "ملاين", "ملاييت", "مليونات", "مليونه", "مليونة"
}
BILLION_TOKENS = {
    "مليار", "مليارات"
}
THOUSAND_TOKENS = {"الف", "الاف", "آلاف"}
HALF_TOKENS = {"نص", "نصف"}
QUARTER_TOKENS = {"ربع", "ربعه"}
ROOM_TOKENS = {"غرفه", "غرفة", "غرف", "غرفات"}
BEDROOM_TOKENS = {"نوم", "منام"}
AREA_PREFIX_TOKENS = {"مساحه", "مساحة", "بمساحه", "بمساحة"}
AREA_SUFFIX_TOKENS = {"م", "م2", "متر", "مربع", "مترمربع", "مترمربعه", "مترمربعة"}

SYNONYM_GROUPS = [
    {"بيت", "البيت", "بيوت", "دار", "الدار", "دور"},
]


def expand_word_variants(word: str):
    w = normalize_text(word)
    variants = {w}
    for group in SYNONYM_GROUPS:
        if w in group:
            variants.update(group)
    return {v for v in variants if v}


# =========================
# WORD -> NUMBER HELPERS
# =========================

def word_to_number(word: str):
    return UNIT_WORDS.get(normalize_text(word))


def word_to_thousand(word: str):
    return THOUSAND_WORDS.get(normalize_text(word))


def parse_numeric_token(word: str):
    w = normalize_text(word).replace(",", "")
    if not w:
        return None
    try:
        if "." in w:
            return float(w)
        return int(w)
    except Exception:
        return None


def tokens_from_text(text: str):
    return [tok for tok in normalize_text(text).split() if tok]


# =========================
# FLOOR HELPERS
# =========================

def normalize_floor_text(text: str) -> str:
    if not text:
        return ""

    t = normalize_text(text)
    t = t.replace("الارضي", "ارضي")
    t = t.replace("الأرضي", "ارضي")
    t = t.replace("الاول", "اول")
    t = t.replace("الأول", "اول")
    t = t.replace("الثاني", "ثاني")
    t = t.replace("الثالث", "ثالث")
    t = t.replace("اولى", "اول")
    t = t.replace("اولي", "اول")
    t = t.replace("الثانيه", "ثاني")
    t = t.replace("الثانية", "ثاني")
    t = t.replace("الثالثه", "ثالث")
    t = t.replace("الثالثة", "ثالث")
    t = t.replace("ادوار", "طوابق")
    t = t.replace("دورين", "طابقين")
    t = t.replace("دوران", "طابقين")
    t = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", t)
    t = re.sub(r"(?<=[^\W\d_])(?=\d)", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def floor_word_to_number(word: str):
    w = normalize_floor_text(word)

    mapping = {
        "واحد": 1,
        "واحده": 1,
        "وحده": 1,
        "اول": 1,

        "اثنين": 2,
        "اثنان": 2,
        "ثنين": 2,
        "طابقين": 2,

        "ثلاث": 3,
        "ثلاثه": 3,
        "ثلاثة": 3,
        "ثلات": 3,
        "ثلاته": 3,
        "ثلاتة": 3,
        "تلاث": 3,
        "تلاثه": 3,
        "تلاثة": 3,
        "تلث": 3,
        "تلت": 3,
        "ثالث": 3,

        "اربع": 4,
        "اربعه": 4,
        "اربعة": 4,

        "خمس": 5,
        "خمسه": 5,
        "خمسة": 5,
    }

    return mapping.get(w)


def detect_floor_query(query: str):
    q = normalize_floor_text(query)

    if not q:
        return None

    if q == "طابق":
        return {"type": "ignore_generic_floor"}

    if re.search(r"\b(?:طابق\s+)?ارضي\b", q):
        return {"type": "specific_floor", "value": "ground"}

    if re.search(r"\b(?:طابق\s+)?اول\b", q):
        return {"type": "specific_floor", "value": "first"}

    if re.search(r"\b(?:طابق\s+)?ثاني\b", q):
        return {"type": "specific_floor", "value": "second"}

    if re.search(r"\b(?:طابق\s+)?ثالث\b", q):
        return {"type": "specific_floor", "value": "third"}

    if re.search(r"\bطابقين\b", q):
        return {"type": "floor_count", "value": 2}

    m = re.search(r"\b(\d+)\s*طوابق\b", q)
    if m:
        try:
            return {"type": "floor_count", "value": int(m.group(1))}
        except Exception:
            pass

    m = re.search(r"\b(\d+)\s*طابق\b", q)
    if m:
        try:
            return {"type": "floor_count", "value": int(m.group(1))}
        except Exception:
            pass

    m = re.search(r"\bطابق\s*(\d+)\b", q)
    if m:
        try:
            return {"type": "floor_count", "value": int(m.group(1))}
        except Exception:
            pass

    m = re.search(r"\b([\w]+)\s*طوابق\b", q)
    if m:
        n = floor_word_to_number(m.group(1))
        if n is not None:
            return {"type": "floor_count", "value": n}

    m = re.search(r"\b([\w]+)\s*طابق\b", q)
    if m:
        n = floor_word_to_number(m.group(1))
        if n is not None:
            return {"type": "floor_count", "value": n}

    m = re.search(r"\bطابق\s+([\w]+)\b", q)
    if m:
        token = m.group(1)
        if token == "ارضي":
            return {"type": "specific_floor", "value": "ground"}
        if token == "اول":
            return {"type": "specific_floor", "value": "first"}
        if token == "ثاني":
            return {"type": "specific_floor", "value": "second"}
        if token == "ثالث":
            return {"type": "specific_floor", "value": "third"}

        n = floor_word_to_number(token)
        if n is not None:
            return {"type": "floor_count", "value": n}

    return None


def extract_floor_signals_from_text(text: str):
    t = normalize_floor_text(text)
    signals = {
        "ground": False,
        "first": False,
        "second": False,
        "third": False,
        "counts": set(),
    }

    if re.search(r"\b(?:طابق|الدور|الطابق)?\s*ارضي\b", t):
        signals["ground"] = True

    if re.search(r"\b(?:طابق|الدور|الطابق)\s*اول\b", t):
        signals["first"] = True

    if re.search(r"\b(?:طابق|الدور|الطابق)\s*ثاني\b", t):
        signals["second"] = True

    if re.search(r"\b(?:طابق|الدور|الطابق)\s*ثالث\b", t):
        signals["third"] = True

    if re.search(r"\bطابقين\b", t):
        signals["counts"].add(2)

    for m in re.finditer(r"\b(\d+)\s*طوابق\b", t):
        try:
            signals["counts"].add(int(m.group(1)))
        except Exception:
            pass

    for m in re.finditer(r"\b(\d+)\s*طابق\b", t):
        try:
            signals["counts"].add(int(m.group(1)))
        except Exception:
            pass

    for m in re.finditer(r"\b([\w]+)\s*طوابق\b", t):
        n = floor_word_to_number(m.group(1))
        if n is not None:
            signals["counts"].add(n)

    for m in re.finditer(r"\b([\w]+)\s*طابق\b", t):
        n = floor_word_to_number(m.group(1))
        if n is not None:
            signals["counts"].add(n)

    return signals


def floor_match(query: str, ad_text: str) -> bool:
    wanted = detect_floor_query(query)
    if wanted is None:
        return True

    if wanted.get("type") == "ignore_generic_floor":
        return True

    signals = extract_floor_signals_from_text(ad_text)

    if wanted["type"] == "specific_floor":
        if wanted["value"] == "ground":
            return signals["ground"]
        if wanted["value"] == "first":
            return signals["first"]
        if wanted["value"] == "second":
            return signals["second"]
        if wanted["value"] == "third":
            return signals["third"]
        return False

    if wanted["type"] == "floor_count":
        return wanted["value"] in signals["counts"]

    return True


# =========================
# TOKEN FILTER FOR TEXT SEARCH
# =========================

def split_query_words(query: str):
    parts = tokens_from_text(query)

    ignored = set()
    ignored.update(MILLION_TOKENS)
    ignored.update(BILLION_TOKENS)
    ignored.update(THOUSAND_TOKENS)
    ignored.update(HALF_TOKENS)
    ignored.update(QUARTER_TOKENS)
    ignored.update({"و"})
    ignored.update(UNIT_WORDS.keys())
    ignored.update(THOUSAND_WORDS.keys())
    ignored.update(TENS_WORDS.keys())
    ignored.update(AREA_PREFIX_TOKENS)
    ignored.update(AREA_SUFFIX_TOKENS)
    ignored.update(ROOM_TOKENS)
    ignored.update(BEDROOM_TOKENS)

    floor_intent = detect_floor_query(query)
    if floor_intent is not None:
        ignored.update({
            "طابق", "طوابق", "ارضي", "اول", "ثاني", "ثالث",
            "واحد", "واحده", "وحده",
            "اثنين", "اثنان", "ثنين", "طابقين",
            "ثلاث", "ثلاثه", "ثلاثة", "ثلات", "ثلاته", "ثلاتة",
            "تلاث", "تلاثه", "تلاثة", "تلث", "تلت",
            "3",
        })

    words = []
    for p in parts:
        if parse_numeric_token(p) is not None:
            continue
        if p in ignored:
            continue
        words.append(p)

    return words


# =========================
# PRICE PARSERS
# =========================

def parse_spelled_million_values(text: str):
    t = normalize_text(text)
    values = set()

    if re.search(r"\b(?:مليونين|مليوني)\b", t):
        values.add(2_000_000)

    tokens = tokens_from_text(t)
    for i, token in enumerate(tokens):
        if token == "مليون":
            prev = tokens[i - 1] if i > 0 else ""
            if prev not in HALF_TOKENS and prev not in QUARTER_TOKENS and parse_numeric_token(prev) is None and word_to_number(prev) is None:
                values.add(1_000_000)

    for m in re.finditer(r"\b([\w\.\,]+)\s+(?:مليون|ملايين|ملاين|ملاييت)\b", t):
        first = m.group(1)
        num = parse_numeric_token(first)
        if isinstance(num, (int, float)):
            values.add(int(float(num) * 1_000_000))
            continue
        n = word_to_number(first)
        if n is not None:
            values.add(n * 1_000_000)

    return values


def parse_spelled_billion_values(text: str):
    t = normalize_text(text)
    values = set()

    if re.search(r"\b(?:مليارين|ملياري)\b", t):
        values.add(2_000_000_000)

    tokens = tokens_from_text(t)
    for i, token in enumerate(tokens):
        if token == "مليار":
            prev = tokens[i - 1] if i > 0 else ""
            if prev not in HALF_TOKENS and prev not in QUARTER_TOKENS and parse_numeric_token(prev) is None and word_to_number(prev) is None:
                values.add(1_000_000_000)

    for m in re.finditer(r"\b([\w\.\,]+)\s+(?:مليار|مليارات)\b", t):
        first = m.group(1)
        num = parse_numeric_token(first)
        if isinstance(num, (int, float)):
            values.add(int(float(num) * 1_000_000_000))
            continue
        n = word_to_number(first)
        if n is not None:
            values.add(n * 1_000_000_000)

    return values


def parse_compound_price_tokens(tokens):
    prices = set()

    for i, tok in enumerate(tokens):
        # مليار / مليون / الف مفردة مسبوقة بكلمة عدد
        if tok in MILLION_TOKENS:
            prev = tokens[i - 1] if i > 0 else ""
            prev_num = parse_numeric_token(prev)
            if isinstance(prev_num, (int, float)):
                prices.add(int(float(prev_num) * 1_000_000))
            else:
                n = word_to_number(prev)
                if n is not None:
                    prices.add(n * 1_000_000)
                elif not prev:
                    prices.add(1_000_000)

        if tok in BILLION_TOKENS:
            prev = tokens[i - 1] if i > 0 else ""
            prev_num = parse_numeric_token(prev)
            if isinstance(prev_num, (int, float)):
                prices.add(int(float(prev_num) * 1_000_000_000))
            else:
                n = word_to_number(prev)
                if n is not None:
                    prices.add(n * 1_000_000_000)
                elif not prev:
                    prices.add(1_000_000_000)

        # مليون ونص / ثلاث ملايين ونص / 3 مليون ونص
        if tok in MILLION_TOKENS and i + 1 < len(tokens):
            if tokens[i + 1] in HALF_TOKENS:
                prices.add(1_500_000)
            if tokens[i + 1] in QUARTER_TOKENS:
                prices.add(1_250_000)
            if i + 2 < len(tokens) and tokens[i + 1] == "و" and tokens[i + 2] in HALF_TOKENS:
                base = 1
                prev = tokens[i - 1] if i > 0 else ""
                prev_num = parse_numeric_token(prev)
                if isinstance(prev_num, (int, float)):
                    base = float(prev_num)
                else:
                    n = word_to_number(prev)
                    if n is not None:
                        base = n
                prices.add(int((base + 0.5) * 1_000_000))
            if i + 2 < len(tokens) and tokens[i + 1] == "و" and tokens[i + 2] in QUARTER_TOKENS:
                base = 1
                prev = tokens[i - 1] if i > 0 else ""
                prev_num = parse_numeric_token(prev)
                if isinstance(prev_num, (int, float)):
                    base = float(prev_num)
                else:
                    n = word_to_number(prev)
                    if n is not None:
                        base = n
                prices.add(int((base + 0.25) * 1_000_000))

            # مليون و 500 الف / 3 مليون و 500 الف / ثلاث ملايين و 500 الف
            if i + 3 < len(tokens) and tokens[i + 1] == "و":
                extra_num = parse_numeric_token(tokens[i + 2])
                if extra_num is None:
                    extra_num = word_to_thousand(tokens[i + 2])
                if extra_num is not None and tokens[i + 3] in THOUSAND_TOKENS:
                    base = 1
                    prev = tokens[i - 1] if i > 0 else ""
                    prev_num = parse_numeric_token(prev)
                    if isinstance(prev_num, (int, float)):
                        base = float(prev_num)
                    else:
                        n = word_to_number(prev)
                        if n is not None:
                            base = n
                    prices.add(int(base * 1_000_000 + int(extra_num) * 1000))

        # مليار ونص / مليار و 250 مليون / 2 مليار و 300 مليون
        if tok in BILLION_TOKENS and i + 1 < len(tokens):
            if tokens[i + 1] in HALF_TOKENS:
                prices.add(1_500_000_000)
            if tokens[i + 1] in QUARTER_TOKENS:
                prices.add(1_250_000_000)
            if i + 2 < len(tokens) and tokens[i + 1] == "و" and tokens[i + 2] in HALF_TOKENS:
                base = 1
                prev = tokens[i - 1] if i > 0 else ""
                prev_num = parse_numeric_token(prev)
                if isinstance(prev_num, (int, float)):
                    base = float(prev_num)
                else:
                    n = word_to_number(prev)
                    if n is not None:
                        base = n
                prices.add(int((base + 0.5) * 1_000_000_000))
            if i + 2 < len(tokens) and tokens[i + 1] == "و" and tokens[i + 2] in QUARTER_TOKENS:
                base = 1
                prev = tokens[i - 1] if i > 0 else ""
                prev_num = parse_numeric_token(prev)
                if isinstance(prev_num, (int, float)):
                    base = float(prev_num)
                else:
                    n = word_to_number(prev)
                    if n is not None:
                        base = n
                prices.add(int((base + 0.25) * 1_000_000_000))

            if i + 3 < len(tokens) and tokens[i + 1] == "و":
                extra_num = parse_numeric_token(tokens[i + 2])
                if extra_num is None:
                    extra_num = word_to_number(tokens[i + 2])
                if extra_num is not None and tokens[i + 3] in MILLION_TOKENS:
                    base = 1
                    prev = tokens[i - 1] if i > 0 else ""
                    prev_num = parse_numeric_token(prev)
                    if isinstance(prev_num, (int, float)):
                        base = float(prev_num)
                    else:
                        n = word_to_number(prev)
                        if n is not None:
                            base = n
                    prices.add(int(base * 1_000_000_000 + int(extra_num) * 1_000_000))

    # خمسميت الف / ميت الف / 500 الف / 90 الف
    for i in range(len(tokens) - 1):
        a = tokens[i]
        b = tokens[i + 1]
        if b in THOUSAND_TOKENS:
            a_num = parse_numeric_token(a)
            if a_num is None:
                a_num = word_to_thousand(a)
            if a_num is None:
                a_num = TENS_WORDS.get(a)
            if a_num is None:
                a_num = word_to_number(a)
            if a_num is not None:
                prices.add(int(a_num) * 1000)

    # خمسميت و خمسين الف / 500 و 50 الف
    for i in range(len(tokens) - 3):
        a, b, c, d = tokens[i], tokens[i + 1], tokens[i + 2], tokens[i + 3]
        if b == "و" and d in THOUSAND_TOKENS:
            first = parse_numeric_token(a)
            if first is None:
                first = word_to_thousand(a)
            second = parse_numeric_token(c)
            if second is None:
                second = TENS_WORDS.get(c)
            if second is None:
                second = word_to_number(c)
            if first is not None and second is not None:
                prices.add(int(first + second) * 1000)

    return prices


def extract_prices(text: str):
    t = normalize_text(text)
    prices = set()
    tokens = tokens_from_text(t)

    prices.update(parse_spelled_million_values(t))
    prices.update(parse_spelled_billion_values(t))
    prices.update(parse_compound_price_tokens(tokens))

    # مباشر: 3 مليون / 1.5 مليون / 2 مليار
    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(مليون|ملايين|ملاين|ملاييت)\b", t):
        prices.add(int(float(m.group(1)) * 1_000_000))

    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(مليار|مليارات)\b", t):
        prices.add(int(float(m.group(1)) * 1_000_000_000))

    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(الف|الاف|آلاف)\b", t):
        prices.add(int(float(m.group(1)) * 1000))

    # مليون و500 الف / مليار و250 مليون
    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:مليون|ملايين|ملاين|ملاييت)\s*و\s*(\d{1,3})\s*(?:الف|الاف|آلاف)\b", t):
        prices.add(int(float(m.group(1)) * 1_000_000 + int(m.group(2)) * 1000))

    for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:مليار|مليارات)\s*و\s*(\d{1,3})\s*(?:مليون|ملايين|ملاين|ملاييت)\b", t):
        prices.add(int(float(m.group(1)) * 1_000_000_000 + int(m.group(2)) * 1_000_000))

    # نصف مليون / ربع مليون
    if "نص مليون" in t or "نصف مليون" in t:
        prices.add(500_000)
    if "ربع مليون" in t or "ربعه مليون" in t:
        prices.add(250_000)
    if "نص مليار" in t or "نصف مليار" in t:
        prices.add(500_000_000)
    if "ربع مليار" in t or "ربعه مليار" in t:
        prices.add(250_000_000)

    # أرقام كاملة مباشرة مثل 3000000 أو 3,000,000
    for m in re.finditer(r"\b\d[\d,]{3,}\b", t):
        raw = m.group(0).replace(",", "")
        try:
            num = int(raw)
        except Exception:
            continue
        if num >= 1000:
            prices.add(num)

    return sorted(prices)


# =========================
# AREA PARSERS
# =========================

def extract_areas_from_text(text: str):
    t = normalize_text(text)
    areas = set()

    for m in re.finditer(
        r"\b(?:مساحه|مساحة|بمساحه|بمساحة)\s*(\d{1,5})(?:\s*(?:م|متر|مربع|متر\s*مربع|م2))?\b",
        t,
    ):
        try:
            num = int(m.group(1))
            if 10 <= num <= 10000:
                areas.add(num)
        except Exception:
            pass

    for m in re.finditer(r"\b(\d{1,5})\s*(?:م2|م|متر|مربع|متر\s*مربع)\b", t):
        try:
            num = int(m.group(1))
            if 10 <= num <= 10000:
                areas.add(num)
        except Exception:
            pass

    return sorted(areas)


def detect_area_query(query: str):
    q = normalize_text(query)
    m = re.search(
        r"\b(?:مساحه|مساحة|بمساحه|بمساحة)\s*(\d{1,5})(?:\s*(?:م|متر|مربع|متر\s*مربع|م2))?\b",
        q,
    )
    if not m:
        return None

    try:
        area = int(m.group(1))
    except Exception:
        return None

    if not (10 <= area <= 10000):
        return None

    return area


def area_match(query: str, ad_text: str) -> bool:
    wanted_area = detect_area_query(query)
    if wanted_area is None:
        return True

    areas = extract_areas_from_text(ad_text)
    if not areas:
        return False

    return wanted_area in areas


# =========================
# ROOM PARSERS
# =========================

def extract_rooms_from_text(text: str):
    t = normalize_text(text)
    rooms = set()

    if re.search(r"\bغرفتين\b|\bغرفتان\b", t):
        rooms.add(2)

    for m in re.finditer(r"\b(\d{1,2})\s*(?:غرفه|غرفة|غرف)(?:\s*(?:نوم|منام))?\b", t):
        try:
            n = int(m.group(1))
            if 1 <= n <= 20:
                rooms.add(n)
        except Exception:
            pass

    word_pattern = r"|".join(sorted(map(re.escape, UNIT_WORDS.keys()), key=len, reverse=True))
    for m in re.finditer(
        rf"\b({word_pattern})\s*(?:غرفه|غرفة|غرف)(?:\s*(?:نوم|منام))?\b",
        t,
    ):
        n = word_to_number(m.group(1))
        if n and 1 <= n <= 20:
            rooms.add(n)

    return sorted(rooms)


def detect_room_query(query: str):
    q = normalize_text(query)

    if re.search(r"\bغرفتين\b|\bغرفتان\b", q):
        return 2

    m = re.search(r"\b(\d{1,2})\s*(?:غرفه|غرفة|غرف)(?:\s*(?:نوم|منام))?\b", q)
    if m:
        try:
            n = int(m.group(1))
            if 1 <= n <= 20:
                return n
        except Exception:
            pass

    word_pattern = r"|".join(sorted(map(re.escape, UNIT_WORDS.keys()), key=len, reverse=True))
    m = re.search(
        rf"\b({word_pattern})\s*(?:غرفه|غرفة|غرف)(?:\s*(?:نوم|منام))?\b",
        q,
    )
    if m:
        n = word_to_number(m.group(1))
        if n and 1 <= n <= 20:
            return n

    return None


def room_match(query: str, ad_text: str) -> bool:
    wanted_rooms = detect_room_query(query)
    if wanted_rooms is None:
        return True

    rooms = extract_rooms_from_text(ad_text)
    if not rooms:
        return False

    return wanted_rooms in rooms


# =========================
# DETECT QUERY PRICE BUCKET
# =========================

def detect_exact_prices(query: str):
    prices = extract_prices(query)
    if not prices:
        return []

    # استبعد أرقام المساحة والغرف من نتائج الاستعلام
    area = detect_area_query(query)
    rooms = detect_room_query(query)
    filtered = []
    for p in prices:
        if area is not None and p == area:
            continue
        if rooms is not None and p == rooms:
            continue
        filtered.append(p)

    filtered = sorted(set(filtered))
    if len(filtered) > 1:
        return [max(filtered)]
    return filtered


def detect_price_bucket(query: str):
    q = normalize_text(query)

    exact_prices = detect_exact_prices(q)
    if exact_prices:
        return None

    nums = re.findall(r"\b\d[\d,]*\.?\d*\b", q)
    for raw in nums:
        raw_num = raw.replace(",", "")
        try:
            num = float(raw_num)
        except Exception:
            continue

        if num >= 1_000_000_000:
            base = int(num // 1_000_000_000) * 1_000_000_000
            return (base, base + 1_000_000_000)
        if num >= 1_000_000:
            base = int(num // 1_000_000) * 1_000_000
            return (base, base + 1_000_000)
        if 50 <= num <= 999 and detect_area_query(query) is None and detect_room_query(query) is None:
            base = int(num) * 1000
            return (base, base + 100_000)

    if re.search(r"\b(?:مليون|ملايين|ملاين|ملاييت)\b", q):
        exact = parse_spelled_million_values(q)
        if exact:
            val = max(exact)
            base = (val // 1_000_000) * 1_000_000
            return (base, base + 1_000_000)
        return (1_000_000, 2_000_000)

    if re.search(r"\b(?:مليار|مليارات)\b", q):
        exact = parse_spelled_billion_values(q)
        if exact:
            val = max(exact)
            base = (val // 1_000_000_000) * 1_000_000_000
            return (base, base + 1_000_000_000)
        return (1_000_000_000, 2_000_000_000)

    return None


# =========================
# MATCH LOGIC
# =========================

def text_match(query: str, ad_text: str) -> bool:
    words = split_query_words(query)
    if not words:
        return True

    ad = normalize_text(ad_text)
    for word in words:
        variants = expand_word_variants(word)
        if not any(variant in ad for variant in variants):
            return False
    return True


def price_match(query: str, ad_text: str) -> bool:
    exact_prices = detect_exact_prices(query)
    prices = extract_prices(ad_text)

    if exact_prices:
        if not prices:
            return False
        return any(p in prices for p in exact_prices)

    bucket = detect_price_bucket(query)
    if not bucket:
        return True

    if not prices:
        return False

    low, high = bucket
    return any(low <= p < high for p in prices)


# =========================
# CLEANUP OLD RESULTS
# =========================

async def clear_old_search_messages(bot, user_id):
    msgs = search_result_messages.get(user_id, [])
    if not msgs:
        return

    for chat_id, msg_id in msgs:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

    search_result_messages[user_id] = []


# =========================
# SEARCH HANDLER
# =========================

async def search(update, context):
    user_id = update.effective_user.id

    if user_id in edit_sessions:
        return

    if user_id in dev_sessions:
        return

    if user_id in text_add_sessions:
        return

    if (
        not update.message
        or not update.message.text
        or update.message.reply_to_message
    ):
        return

    query = update.message.text.strip()

    if len(query) < 2:
        return

    await clear_old_search_messages(context.bot, user_id)

    data = load_data()
    results = []

    def scan_node(node):
        for item in node.get("items", []):
            ad_text = item.get("text", "")

            if (
                text_match(query, ad_text)
                and price_match(query, ad_text)
                and area_match(query, ad_text)
                and room_match(query, ad_text)
                and floor_match(query, ad_text)
            ):
                results.append(item)

        for child in node.get("sub", {}).values():
            scan_node(child)

    for cat in data.get("categories", {}).values():
        scan_node(cat)

    if not results:
        return

    sent_messages = []
    seen_texts = set()

    for r in results:
        ad_text = r.get("text", "").strip()
        if not ad_text or ad_text in seen_texts:
            continue

        seen_texts.add(ad_text)

        msg = await update.message.reply_text(f"🏠 نتيجة:\n{ad_text}")
        sent_messages.append((msg.chat_id, msg.message_id))

        if len(sent_messages) >= 5:
            break

    if not sent_messages:
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("تمت الرؤية", callback_data="search_seen")]
    ])

    done_msg = await update.message.reply_text(
        "انتهت نتائج البحث.",
        reply_markup=keyboard,
    )
    sent_messages.append((done_msg.chat_id, done_msg.message_id))

    search_result_messages[user_id] = sent_messages


# =========================
# BUTTON HANDLER
# =========================

async def search_seen_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()

    msgs = search_result_messages.get(user_id, [])

    for chat_id, msg_id in msgs:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

    search_result_messages[user_id] = []


# =========================
# REGISTER
# =========================

def register(app):
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, search),
        group=5,
    )

    app.add_handler(
        CallbackQueryHandler(search_seen_callback, pattern="^search_seen$")
    )