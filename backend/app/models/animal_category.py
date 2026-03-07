"""
Taurus Vision — Animal Category Model

Jonivor kategoriyalari: tur va maqsadiga qarab tasniflanadi.
Kategoriyani qo'shishda va keyinchalik o'zgartirishda ishlatiladi.

Kategoriya tur bo'yicha:
    CATTLE: buzoq → sut_uchun | gosht_uchun | nasl_uchun | ishchi
    SHEEP:  qo'zichoq → gosht_uchun | nasl_uchun | jun_uchun
    GOAT:   uloqcha → sut_uchun | gosht_uchun | nasl_uchun
    HORSE:  toy → ish_oti | sport | nasl_uchun
"""

import enum


class AnimalCategory(str, enum.Enum):
    """
    Jonivor kategoriyasi — tur va foydalanish maqsadiga qarab.

    YOSH kategoriyalari (keyinchalik o'zgartiriladi):
        BUZOQ      — Qoramol bolasi (< 6 oy)
        QOZICHOQ   — Qo'y bolasi (< 4 oy)
        ULOQCHA    — Echki bolasi (< 4 oy)
        TOY        — Ot bolasi (< 1 yil)

    ASOSIY kategoriyalar (barcha turlarga mos):
        SUT_UCHUN  — Sut ishlab chiqarish
        GOSHT_UCHUN — Go'sht uchun boqilmoqda
        NASL_UCHUN  — Naslchilik, zot yaxshilash
        ISHCHI      — Mehnat (ot, ho'kiz)
        JUN_UCHUN   — Jun/tola uchun (qo'y, echki)
        BOSHQA      — Boshqa maqsad
    """

    # Yoshlar
    BUZOQ     = "buzoq"      # Calf  — qoramol
    QOZICHOQ  = "qo'zichoq"  # Lamb  — qo'y
    ULOQCHA   = "uloqcha"    # Kid   — echki
    TOY       = "toy"        # Foal  — ot

    # Asosiy maqsad
    SUT_UCHUN   = "sut_uchun"    # Dairy
    GOSHT_UCHUN = "gosht_uchun"  # Meat
    NASL_UCHUN  = "nasl_uchun"   # Breeding
    ISHCHI      = "ishchi"       # Work / Draft
    JUN_UCHUN   = "jun_uchun"    # Wool / Fiber
    BOSHQA      = "boshqa"       # Other


# Tur bo'yicha tavsiya etilgan kategoriyalar (frontend uchun)
SPECIES_CATEGORIES: dict[str, list[str]] = {
    "cattle": [
        "buzoq", "sut_uchun", "gosht_uchun", "nasl_uchun", "ishchi", "boshqa"
    ],
    "sheep": [
        "qo'zichoq", "gosht_uchun", "nasl_uchun", "jun_uchun", "boshqa"
    ],
    "goat": [
        "uloqcha", "sut_uchun", "gosht_uchun", "nasl_uchun", "jun_uchun", "boshqa"
    ],
    "horse": [
        "toy", "nasl_uchun", "ishchi", "boshqa"
    ],
    "other": [
        "gosht_uchun", "nasl_uchun", "boshqa"
    ],
}

# O'zbekcha yorliqlar (frontend uchun)
CATEGORY_LABELS: dict[str, str] = {
    "buzoq":      "Buzoq (< 6 oy)",
    "qo'zichoq":  "Qo'zichoq (< 4 oy)",
    "uloqcha":    "Uloqcha (< 4 oy)",
    "toy":        "Toy (< 1 yil)",
    "sut_uchun":  "Sut uchun",
    "gosht_uchun":"Go'sht uchun",
    "nasl_uchun": "Nasl uchun",
    "ishchi":     "Ishchi / Mehnat",
    "jun_uchun":  "Jun / Tola uchun",
    "boshqa":     "Boshqa",
}