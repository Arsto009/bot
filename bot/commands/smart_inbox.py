# commands/smart_inbox.py
# فرز ذكي: بعد ما تحفظ الإعلانات داخل smart_inbox، ننقلها تلقائياً حسب:
# (بيع/إيجار) + (سكني/تجاري/ارض) + (السعر)
# وإذا ما لقى لستة مطابقة، ينشئ لستة جديدة تلقائياً بنفس نمط اللستات الموجودة.

import re
from typing import Optional, Tuple, List

from services.storage import load_data, save_data
from commands.shared_ads import get_node

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_ARABIC_DIGITS_2 = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")  # Persian variants


_NUMBER_WORD_VARIANTS = {
    "صفر": 0,

    "واحد": 1,
    "واحده": 1,
    "وحده": 1,
    "واحدهه": 1,

    "اثنين": 2,
    "اثنان": 2,
    "اثنيين": 2,
    "اثنينن": 2,
    "اثنينه": 2,
    "اثنيه": 2,
    "اثني": 2,
    "اثنا": 2,
    "ثنين": 2,
    "ثننين": 2,

    "ثلاث": 3,
    "ثلاثه": 3,
    "ثلاثة": 3,
    "ثلالث": 3,
    "ثلالثة": 3,
    "ثلالثه": 3,
    "ثلالته": 3,
    "ثلالتهه": 3,
    "ثلات": 3,
    "ثلاته": 3,
    "ثلاتة": 3,
    "تلاث": 3,
    "تلاثه": 3,
    "تلاثة": 3,
    "تلث": 3,
    "تلت": 3,
    "تلته": 3,
    "تلاته": 3,

    "اربع": 4,
    "اربعه": 4,
    "اربعة": 4,
    "اربعهه": 4,
    "ارع": 4,

    "خمس": 5,
    "خمسه": 5,
    "خمسة": 5,
    "خمست": 5,

    "ست": 6,
    "سته": 6,
    "ستة": 6,

    "سبع": 7,
    "سبعه": 7,
    "سبعة": 7,

    "ثمن": 8,
    "ثمان": 8,
    "ثمانيه": 8,
    "ثمانية": 8,
    "ثمنيه": 8,

    "تسع": 9,
    "تسعه": 9,
    "تسعة": 9,

    "عشر": 10,
    "عشرة": 10,
    "عشره": 10,

    "احد عشر": 11,
    "حدعشر": 11,
    "احدى عشر": 11,
    "احدعشر": 11,
    "احدىعشر": 11,

    "اثنا عشر": 12,
    "اثني عشر": 12,
    "اثنعش": 12,
    "اثنعشر": 12,
    "ثنعش": 12,
    "ثنعشر": 12,
    "اثناعش": 12,
    "اثنيعش": 12,
    "اثناعشر": 12,

    "ثلاث عشر": 13,
    "ثلاثة عشر": 13,
    "ثلاثعشر": 13,
    "ثلاثةعشر": 13,
    "ثلاثطعش": 13,
    "ثلتعش": 13,
    "تلتعش": 13,
    "ثلثطعش": 13,
    "ثلطعش": 13,
    "تلطعش": 13,
    "ثلث عشر": 13,
    "ثلاثطعشر": 13,

    "ارطعش": 14,
    "اربع عشر": 14,
    "اربعة عشر": 14,
    "اربعه عشر": 14,
    "اربعطعش": 14,
    "اربعتعش": 14,

    "خمس عشر": 15,
    "خمسة عشر": 15,
    "خمسطعش": 15,
    "خمستعش": 15,

    "ست عشر": 16,
    "ستة عشر": 16,
    "ستطعش": 16,

    "سبع عشر": 17,
    "سبعة عشر": 17,
    "سبعتعش": 17,

    "ثمان عشر": 18,
    "ثمانية عشر": 18,
    "ثمنتعش": 18,
    "ثمنطعش": 18,

    "تسع عشر": 19,
    "تسعة عشر": 19,
    "تسعتعش": 19,

    "عشرين": 20,
    "عشرون": 20,

    "ثلاثين": 30,
    "ثلاثون": 30,

    "اربعين": 40,
    "اربعون": 40,

    "خمسين": 50,
    "خمسون": 50,

    "ستين": 60,
    "ستون": 60,

    "سبعين": 70,
    "سبعون": 70,

    "ثمانين": 80,
    "ثمانون": 80,

    "تسعين": 90,
    "تسعون": 90,

    "ميه": 100,
    "مية": 100,
    "مئه": 100,
    "مئة": 100,
    "مائه": 100,
    "مائة": 100,

    "ميتين": 200,
    "مئتين": 200,
    "ماتين": 200,
    "ماءتين": 200,
    "مائتين": 200,
    "ماءتان": 200,
    "مائتان": 200,

    "ثلاثميه": 300,
    "ثلاثمية": 300,
    "ثلاثماءه": 300,
    "ثلاثماءة": 300,
    "تلثمية": 300,
    "ثلاثمئه": 300,
    "ثلاثمئة": 300,
    "ثلاثميت": 300,
    "ثلثميه": 300,
    "تلت ميه": 300,
    "تلث ميه": 300,
    "تلت مية": 300,
    "تلث مية": 300,

    "اربعميه": 400,
    "اربعمئه": 400,
    "اربعمئة": 400,

    "خمسميه": 500,
    "خمسمية": 500,
    "خمسميت": 500,
    "خمسمئه": 500,
    "خمسمئة": 500,

    "ستمية": 600,
    "ستميه": 600,
    "ستمئه": 600,
    "ستمئة": 600,

    "سبعمية": 700,
    "سبعميه": 700,
    "سبعمئه": 700,
    "سبعمئة": 700,

    "ثمانمية": 800,
    "ثمانميه": 800,
    "ثمانمئه": 800,
    "ثمانمئة": 800,

    "تسعمية": 900,
    "تسعميه": 900,
    "تسعمئه": 900,
    "تسعمئة": 900,

    "الف": 1000,
    "الفين": 2000,
    "الفان": 2000,
    "الفي": 2000,
}

