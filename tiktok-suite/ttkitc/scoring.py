"""意向评分规则（CONTRACT.md「意向评分规则」节）。

规则：
- 问价关键词(how much/price/prezzo/价格/多少钱/quote/прейскурант) +40
- bio 含 whatsapp/phone/数字连号 ≥9位 +30
- dealer 关键词(auto/cars/motor/ev/export/dealer/электро/Cars.TJ 等) +20
- followers>500 +10；aweme_count>0 +10；上限 100
"""

PRICE_KEYWORDS = ["how much", "price", "prezzo", "价格", "多少钱", "quote", "прейскурант"]
DEALER_KEYWORDS = ["auto", "cars", "motor", "ev", "export", "dealer", "электро", "cars.tj"]

import re

RE_DIGITS_9 = re.compile(r"\d[\d\s\-()]{7,}\d")


def score_lead(lead: dict) -> int:
    score = 0
    text = " ".join(str(lead.get(k) or "") for k in ("comment_text", "nickname")).lower()
    bio = str(lead.get("bio") or "").lower()

    if any(k in text for k in PRICE_KEYWORDS):
        score += 40
    if ("whatsapp" in bio or "phone" in bio or RE_DIGITS_9.search(bio)):
        score += 30
    if any(k in text or k in bio for k in DEALER_KEYWORDS):
        score += 20
    if (lead.get("followers") or 0) > 500:
        score += 10
    if (lead.get("aweme_count") or 0) > 0:
        score += 10
    return min(score, 100)
