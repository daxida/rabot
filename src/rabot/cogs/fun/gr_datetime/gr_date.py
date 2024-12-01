from datetime import datetime

from rabot.cogs.fun.gr_datetime.gr_numbers import num2word

DAYS_NOMINATIVE = [
    "Δευτέρα",
    "Τρίτη",
    "Τετάρτη",
    "Πέμπτη",
    "Παρασκευή",
    "Σάββατο",
    "Κυριακή",
]

MONTHS_GENITIVE = [
    "Ιανουαρίου",
    "Φεβρουαρίου",
    "Μαρτίου",
    "Απριλίου",
    "Μαΐου",
    "Ιουνίου",
    "Ιουλίου",
    "Αυγούστου",
    "Σεπτεμβρίου",
    "Οκτωβρίου",
    "Νοεμβρίου",
    "Δεκεμβρίου",
]


def get_full_date(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return f"{get_date(dt)} {get_hour(dt)}"


def get_date(dt: datetime) -> str:
    wd = dt.weekday()
    d, m, y = dt.day, dt.month, dt.year

    str_wd = DAYS_NOMINATIVE[wd]
    str_d = num2word(d).capitalize()
    str_d = str_d.replace("σσερα", "σσερις")
    str_m = MONTHS_GENITIVE[m - 1]
    str_y = num2word(y)

    fdate = (
        "Καλημέρα. Σήμερα η μέρα, εδώ που μένω εγώ, "
        f"είναι {str_wd}, {str_d} (του) {str_m} (του έτους) {str_y}."
    )

    return fdate


def get_hour(dt: datetime) -> str:
    h, m = dt.hour, dt.minute

    pm = h > 12
    h %= 12

    str_m = num2word(m)
    str_h = num2word(h)
    str_h = str_h.replace("ένα", "μία")

    fhour = f"Και η ώρα είναι {str_h}"
    if m > 0:
        fhour += f" και {str_m} λεπτά"
    fhour += " μ.μ." if pm else " π.μ."
    fhour += "."

    return fhour