_NUMBER_CONNECTORS = {"و", "ويا", "وي", "with"}

_FRACTION_WORDS = {
    "نص": 0.5,
    "نصف": 0.5,
    "ربع": 0.25,
    "ثلث": (1 / 3),
    "ثلثين": (2 / 3),
    "ثلاثه ارباع": 0.75,
}

_UNIT_MULTIPLIERS = {
    "الف": 1_000,
    "مليون": 1_000_000,
    "مليار": 1_000_000_000,
}


def _norm(text: str) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    t = t.translate(_ARABIC_DIGITS).translate(_ARABIC_DIGITS_2)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("٫", ".").replace("،", ",")
    return t


def _normalize_number_words(text: str) -> str:
    if not text:
        return ""

    t = _norm(text)
    t = t.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي").replace("گ", "ك")

    replacements = {
        "ونص": "و نص",
        "ونصف": "و نصف",
        "وربع": "و ربع",
        "وثلث": "و ثلث",
        "وثلثين": "و ثلثين",

        "ملايين": "مليون",
        "ملاين": "مليون",
        "مليارات": "مليار",
        "الاف": "الف",
        "ألف": "الف",

        "خمست الاف": "خمسه الف",
        "خمس الاف": "خمسه الف",
        "خمسة الاف": "خمسه الف",
        "خمست الف": "خمسه الف",
        "خمس الف": "خمسه الف",
        "خمسة الف": "خمسه الف",

        "تلث الاف": "ثلاثه الف",
        "تلت الاف": "ثلاثه الف",
        "ثلث الاف": "ثلاثه الف",
        "ثلالثة الاف": "ثلاثه الف",
        "ثلالثه الاف": "ثلاثه الف",
        "ثلاثة الاف": "ثلاثه الف",

        "عشرت الاف": "عشره الف",
        "عشرة الاف": "عشره الف",
        "عشر الاف": "عشره الف",

        "خمست مليون": "خمسه مليون",
        "خمس مليون": "خمسه مليون",
        "خمسة مليون": "خمسه مليون",

        "تلث مليون": "ثلاثه مليون",
        "تلت مليون": "ثلاثه مليون",
        "ثلالثة مليون": "ثلاثه مليون",
        "ثلالثه مليون": "ثلاثه مليون",
        "ثلاثة مليون": "ثلاثه مليون",
    }

    for src, dst in replacements.items():
        t = t.replace(src, dst)

    t = re.sub(r"\b(\d)\s*الاف\b", r"\1 الف", t)
    t = re.sub(r"\b(\d)\s*ملايين\b", r"\1 مليون", t)
    t = re.sub(r"\b(\d)\s*ملاين\b", r"\1 مليون", t)

    # فصل الرقم عن الوحدة إذا كانت ملتصقة مثل: 850الف / 2مليون
    t = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", t)
    t = re.sub(r"(?<=[^\W\d_])(?=\d)", " ", t)

    # الحفاظ على الأرقام العشرية
    t = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", t)

    # توحيد المثنى
    t = re.sub(r"\bمليونين\b", "2 مليون", t)
    t = re.sub(r"\bمليونان\b", "2 مليون", t)
    t = re.sub(r"\bمليارين\b", "2 مليار", t)
    t = re.sub(r"\bملياران\b", "2 مليار", t)
    t = re.sub(r"\bالفين\b", "2 الف", t)
    t = re.sub(r"\bالفان\b", "2 الف", t)

    t = re.sub(r"\s+", " ", t).strip()
    return t


