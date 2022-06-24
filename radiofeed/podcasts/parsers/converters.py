from radiofeed.podcasts.parsers import date_parser


def pub_date(value):
    return date_parser.parse_date(value)


def complete(value):
    if value and value.casefold() == "yes":
        return True
    return False


def explicit(value):
    if value and value.casefold() in ("clean", "yes"):
        return True
    return False


def duration(value):
    if not value:
        return ""

    try:
        # plain seconds value
        return str(int(value))
    except ValueError:
        pass

    try:
        return ":".join(
            [
                str(v)
                for v in [int(v) for v in value.split(":")[:3]]
                if v in range(0, 60)
            ]
        )
    except ValueError:
        return ""


def language_code(value):
    return (value or "en")[:2]


def int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
