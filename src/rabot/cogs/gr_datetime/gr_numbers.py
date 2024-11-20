# https://github.com/savoirfairelinux/num2words doesn't support greek

units = ["", "ένα", "δύο", "τρία", "τέσσερα", "πέντε", "έξι", "επτά", "οκτώ", "εννέα"]
tens = [
    "",
    "δέκα",
    "είκοσι",
    "τριάντα",
    "σαράντα",
    "πενήντα",
    "εξήντα",
    "εβδομήντα",
    "ογδόντα",
    "ενενήντα",
]
teens = [
    "",
    "έντεκα",
    "δώδεκα",
    "δεκατρία",
    "δεκατέσσερα",
    "δεκαπέντε",
    "δεκαέξι",
    "δεκαεπτά",
    "δεκαοκτώ",
    "δεκαεννέα",
]
hundreds = [
    "",
    "εκατόν",
    "διακόσια",
    "τριακόσια",
    "τετρακόσια",
    "πεντακόσια",
    "εξακόσια",
    "επτακόσια",
    "οκτακόσια",
    "εννιακόσια",
]
thousands_sing = ["", "χίλια", "εκατομμύριο"]
thousands_plur = ["", "χιλιάδες", "εκατομμύρια"]


def num2word(n: int) -> str:
    if n == 0:
        return "μηδέν"

    if n < 0:
        return f"μείον {num2word(-n)}"

    words: list[str] = []
    groups_count = 0

    while n > 0:
        group = n % 1000
        group_words = process_group(group)

        if group_words:
            term = thousands_sing[groups_count] if group == 1 else thousands_plur[groups_count]
            words.append(f"{group_words} {term}")

        n //= 1000
        groups_count += 1

    out = " ".join(reversed(words))
    # Temporary fix
    out = out.replace("ένα χίλια", "χίλια")

    return out.strip()


def process_group(group: int) -> str:
    if group == 0:
        return ""

    group_words: list[str] = []
    hundreds_digit = group // 100
    tens_digit = (group % 100) // 10
    units_digit = group % 10

    if hundreds_digit > 0:
        group_words.append(hundreds[hundreds_digit])

    if tens_digit > 1:
        group_words.append(tens[tens_digit])

        if units_digit > 0:
            group_words.append(units[units_digit])

    elif tens_digit == 1:
        if units_digit > 0:
            group_words.append(teens[units_digit])
        else:
            group_words.append(tens[tens_digit])

    elif units_digit > 0:
        group_words.append(units[units_digit])

    return " ".join(group_words)


if __name__ == "__main__":
    assert num2word(0) == "μηδέν"
    assert num2word(1) == "ένα"