def _split_prefixed_waw_tokens(tokens: List[str]) -> List[str]:
    out = []
    for tok in tokens:
        if tok.startswith("و") and len(tok) > 1:
            rest = tok[1:]
            if (
                rest in _NUMBER_WORD_VARIANTS
                or rest in _FRACTION_WORDS
                or rest in _UNIT_MULTIPLIERS
                or re.fullmatch(r"\d+(?:\.\d+)?", rest or "")
            ):
                out.append("و")
                out.append(rest)
                continue
        out.append(tok)
    return out


def _token_to_number(token: str) -> Optional[float]:
    if not token:
        return None

    t = _normalize_number_words(token)
    t = t.replace("-", " ").replace("_", " ").strip(" ,:/\\")
    if not t:
        return None

    compact = t.replace(",", "")
    if re.fullmatch(r"\d+(?:\.\d+)?", compact):
        try:
            return float(compact)
        except Exception:
            return None

    if t in _NUMBER_WORD_VARIANTS:
        return float(_NUMBER_WORD_VARIANTS[t])

    if t in _FRACTION_WORDS:
        return float(_FRACTION_WORDS[t])

    parts = _split_prefixed_waw_tokens(t.split())
    parts = [p for p in parts if p and p not in _NUMBER_CONNECTORS]

    if not parts:
        return None

    total = 0.0
    matched = False
    i = 0

    while i < len(parts):
        three = " ".join(parts[i:i + 3])
        two = " ".join(parts[i:i + 2])
        one = parts[i]

        if three in _NUMBER_WORD_VARIANTS:
            total += float(_NUMBER_WORD_VARIANTS[three])
            matched = True
            i += 3
            continue

        if two in _NUMBER_WORD_VARIANTS:
            total += float(_NUMBER_WORD_VARIANTS[two])
            matched = True
            i += 2
            continue

        if two in _FRACTION_WORDS:
            total += float(_FRACTION_WORDS[two])
            matched = True
            i += 2
            continue

        if one in _NUMBER_WORD_VARIANTS:
            total += float(_NUMBER_WORD_VARIANTS[one])
            matched = True
            i += 1
            continue

        if one in _FRACTION_WORDS:
            total += float(_FRACTION_WORDS[one])
            matched = True
            i += 1
            continue

        if re.fullmatch(r"\d+(?:\.\d+)?", one):
            total += float(one)
            matched = True
            i += 1
            continue

        return None

    return total if matched else None


def _extract_number_before_unit(t: str, unit_pattern: str) -> Optional[float]:
    if not t:
        return None

    normalized_t = _normalize_number_words(t)
    pattern = rf"([^\n\r:]+?)\s*(?:{unit_pattern})\b"
    matches = list(re.finditer(pattern, normalized_t))

    for m in matches:
        phrase = m.group(1).strip()
        parts = re.split(r"\s*[:/\\\-]\s*", phrase)
        candidate = parts[-1].strip() if parts else phrase
        num = _token_to_number(candidate)
        if num is not None:
            return float(num)

    return None


def _contains_any(t: str, words) -> bool:
    return any(w in t for w in words)


def _count_matches(t: str, words) -> int:
    return sum(1 for w in words if w in t)


def _is_price_per_meter(text: str) -> bool:
    t = _norm(text)
    return _contains_any(
        t,
        [
            "للمتر",
            "للمتر الواحد",
            "للمترمربع",
            "للمتر المربع",
            "سعر المتر",
            "سعر المتر الواحد",
            "للمتر فقط",
            "للمتر الواحد فقط",
        ],
    )


def _decide_root(text: str) -> Optional[str]:
    t = _norm(text)

    # إذا السعر للمتر نعتبره بيع مباشرة
    if _is_price_per_meter(t):
        return "sale"

    if _contains_any(t, ["للبيع", "بيع"]):
        return "sale"

    if _contains_any(t, ["للايجار", "ايجار", "إيجار", "للاجار", "اجار"]):
        return "rent"

    return None


