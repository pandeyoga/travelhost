"""services/translate_ai.py — CMS-06: bantuan terjemahan ID→EN (opsional, bisa diedit).

Prinsip
-------
1. **Bantuan, bukan otomatis.** Hasil terjemahan dikembalikan sebagai SARAN ke editor;
   tidak pernah langsung menimpa konten tayang. Editor tetap pemilik keputusan.
2. **Degradasi mulus.** Bila `EMERGENT_LLM_KEY` belum diisi / pustaka tak tersedia /
   model gagal, endpoint membalas 503 berpesan jelas — CMS tetap bisa dipakai manual.
3. **Keluaran ketat JSON** (`{field: teks}`) supaya bisa dipetakan langsung ke form, dan
   markup HTML artikel DIPERTAHANKAN (hanya teks di dalam tag yang diterjemahkan).

Kunci diambil dari env `EMERGENT_LLM_KEY` (universal key Emergent) — tidak pernah
di-log & tidak pernah dikirim ke frontend.
"""
import asyncio
import json
import os
import re

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-5.4"
TIMEOUT_SECONDS = 90
MAX_FIELDS = 12
MAX_CHARS_PER_FIELD = 12000

LANG_NAMES = {"en": "English", "id": "Bahasa Indonesia"}


class TranslateError(RuntimeError):
    """Gagal menerjemahkan — WAJIB dilaporkan 4xx/503 berpesan, bukan 500 telanjang."""


def api_key() -> str:
    return (os.environ.get("EMERGENT_LLM_KEY") or "").strip()


def available() -> bool:
    if not api_key():
        return False
    try:
        import emergentintegrations.llm.chat  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _extract_json(text: str) -> dict:
    """Ambil objek JSON dari balasan model (toleran terhadap ```json fences / prosa)."""
    raw = str(text or "").strip()
    if not raw:
        raise TranslateError("Model tidak mengembalikan apa pun")
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fence:
        raw = fence.group(1)
    else:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TranslateError("Balasan model bukan JSON yang sah") from exc
    if not isinstance(data, dict):
        raise TranslateError("Balasan model bukan objek JSON")
    return data


def _prompt(fields: dict, target: str, context: str) -> str:
    target_name = LANG_NAMES.get(target, target)
    payload = json.dumps(fields, ensure_ascii=False, indent=2)
    return (
        f"Translate the following Indonesian website content into {target_name}.\n\n"
        f"Context: {context or 'Travel & transport rental company website (Java-Bali, Indonesia).'}\n\n"
        "RULES:\n"
        "1. Return ONLY a JSON object with EXACTLY the same keys as the input.\n"
        "2. Translate values naturally for tourists; keep brand names, place names, "
        "vehicle model names (Hiace Premio, Alphard) unchanged.\n"
        "3. Preserve HTML tags, attributes and their order exactly; translate only the text nodes.\n"
        "4. Keep numbers, prices, dates and units unchanged (do not convert currencies).\n"
        "5. Never invent new information and never add commentary.\n"
        "6. If a value is an array of strings, return an array of translated strings.\n\n"
        f"INPUT JSON:\n{payload}"
    )


async def translate_fields(fields: dict, target: str = "en", context: str = "",
                           model: str = DEFAULT_MODEL, provider: str = DEFAULT_PROVIDER) -> dict:
    """Terjemahkan `{field: teks|list}` → `{field: teks|list}`. Raise TranslateError bila gagal."""
    clean = {}
    for key, val in (fields or {}).items():
        if isinstance(val, list):
            items = [str(v)[:MAX_CHARS_PER_FIELD] for v in val if str(v or "").strip()]
            if items:
                clean[str(key)] = items
        elif str(val or "").strip():
            clean[str(key)] = str(val)[:MAX_CHARS_PER_FIELD]
        if len(clean) >= MAX_FIELDS:
            break
    if not clean:
        raise TranslateError("Tidak ada teks yang bisa diterjemahkan")
    if not api_key():
        raise TranslateError("EMERGENT_LLM_KEY belum diisi di backend/.env — "
                             "terjemahan otomatis tidak tersedia, isi manual tetap bisa")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as exc:  # noqa: BLE001
        raise TranslateError("Pustaka emergentintegrations tidak tersedia di server") from exc

    chat = LlmChat(
        api_key=api_key(),
        session_id=f"cms-translate-{target}",
        system_message=("You are a professional Indonesian→English translator for travel "
                        "marketing websites. You always answer with strict JSON only."),
    ).with_model(provider, model)

    async def _run():
        return await chat.send_message(UserMessage(text=_prompt(clean, target, context)))

    try:
        reply = await asyncio.wait_for(_run(), timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise TranslateError("Terjemahan otomatis melebihi batas waktu — coba lagi") from exc
    except Exception as exc:  # noqa: BLE001
        raise TranslateError(f"Model terjemahan gagal: {str(exc)[:180]}") from exc

    text = reply if isinstance(reply, str) else getattr(reply, "content", "") or str(reply)
    data = _extract_json(text)
    out = {}
    for key in clean:
        val = data.get(key)
        if isinstance(val, list):
            out[key] = [str(v) for v in val if str(v or "").strip()]
        elif val is not None and str(val).strip():
            out[key] = str(val)
    if not out:
        raise TranslateError("Model tidak mengembalikan field yang diminta")
    return out
