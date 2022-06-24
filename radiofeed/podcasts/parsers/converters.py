from datetime import datetime

from radiofeed.podcasts.parsers import date_parser


def pub_date(value: str) -> datetime | None:
    return date_parser.parse_date(value)


def complete(value: str) -> bool:
    if value and value.casefold() == "yes":
        return True
    return False


def explicit(value: str) -> bool:
    if value and value.casefold() in ("clean", "yes"):
        return True
    return False


def duration(value: str) -> str:
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


def language_code(value: str) -> str:
    return (value or "en")[:2]


def int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