# =========================
# تحديد النوع داخل البيع
# =========================
def _sale_base(text: str) -> str:
    t = _norm(text)

    residential_words = [
        "دار", "بيت", "منزل", "شقة", "شقه", "طابق", "طوابق",
        "غرف", "غرفة", "غرفه", "منام", "صالة", "صاله",
        "استقبال", "مطبخ", "كراج", "حديقة", "حديقه",
        "مشتمل", "مشتملات", "بناء", "تشطيب", "سكني", "للسكن",
        "درج", "شلال", "سكاي لايت",
    ]

    commercial_words = [
        "تجاري", "تجارية", "محل", "محلات", "مكتب", "مكاتب", "مخزن", "مستودع",
        "هنگر", "هنكر", "ورشة", "ورشه", "معرض", "بناية", "بنايه", "عمارة", "عماره",
        "مطعم", "كوفي", "مقهى", "صيدلية", "صيدليه", "مول",
        "شركة", "شركه", "عيادة", "عياده", "مختبر", "مخبز", "صالون",
    ]

    land_words = [
        "قطعة ارض", "قطعه ارض", "ارض سكنية", "ارض سكنيه",
        "ارض تجارية", "ارض تجاريه", "عقار فارغ", "بدون بناء",
        "للأرض فقط", "للارض فقط", "قيمة ارض", "قيمه ارض",
        "ارض", "قطعة", "قطعه",
    ]

    residential_score = _count_matches(t, residential_words)
    commercial_score = _count_matches(t, commercial_words)
    land_score = _count_matches(t, land_words)

    if _contains_any(
        t,
        [
            "دار", "بيت", "منزل", "شقة", "شقه", "طابق", "طوابق",
            "غرف", "غرفة", "غرفه", "منام", "صالة", "صاله",
            "استقبال", "مطبخ", "كراج", "حديقة", "حديقه",
            "مشتمل", "مشتملات", "بناء", "تشطيب",
        ],
    ):
        land_score -= 2

    if _contains_any(t, ["قطعة ارض", "قطعه ارض", "عقار فارغ", "بدون بناء", "للأرض فقط", "للارض فقط", "قيمة ارض", "قيمه ارض"]):
        return "sale/land"

    if commercial_score > residential_score and commercial_score >= land_score and commercial_score > 0:
        return "sale/commercial"

    if residential_score >= commercial_score and residential_score > 0:
        return "sale/residential"

    if land_score > 0:
        return "sale/land"

    return "sale/residential"


# =========================
# تحديد النوع داخل الإيجار
# =========================
def _rent_base(text: str) -> str:
    t = _norm(text)

    commercial_words = [
        "تجاري", "تجارية", "محل", "محلات", "مكتب", "مكاتب", "مخزن", "مستودع",
        "هنگر", "هنكر", "ورشة", "ورشه", "معرض", "بناية", "عمارة", "مول",
        "شركة", "شركه", "عيادة", "عياده", "مختبر", "مخبز", "صالون",
    ]

    residential_words = [
        "دار", "بيت", "منزل", "شقة", "شقه", "طابق",
        "غرف", "غرفة", "غرفه", "منام", "صالة", "صاله",
        "استقبال", "مطبخ", "كراج", "حديقة", "حديقه",
        "مشتمل", "مشتملات", "عائلي", "للعوائل", "سكني", "للسكن",
        "مفروش", "غير مفروش",
    ]

    commercial_score = _count_matches(t, commercial_words)
    residential_score = _count_matches(t, residential_words)

    if commercial_score > residential_score and commercial_score >= 1:
        return "rent/commercial"

    return "rent/residential"


def _is_old_house_dual_candidate(text: str) -> bool:
    t = _norm(text)

    return (
        _contains_any(t, ["دار", "بيت", "منزل"])
        and
        _contains_any(
            t,
            [
                "قديم", "قديمه", "قديمة",
                "بناء قديم",
                "تراث", "تراثي", "تراثيه",
                "متهالك", "متهالكه",
                "يصلح هدم", "تصلح هدم",
                "هدم واعاده بناء", "هدم واعادة بناء",
                "قيمه ارض", "قيمة ارض",
                "للارض فقط", "للأرض فقط",
            ],
        )
    )


# =========================
# استخراج المساحة بالمتر
# =========================
def _extract_area_m2(text: str) -> Optional[float]:
    t = _norm(text)

    patterns = [
        r"(?:المساحة|المساحه)\s*[:/\-]?\s*(\d+(?:\.\d+)?)\s*(?:متر|م)",
        r"(\d+(?:\.\d+)?)\s*(?:متر مربع|مترمربع)",
        r"(\d+(?:\.\d+)?)\s*(?:متر|م)\s*(?:مربع)?",
    ]

    for pat in patterns:
        m = re.search(pat, t)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass

    return None


