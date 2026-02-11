import re
from typing import List, Optional


_COMPANY_STOPWORDS = {"ANNOUNCES", "RESULTS", "EARNINGS", "REPORT", "STATEMENT", "PRESS", "RELEASE","THIRD", "FOURTH","FIRST", "SECOND", "QUARTER", "Q1", "Q2", "Q3", "Q4","CONSOLIDATED", "FINANCIAL", "GUIDANCE", "INFORMATION", "ABOUT",}

def _clean_company_name(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*[-–—]\s*.*$", "", s)
    return s.strip(" .,:;|/\\")[:200]

def extract_company_from_markdown(md: str) -> Optional[str]:
    lines = [ln.strip() for ln in md.splitlines() if ln.strip()]
    if not lines:
        return None

    header = None
    for ln in lines[:30]:
        if ln.startswith("#"):
            header = re.sub(r"^#+\s*", "", ln).strip()
            break

    if header:
        tokens = header.split()
        cut_idx = None
        for i, t in enumerate(tokens):
            if re.sub(r"[^A-Za-z]", "", t).upper() in _COMPANY_STOPWORDS:
                cut_idx = i
                break
        if cut_idx and cut_idx > 0:
            cand = _clean_company_name(" ".join(tokens[:cut_idx]))
            if len(cand) >= 3:
                return cand

        cand = _clean_company_name(header)
        if len(cand) >= 3:
            return cand

    top = "\n".join(lines[:80])
    m = re.search(
        r"\b([A-Z][A-Za-z0-9&.,'’\- ]{2,80}?)\s*(?:,?\s*(?:Inc\.|Incorporated|Corp\.|Corporation|S\.A\.|Ltd\.|Limited|PLC|LLC))\b",
        top,
    )
    if m:
        return _clean_company_name(m.group(0))
