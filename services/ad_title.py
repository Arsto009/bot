import re

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_ARABIC_DIGITS_2 = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _norm(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = t.translate(_ARABIC_DIGITS).translate(_ARABIC_DIGITS_2)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return t


def _first_non_empty_line(text: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip()
        if s:
            return s
    return (text or "").strip()


def short_title_from_text(text: str) -> str:
    if not text:
        return "إعلان"

    t = _norm(text)
    tl = t.lower()

    kind = ""
    if any(w in tl for w in ["شقه", "شقة", "شقق"]):
        kind = "شقة"
    elif any(w in tl for w in ["بيت", "دار", "منزل"]):
        kind = "بيت"
    elif any(w in tl for w in ["ارض", "قطعة"]):
        kind = "قطعة أرض"
    elif "محل" in tl:
        kind = "محل"

    op = ""
    if "بيع" in tl:
        op = "بيع"
    elif "ايجار" in tl or "اجار" in tl:
        op = "إيجار"

    area = ""
    m = re.search(r"(?:منطقة|في)\s+([^\n\r\-]{2,30})", t)
    if m:
        area = m.group(1).strip()

    parts = []
    if kind:
        parts.append(kind)
    if op:
        parts.append(op)
    if area:
        parts.append(area)

    if not parts:
        line = _first_non_empty_line(t)
        if len(line) > 60:
            line = line[:60] + "..."
        return line

    return " - ".join(parts)