# =========================
# تحويل تعبير سعر إلى دينار
# =========================
def _parse_price_phrase_to_iqd(phrase: str) -> Optional[float]:
    t = _normalize_number_words(phrase)
    if not t:
        return None

    # لو النص كله رقم كبير بدون وحدات
    t_compact = t.replace(",", "")
    if (
        re.search(r"\b\d{4,}(?:\.\d+)?\b", t_compact)
        and not re.search(r"\b(?:الف|مليون|مليار)\b", t)
    ):
        m_big = re.search(r"\b(\d{4,}(?:\.\d+)?)\b", t_compact)
        if m_big:
            try:
                return float(m_big.group(1))
            except Exception:
                pass

    tokens = _split_prefixed_waw_tokens(t.split())
    if not tokens:
        return None

    total = 0.0
    matched_any_unit = False
    buffer_tokens = []
    i = 0

    while i < len(tokens):
        tok = tokens[i]

        if tok in _UNIT_MULTIPLIERS:
            if buffer_tokens:
                number_value = _token_to_number(" ".join(buffer_tokens))
            else:
                number_value = 1.0

            if number_value is None and not buffer_tokens:
                number_value = 1.0

            if number_value is not None:
                total += float(number_value) * _UNIT_MULTIPLIERS[tok]
                matched_any_unit = True
                buffer_tokens = []

                # دعم مثل: مليون و نص / مليار وربع / مليون وثلاثه ارباع
                j = i + 1
                if j < len(tokens) and tokens[j] in _NUMBER_CONNECTORS:
                    j += 1

                if j < len(tokens):
                    if j + 1 < len(tokens) and " ".join(tokens[j:j + 2]) == "ثلاثه ارباع":
                        total += 0.75 * _UNIT_MULTIPLIERS[tok]
                        i = j + 2
                        continue

                    frac = _FRACTION_WORDS.get(tokens[j])
                    if frac is not None:
                        total += frac * _UNIT_MULTIPLIERS[tok]
                        i = j + 1
                        continue

                i += 1
                continue

        buffer_tokens.append(tok)
        i += 1

    if matched_any_unit:
        if total > 0:
            return total
        return None

    plain_value = _token_to_number(t)
    if plain_value is not None:
        return float(plain_value)

    m = re.search(r"\b(\d+(?:\.\d+)?)\b", t_compact)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass

    return None


def _should_scale_small_rent_value(raw_phrase: str, parsed_value: float) -> bool:
    if parsed_value >= 10_000:
        return False

    t = _normalize_number_words(raw_phrase)

    if re.search(r"\b\d{4,}\b", t.replace(",", "")):
        return False

    if _contains_any(t, ["الف", "الاف", "ألف", "مليون", "ملايين", "ملاين", "مليار", "مليارات"]):
        return False

    return True


# =========================
# استخراج السعر بالدينار
# =========================
def _extract_price_iqd(text: str) -> Optional[float]:
    t = _norm(text)

    # إذا السعر للمتر -> سعر المتر * المساحة
    if _is_price_per_meter(t):
        price_phrase = None

        m = re.search(
            r"((?:\d+(?:\.\d+)?\s*(?:مليار|مليون|الف|ألف)?(?:\s*و\s*\d+(?:\.\d+)?\s*(?:مليار|مليون|الف|ألف)?)?(?:\s*(?:ونص|ونصف))?))\s*(?:للمتر|للمتر الواحد|للمتر المربع|سعر المتر)",
            t
        )
        if m:
            price_phrase = m.group(1)

        if not price_phrase:
            m2 = re.search(
                r"(?:السعر|سعر)\s*[:/\-]?\s*([^.\n\r]+?)\s*(?:للمتر|للمتر الواحد|للمتر المربع)",
                t
            )
            if m2:
                price_phrase = m2.group(1)

        area = _extract_area_m2(t)
        per_meter = _parse_price_phrase_to_iqd(price_phrase or t)

        if per_meter is not None and area is not None:
            return per_meter * area

    m = re.search(r"(?:السعر|سعر)\s*[:/\\\-]?\s*([^\n\r]+)", t)
    if m:
        price_line = m.group(1)
        parsed = _parse_price_phrase_to_iqd(price_line)
        if parsed is not None:
            if _contains_any(t, ["للايجار", "ايجار", "اجار", "للاجار"]) and _should_scale_small_rent_value(price_line, parsed):
                return parsed * 1_000
            return parsed

    parsed2 = _parse_price_phrase_to_iqd(t)
    if parsed2 is not None:
        if _contains_any(t, ["للايجار", "ايجار", "اجار", "للاجار"]) and _should_scale_small_rent_value(t, parsed2):
            return parsed2 * 1_000
        return parsed2

    return None


