#!/usr/bin/env python3
"""
Geo Config — configurações por país/região para criação de perfis globais.
Cobre idioma, fuso, plataformas dominantes, cultura de conteúdo e horários.
"""

# ─── Mapa completo de países ──────────────────────────────────────────────────
# Formato: código_país → { idioma, gtts_lang, fuso, plataformas, cultura }

COUNTRIES = {
    # ── América Latina ──────────────────────────────────────────────────────
    "BR": {
        "nome": "Brasil",
        "idioma": "Português (BR)",
        "gtts_lang": "pt",
        "fuso": "America/Sao_Paulo",
        "plataformas_top": ["instagram", "tiktok", "youtube", "facebook", "twitter"],
        "horarios_post": ["08:00", "12:00", "19:00", "21:00"],
        "cultura": "emotivo, direto, usa gírias, emojis frequentes, storytelling pessoal",
        "moeda": "BRL",
        "hashtag_style": "portugues_brasil",
    },
    "AR": {
        "nome": "Argentina",
        "idioma": "Español (AR)",
        "gtts_lang": "es",
        "fuso": "America/Argentina/Buenos_Aires",
        "plataformas_top": ["instagram", "tiktok", "twitter", "youtube", "facebook"],
        "horarios_post": ["09:00", "13:00", "20:00", "22:00"],
        "cultura": "apaixonado, cultural, referências locais, humor portenho",
        "moeda": "ARS",
        "hashtag_style": "español_latino",
    },
    "MX": {
        "nome": "México",
        "idioma": "Español (MX)",
        "gtts_lang": "es",
        "fuso": "America/Mexico_City",
        "plataformas_top": ["tiktok", "instagram", "facebook", "youtube", "twitter"],
        "horarios_post": ["08:00", "13:00", "19:00", "21:00"],
        "cultura": "festivo, familiar, orgulho cultural, humor mexicano",
        "moeda": "MXN",
        "hashtag_style": "español_mexico",
    },
    "CO": {
        "nome": "Colômbia",
        "idioma": "Español (CO)",
        "gtts_lang": "es",
        "fuso": "America/Bogota",
        "plataformas_top": ["instagram", "tiktok", "facebook", "youtube"],
        "horarios_post": ["08:00", "12:00", "19:00"],
        "cultura": "alegre, musical, regional, empreendedor",
        "moeda": "COP",
        "hashtag_style": "español_latino",
    },
    "CL": {
        "nome": "Chile",
        "idioma": "Español (CL)",
        "gtts_lang": "es",
        "fuso": "America/Santiago",
        "plataformas_top": ["instagram", "tiktok", "twitter", "youtube"],
        "horarios_post": ["08:00", "13:00", "20:00"],
        "cultura": "formal, aspiracional, tech-friendly",
        "moeda": "CLP",
        "hashtag_style": "español_latino",
    },

    # ── América do Norte ────────────────────────────────────────────────────
    "US": {
        "nome": "Estados Unidos",
        "idioma": "English (US)",
        "gtts_lang": "en",
        "fuso": "America/New_York",
        "plataformas_top": ["instagram", "tiktok", "youtube", "twitter", "linkedin", "facebook"],
        "horarios_post": ["07:00", "12:00", "17:00", "20:00"],
        "cultura": "motivacional, aspiracional, direto ao ponto, storytelling de sucesso",
        "moeda": "USD",
        "hashtag_style": "english_us",
    },
    "CA": {
        "nome": "Canadá",
        "idioma": "English (CA)",
        "gtts_lang": "en",
        "fuso": "America/Toronto",
        "plataformas_top": ["instagram", "tiktok", "youtube", "linkedin"],
        "horarios_post": ["07:00", "12:00", "18:00"],
        "cultura": "inclusivo, multicultural, profissional, amigável",
        "moeda": "CAD",
        "hashtag_style": "english_us",
    },

    # ── Europa ──────────────────────────────────────────────────────────────
    "PT": {
        "nome": "Portugal",
        "idioma": "Português (PT)",
        "gtts_lang": "pt",
        "fuso": "Europe/Lisbon",
        "plataformas_top": ["instagram", "facebook", "youtube", "tiktok", "linkedin"],
        "horarios_post": ["08:00", "13:00", "19:00", "21:00"],
        "cultura": "saudosista, autêntico, criativo, ligado à tradição",
        "moeda": "EUR",
        "hashtag_style": "portugues_pt",
    },
    "ES": {
        "nome": "Espanha",
        "idioma": "Español (ES)",
        "gtts_lang": "es",
        "fuso": "Europe/Madrid",
        "plataformas_top": ["instagram", "tiktok", "youtube", "twitter", "facebook"],
        "horarios_post": ["09:00", "14:00", "20:00", "22:00"],
        "cultura": "vibrante, social, humor, gastronomia, lifestyle",
        "moeda": "EUR",
        "hashtag_style": "español_españa",
    },
    "FR": {
        "nome": "França",
        "idioma": "Français",
        "gtts_lang": "fr",
        "fuso": "Europe/Paris",
        "plataformas_top": ["instagram", "tiktok", "youtube", "linkedin", "twitter"],
        "horarios_post": ["08:00", "12:00", "18:00", "20:00"],
        "cultura": "elegante, intelectual, moda, arte, culinária",
        "moeda": "EUR",
        "hashtag_style": "francais",
    },
    "DE": {
        "nome": "Alemanha",
        "idioma": "Deutsch",
        "gtts_lang": "de",
        "fuso": "Europe/Berlin",
        "plataformas_top": ["instagram", "youtube", "linkedin", "tiktok", "twitter"],
        "horarios_post": ["07:00", "12:00", "18:00"],
        "cultura": "preciso, técnico, qualidade, eficiência, confiável",
        "moeda": "EUR",
        "hashtag_style": "deutsch",
    },
    "IT": {
        "nome": "Itália",
        "idioma": "Italiano",
        "gtts_lang": "it",
        "fuso": "Europe/Rome",
        "plataformas_top": ["instagram", "tiktok", "youtube", "facebook"],
        "horarios_post": ["08:00", "13:00", "19:00", "21:00"],
        "cultura": "passional, estético, moda, gastronomia, arte",
        "moeda": "EUR",
        "hashtag_style": "italiano",
    },
    "GB": {
        "nome": "Reino Unido",
        "idioma": "English (UK)",
        "gtts_lang": "en-uk",
        "fuso": "Europe/London",
        "plataformas_top": ["instagram", "tiktok", "youtube", "twitter", "linkedin"],
        "horarios_post": ["07:00", "12:00", "17:00", "20:00"],
        "cultura": "humor seco, criativo, profissional, storytelling",
        "moeda": "GBP",
        "hashtag_style": "english_uk",
    },

    # ── Ásia ────────────────────────────────────────────────────────────────
    "JP": {
        "nome": "Japão",
        "idioma": "Japanese",
        "gtts_lang": "ja",
        "fuso": "Asia/Tokyo",
        "plataformas_top": ["instagram", "twitter", "tiktok", "youtube", "line"],
        "horarios_post": ["07:00", "12:00", "19:00", "21:00"],
        "cultura": "preciso, kawaii, estético, minimal, respeito",
        "moeda": "JPY",
        "hashtag_style": "japanese",
    },
    "KR": {
        "nome": "Coreia do Sul",
        "idioma": "Korean",
        "gtts_lang": "ko",
        "fuso": "Asia/Seoul",
        "plataformas_top": ["instagram", "tiktok", "youtube", "twitter", "kakao"],
        "horarios_post": ["07:00", "12:00", "19:00", "22:00"],
        "cultura": "K-pop, trends, beleza, tecnologia, viral",
        "moeda": "KRW",
        "hashtag_style": "korean",
    },
    "IN": {
        "nome": "Índia",
        "idioma": "Hindi / English",
        "gtts_lang": "hi",
        "fuso": "Asia/Kolkata",
        "plataformas_top": ["instagram", "youtube", "facebook", "tiktok", "twitter"],
        "horarios_post": ["08:00", "13:00", "19:00", "21:00"],
        "cultura": "diverso, familiar, espiritualidade, Bollywood, empreendedorismo",
        "moeda": "INR",
        "hashtag_style": "hindi_english",
    },
    "CN": {
        "nome": "China",
        "idioma": "Mandarin",
        "gtts_lang": "zh-CN",
        "fuso": "Asia/Shanghai",
        "plataformas_top": ["douyin", "weibo", "wechat", "xiaohongshu", "bilibili"],
        "horarios_post": ["07:00", "12:00", "19:00", "21:00"],
        "cultura": "aspiracional, consumo, tecnologia, trabalho duro, família",
        "moeda": "CNY",
        "hashtag_style": "mandarin",
    },
    "AE": {
        "nome": "Emirados Árabes",
        "idioma": "Arabic",
        "gtts_lang": "ar",
        "fuso": "Asia/Dubai",
        "plataformas_top": ["instagram", "tiktok", "snapchat", "youtube", "twitter"],
        "horarios_post": ["09:00", "13:00", "20:00", "22:00"],
        "cultura": "luxo, lifestyle, hospitalidade, modernidade, empreendedorismo",
        "moeda": "AED",
        "hashtag_style": "arabic",
    },

    # ── África ──────────────────────────────────────────────────────────────
    "NG": {
        "nome": "Nigéria",
        "idioma": "English (NG)",
        "gtts_lang": "en",
        "fuso": "Africa/Lagos",
        "plataformas_top": ["instagram", "tiktok", "twitter", "youtube", "facebook"],
        "horarios_post": ["08:00", "13:00", "19:00", "21:00"],
        "cultura": "Afrobeats, humor, Nollywood, hustler spirit, vibrant",
        "moeda": "NGN",
        "hashtag_style": "english_africa",
    },
    "ZA": {
        "nome": "África do Sul",
        "idioma": "English (ZA)",
        "gtts_lang": "en",
        "fuso": "Africa/Johannesburg",
        "plataformas_top": ["instagram", "tiktok", "facebook", "twitter", "youtube"],
        "horarios_post": ["07:00", "12:00", "18:00", "20:00"],
        "cultura": "diverso, ubuntu, aventura, natureza, lifestyle",
        "moeda": "ZAR",
        "hashtag_style": "english_africa",
    },

    # ── Oceania ─────────────────────────────────────────────────────────────
    "AU": {
        "nome": "Austrália",
        "idioma": "English (AU)",
        "gtts_lang": "en-au",
        "fuso": "Australia/Sydney",
        "plataformas_top": ["instagram", "tiktok", "youtube", "linkedin", "facebook"],
        "horarios_post": ["07:00", "12:00", "17:00", "20:00"],
        "cultura": "descontraído, outdoor, lifestyle, humor, sustentabilidade",
        "moeda": "AUD",
        "hashtag_style": "english_au",
    },
}

def get_country(code: str) -> dict:
    """Retorna config do país. Fallback para EN se não encontrado."""
    code = code.upper()
    return COUNTRIES.get(code, COUNTRIES["US"])

def list_countries() -> list:
    return [{"code": k, "nome": v["nome"], "idioma": v["idioma"]} for k, v in COUNTRIES.items()]

def get_gtts_lang(country_code: str) -> str:
    return get_country(country_code).get("gtts_lang", "en")

def get_best_posting_times(country_code: str) -> list:
    return get_country(country_code).get("horarios_post", ["08:00", "12:00", "19:00"])

def get_top_platforms(country_code: str) -> list:
    return get_country(country_code).get("plataformas_top", ["instagram", "tiktok", "youtube"])

def get_culture_prompt(country_code: str) -> str:
    c = get_country(country_code)
    return (
        f"País: {c['nome']} | Idioma: {c['idioma']} | "
        f"Cultura: {c['cultura']} | "
        f"Plataformas top: {', '.join(c['plataformas_top'][:3])}"
    )
