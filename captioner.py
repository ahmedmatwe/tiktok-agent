"""Writes platform-specific titles/captions with a free LLM (Gemini free tier or local Ollama)."""
import json
import os
import re

import requests

PROMPT = """أنت خبير سوشيال ميديا ومتخصص في كتابة عناوين فيرال.
عندي فيديو قصير اتنشر على تيك توك، ده الوصف الأصلي بتاعه:
---
{description}
---
اكتب محتوى نشر جذاب باللغة: {language}.
القواعد:
- youtube_title: عنوان قوي وجذاب أقل من 90 حرف، من غير هاشتاجات.
- youtube_description: وصف من 2-3 سطور + هاشتاجات مناسبة وفي آخرها #Shorts.
- youtube_tags: من 5 لـ 12 كلمة مفتاحية (قائمة).
- facebook_caption: كابشن قصير جذاب مع 3-5 هاشتاجات وسؤال يشجع على التفاعل.
- instagram_caption: كابشن جذاب + سطر فاضي + من 8 لـ 15 هاشتاج مناسبين.
لو الوصف فاضي، استنتج موضوع عام مناسب ومتقولش إنك مش عارف.
رجّع JSON فقط بالمفاتيح دي بالظبط: youtube_title, youtube_description, youtube_tags, facebook_caption, instagram_caption
"""


def _gemini(prompt):
    key = os.environ["GEMINI_API_KEY"]
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
        },
        timeout=90,
    )
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _ollama(prompt):
    r = requests.post(
        f"{os.getenv('OLLAMA_URL', 'http://localhost:11434')}/api/generate",
        json={"model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"), "prompt": prompt, "format": "json", "stream": False},
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["response"]


def _parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def _fallback(description):
    base = (description or "فيديو جديد").strip()
    title = re.sub(r"#\S+", "", base).strip()[:90] or "فيديو جديد 🔥"
    return {
        "youtube_title": title,
        "youtube_description": f"{base}\n\n#Shorts",
        "youtube_tags": [],
        "facebook_caption": base,
        "instagram_caption": base,
    }


def generate(description):
    prompt = PROMPT.format(description=description or "(بدون وصف)", language=os.getenv("CAPTION_LANGUAGE", "العربية"))
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    try:
        meta = _parse(_ollama(prompt) if provider == "ollama" else _gemini(prompt))
    except Exception as e:  # never block publishing because the LLM is down / rate limited
        print(f"  ⚠️  AI caption failed ({e}); using original description")
        return _fallback(description)
    fb = _fallback(description)
    for k, v in fb.items():
        meta.setdefault(k, v)
    meta["youtube_title"] = str(meta["youtube_title"])[:100]
    if not isinstance(meta["youtube_tags"], list):
        meta["youtube_tags"] = [t.strip() for t in str(meta["youtube_tags"]).split(",") if t.strip()]
    return meta