def _bucket_bounds_from_title(
    title: str,
    *,
    default_scale: float = 1.0,
) -> Optional[Tuple[Optional[float], Optional[float]]]:
    """
    يفهم:
      - اقل من 500 الف
      - اكثر من 2 مليون
      - 500 - 600 الف
      - 500 الى 600 الف
      - 500/600 الف
      - 500\\600 الف
      - 500_600 الف
      - 1.5 مليون - 2 مليون
      - 1.5 - 2 مليون
      - 1.5 مليون الى 2 مليون
      - 1.5 الى 2 مليون
      - 1.5 مليون / 2 مليون
      - 1.5 / 2 مليون
      - 1 مليون - 1.5 مليار
    """
    t = _norm(title)

    separators_pattern = r"\s*(?:-|الى|إلى|/|\\|_)\s*"
    normalized = re.sub(separators_pattern, " - ", t)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if "اقل من" in normalized:
        phrase = normalized.replace("اقل من", "").strip()
        high = _parse_price_phrase_to_iqd(phrase)
        if high is not None:
            if high < 10_000 and default_scale != 1.0:
                high *= default_scale
            return (None, high)

    if "اكثر من" in normalized:
        phrase = normalized.replace("اكثر من", "").strip()
        low = _parse_price_phrase_to_iqd(phrase)
        if low is not None:
            if low < 10_000 and default_scale != 1.0:
                low *= default_scale
            return (low, None)

    parts = [p.strip() for p in normalized.split(" - ") if p.strip()]
    if len(parts) >= 2:
        left = parts[0]
        right = parts[1]

        units = ["الف", "ألف", "مليون", "مليار"]

        left_has_unit = _contains_any(left, units)
        right_has_unit = _contains_any(right, units)

        if not left_has_unit and right_has_unit:
            if "مليار" in right:
                left = f"{left} مليار"
            elif "مليون" in right:
                left = f"{left} مليون"
            elif "الف" in right or "ألف" in right:
                left = f"{left} الف"

        if left_has_unit and not right_has_unit:
            if "مليار" in left:
                right = f"{right} مليار"
            elif "مليون" in left:
                right = f"{right} مليون"
            elif "الف" in left or "ألف" in left:
                right = f"{right} الف"

        low = _parse_price_phrase_to_iqd(left)
        high = _parse_price_phrase_to_iqd(right)

        if low is not None and high is not None:
            if low < 10_000 and default_scale != 1.0:
                low *= default_scale
            if high < 10_000 and default_scale != 1.0:
                high *= default_scale
            return (low, high)

    scale = None
    if "مليار" in normalized:
        scale = 1_000_000_000
    elif "مليون" in normalized:
        scale = 1_000_000
    elif "الف" in normalized or "الاف" in normalized or "ألف" in normalized:
        scale = 1_000

    if scale is None:
        scale = default_scale

    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", normalized)]
    if not nums:
        return None

    if "اقل" in normalized:
        return (None, nums[0] * scale)
    if "اكثر" in normalized:
        return (nums[0] * scale, None)
    if len(nums) >= 2:
        return (nums[0] * scale, nums[1] * scale)

    return None


def _format_num_clean(n: float) -> str:
    s = f"{n:.2f}".rstrip("0").rstrip(".")
    return s


def _guess_step_and_unit(bounds: List[Tuple[Optional[float], Optional[float]]], base_path: str, price_iqd: float) -> Tuple[float, str]:
    """
    يخمّن حجم الخطوة ووحدة التسمية بشكل ذكي يراعي مستوى السعر.
    """

    # الإيجارات
    if base_path.startswith("rent/"):
        if price_iqd < 1_000_000:
            return 100_000, "الف"
        return 500_000, "مليون"

    # البيع
    if base_path.startswith("sale/"):
        if price_iqd < 500_000_000:
            return 50_000_000, "مليون"
        if price_iqd < 1_000_000_000:
            return 250_000_000, "مليون"
        return 500_000_000, "مليار"

    # fallback
    diffs = []
    for low, high in bounds:
        if low is not None and high is not None and high > low:
            diffs.append(high - low)

    if diffs:
        step = min(diffs)
    else:
        step = 500_000

    if step >= 1_000_000_000:
        unit = "مليار"
    elif step >= 1_000_000:
        unit = "مليون"
    else:
        unit = "الف"

    return step, unit


def _format_bucket_title(low: float, high: float, unit: str) -> str:
    if unit == "مليار":
        a = _format_num_clean(low / 1_000_000_000)
        b = _format_num_clean(high / 1_000_000_000)
        return f"{a} - {b} مليار"

    if unit == "مليون":
        a = _format_num_clean(low / 1_000_000)
        b = _format_num_clean(high / 1_000_000)
        return f"{a} - {b} مليون"

    a = _format_num_clean(low / 1_000)
    b = _format_num_clean(high / 1_000)
    return f"{a} - {b} الف"


