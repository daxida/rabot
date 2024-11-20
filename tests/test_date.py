from datetime import datetime

from rabot.cogs.gr_datetime.gr_date import get_date, get_full_date, get_hour


def _test_date(dt, expected_d, expected_h):
    d = get_date(dt)
    h = get_hour(dt)
    dh = get_full_date(dt)

    assert d == expected_d
    assert h == expected_h
    assert dh == f"{expected_d} {expected_h}"


def test_date_one():
    dt = datetime(2022, 12, 25, 15, 30)
    expected_d = (
        "Καλημέρα. Σήμερα η μέρα, εδώ που μένω εγώ, "
        "είναι Κυριακή, Είκοσι πέντε (του) Δεκεμβρίου (του έτους) δύο χιλιάδες είκοσι δύο."
    )
    expected_h = "Και η ώρα είναι τρία και τριάντα λεπτά μ.μ.."
    _test_date(dt, expected_d, expected_h)


def test_date_two():
    dt = datetime(1999, 7, 20, 6, 45, 12)
    expected_d = (
        "Καλημέρα. Σήμερα η μέρα, εδώ που μένω εγώ, "
        "είναι Τρίτη, Είκοσι (του) Ιουλίου (του έτους) χίλια εννιακόσια ενενήντα εννέα."
    )
    expected_h = "Και η ώρα είναι έξι και σαράντα πέντε λεπτά π.μ.."
    _test_date(dt, expected_d, expected_h)