def _slugify_bucket_key(low: float, high: float, unit: str) -> str:
    if unit == "مليار":
        a = _format_num_clean(low / 1_000_000_000).replace(".", "_")
        b = _format_num_clean(high / 1_000_000_000).replace(".", "_")
        return f"{a}_{b}b"

    if unit == "مليون":
        a = _format_num_clean(low / 1_000_000).replace(".", "_")
        b = _format_num_clean(high / 1_000_000).replace(".", "_")
        return f"{a}_{b}m"

    a = _format_num_clean(low / 1_000).replace(".", "_")
    b = _format_num_clean(high / 1_000).replace(".", "_")
    return f"{a}_{b}k"


def _ensure_bucket_exists(categories: dict, base_path: str, price_iqd: float) -> Optional[str]:
    """
    إذا ما لقى bucket مناسبة، ينشئها تلقائياً بنفس نمط اللستات الموجودة.
    """
    base = get_node(categories, base_path)
    if not base or "sub" not in base:
        return None

    default_scale = 1_000 if base_path.startswith("rent/") else 1.0

    parsed_bounds = []
    for _, child in base["sub"].items():
        title = child.get("title", "")
        bounds = _bucket_bounds_from_title(title, default_scale=default_scale)
        if bounds:
            parsed_bounds.append(bounds)

    if not parsed_bounds:
        return None

    ranges = [(lo, hi) for lo, hi in parsed_bounds if lo is not None and hi is not None]
    if not ranges:
        return None

    ranges.sort(key=lambda x: x[0])

    step, unit = _guess_step_and_unit(ranges, base_path, price_iqd)

    # نحدد البداية حسب step
    if base_path.startswith("rent/"):
        if price_iqd < 1_000_000:
            low = int(price_iqd // step) * step
            high = low + step
        else:
            low = int((price_iqd - 1_000_000) // step) * step + 1_000_000
            high = low + step
    else:
        low = int(price_iqd // step) * step
        high = low + step

    key = _slugify_bucket_key(low, high, unit)
    title = _format_bucket_title(low, high, unit)

    if key not in base["sub"]:
        base["sub"][key] = {
            "title": title,
            "items": []
        }

    return f"{base_path}/{key}"


def _find_bucket_path(categories: dict, base_path: str, price_iqd: float, *, auto_create: bool = True) -> Optional[str]:
    base = get_node(categories, base_path)
    if not base or "sub" not in base:
        return None

    default_scale = 1.0
    if base_path.startswith("rent/"):
        default_scale = 1_000

    for key, child in base["sub"].items():
        title = child.get("title", "")
        bounds = _bucket_bounds_from_title(title, default_scale=default_scale)
        if not bounds:
            continue

        low, high = bounds

        if low is None and high is not None:
            if price_iqd < high:
                return f"{base_path}/{key}"
        elif low is not None and high is None:
            if price_iqd >= low:
                return f"{base_path}/{key}"
        elif low is not None and high is not None:
            if (low - 1000) <= price_iqd <= (high + 1000):
                return f"{base_path}/{key}"

    if auto_create:
        return _ensure_bucket_exists(categories, base_path, price_iqd)

    return None


def _ensure_without_price_bucket(categories: dict, base_path: str) -> Optional[str]:
    base = get_node(categories, base_path)
    if not base or "sub" not in base:
        return None

    key = "without_price"
    if key not in base["sub"]:
        base["sub"][key] = {
            "title": "اعلان بدون سعر",
            "items": []
        }

    return f"{base_path}/{key}"


def _has_explicit_price_label_without_value(text: str) -> bool:
    if not text:
        return False

    for line in text.splitlines():
        t = _norm(line)
        if re.fullmatch(r"(?:السعر|سعر)\s*[:/\\-]?\s*", t):
            return True

    return False


def _fallback_without_price_targets(categories: dict, text: str) -> Tuple[List[str], int]:
    targets = []
    created = 0
    seen = set()

    root = _decide_root(text)

    if root == "sale":
        base_paths = [_sale_base(text)]
        if _is_old_house_dual_candidate(text):
            base_paths.append("sale/land")
    elif root == "rent":
        base_paths = [_rent_base(text)]
    else:
        base_paths = [_rent_base(text)]
        sale_base = _sale_base(text)
        if sale_base not in base_paths:
            base_paths.append(sale_base)
        if _is_old_house_dual_candidate(text) and "sale/land" not in base_paths:
            base_paths.append("sale/land")

    for base_path in base_paths:
        base_node = get_node(categories, base_path)
        if not base_node or "sub" not in base_node:
            continue
        existed = "without_price" in base_node["sub"]
        target = _ensure_without_price_bucket(categories, base_path)
        if target and target not in seen:
            seen.add(target)
            targets.append(target)
            if not existed:
                created += 1

    return targets, created


def smart_process_and_move(*, delete_unmatched: bool = True) -> Tuple[bool, str]:
    """
    ينقل من smart_inbox إلى وجهته.
    إذا delete_unmatched=True: أي إعلان ما يطابق أو ما يطلع سعر => ينحذف من inbox.
    """
    data = load_data()
    cats = data.get("categories", {})

    inbox = get_node(cats, "smart_inbox")
    if not inbox:
        return False, "⚠️ لستة فرز ذكي غير موجودة."

    items = inbox.get("items", [])
    if not items:
        return True, "ℹ️ لا توجد إعلانات داخل فرز ذكي."

    moved = 0
    deleted = 0
    created = 0

    for item in list(items):
        text = item.get("text", "")
        root = _decide_root(text)
        price = _extract_price_iqd(text) if text else None

        if price is None:
            if _has_explicit_price_label_without_value(text):
                targets, created_now = _fallback_without_price_targets(cats, text)
                created += created_now

                if targets:
                    appended = 0

                    for idx, target in enumerate(targets):
                        node = get_node(cats, target)
                        if not node:
                            continue

                        if idx == 0:
                            node.setdefault("items", []).append(item)
                        else:
                            node.setdefault("items", []).append(dict(item))

                        appended += 1

                    if appended > 0:
                        items.remove(item)
                        moved += appended
                        continue

            if delete_unmatched:
                items.remove(item)
                deleted += 1
            continue

        targets = []
        before_keys_map = {}

        if root == "sale":
            base = _sale_base(text)
            base_node = get_node(cats, base)
            if base_node and "sub" in base_node:
                before_keys_map[base] = set(base_node["sub"].keys())
            target = _find_bucket_path(cats, base, price, auto_create=True)
            if target:
                targets.append(target)

            if _is_old_house_dual_candidate(text):
                land_base = "sale/land"
                land_node = get_node(cats, land_base)
                if land_node and "sub" in land_node:
                    before_keys_map[land_base] = set(land_node["sub"].keys())
                land_target = _find_bucket_path(cats, land_base, price, auto_create=True)
                if land_target and land_target not in targets:
                    targets.append(land_target)

        elif root == "rent":
            base = _rent_base(text)
            base_node = get_node(cats, base)
            if base_node and "sub" in base_node:
                before_keys_map[base] = set(base_node["sub"].keys())
            target = _find_bucket_path(cats, base, price, auto_create=True)
            if target:
                targets.append(target)

        else:
            rent_base = _rent_base(text)
            rent_node = get_node(cats, rent_base)
            if rent_node and "sub" in rent_node:
                before_keys_map[rent_base] = set(rent_node["sub"].keys())
            rent_target = _find_bucket_path(cats, rent_base, price, auto_create=True)
            if rent_target:
                targets.append(rent_target)

            if not targets:
                sale_base = _sale_base(text)
                sale_node = get_node(cats, sale_base)
                if sale_node and "sub" in sale_node:
                    before_keys_map[sale_base] = set(sale_node["sub"].keys())
                sale_target = _find_bucket_path(cats, sale_base, price, auto_create=True)
                if sale_target:
                    targets.append(sale_target)

                if _is_old_house_dual_candidate(text):
                    land_base = "sale/land"
                    land_node = get_node(cats, land_base)
                    if land_node and "sub" in land_node:
                        before_keys_map[land_base] = set(land_node["sub"].keys())
                    land_target = _find_bucket_path(cats, land_base, price, auto_create=True)
                    if land_target and land_target not in targets:
                        targets.append(land_target)

        for base_path, before_keys in before_keys_map.items():
            base_node = get_node(cats, base_path)
            if base_node and "sub" in base_node:
                after_keys = set(base_node["sub"].keys())
                if len(after_keys) > len(before_keys):
                    created += len(after_keys - before_keys)

        if not targets:
            if delete_unmatched:
                items.remove(item)
                deleted += 1
            continue

        appended = 0

        for idx, target in enumerate(targets):
            node = get_node(cats, target)
            if not node:
                continue

            if idx == 0:
                node.setdefault("items", []).append(item)
            else:
                node.setdefault("items", []).append(dict(item))

            appended += 1

        if appended == 0:
            if delete_unmatched:
                items.remove(item)
                deleted += 1
            continue

        items.remove(item)
        moved += appended

    save_data(data)

    if delete_unmatched:
        return True, f"✅ تم نقل {moved} إعلان. 🆕 تم إنشاء {created} لستة. 🗑 تم حذف {deleted} إعلان لعدم التطابق."
    return True, f"✅ تم نقل {moved} إعلان. 🆕 تم إنشاء {created} لستة. (بقي {len(items)} داخل فرز ذكي)"