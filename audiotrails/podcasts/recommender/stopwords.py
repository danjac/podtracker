from typing import Dict, List

"""Additional language-specific stopwords"""

ENGLISH_DAYS: List[str] = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
]

ENGLISH_NUMBERS: List[str] = [
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
]

ENGLISH_MONTHS: List[str] = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]

ENGLISH_MISC_WORDS: List[str] = [
    "across",
    "advice",
    "along",
    "also",
    "always",
    "answer",
    "around",
    "audio",
    "available",
    "back",
    "become",
    "behind",
    "best",
    "better",
    "beyond",
    "big",
    "biggest",
    "bring",
    "brings",
    "change",
    "channel",
    "city",
    "come",
    "content",
    "conversation",
    "course",
    "daily",
    "date",
    "day",
    "days",
    "different",
    "discussion",
    "dont",
    "dr",
    "end",
    "enjoy",
    "episode",
    "episodes",
    "even",
    "ever",
    "every",
    "everyone",
    "everything",
    "favorite",
    "feature",
    "featuring",
    "feed",
    "field",
    "find",
    "first",
    "focus",
    "follow",
    "full",
    "fun",
    "get",
    "give",
    "go",
    "going",
    "good",
    "gmt",
    "great",
    "guest",
    "happen",
    "happening",
    "hear",
    "host",
    "hosted",
    "hour",
    "idea",
    "impact",
    "important",
    "including",
    "information",
    "inside",
    "insight",
    "interesting",
    "interview",
    "issue",
    "join",
    "journalist",
    "keep",
    "know",
    "knowledge",
    "known",
    "latest",
    "leading",
    "learn",
    "let",
    "life",
    "like",
    "listen",
    "listener",
    "little",
    "live",
    "look",
    "looking",
    "made",
    "make",
    "making",
    "many",
    "matter",
    "medium",
    "member",
    "minute",
    "moment",
    "month",
    "mr",
    "mrs",
    "ms",
    "much",
    "name",
    "need",
    "never",
    "new",
    "news",
    "next",
    "night",
    "offer",
    "open",
    "original",
    "other",
    "others",
    "part",
    "past",
    "people",
    "personal",
    "perspective",
    "place",
    "podcast",
    "podcasts",
    "premium",
    "present",
    "problem",
    "produced",
    "producer",
    "product",
    "production",
    "question",
    "radio",
    "read",
    "real",
    "really",
    "review",
    "right",
    "scene",
    "season",
    "see",
    "series",
    "set",
    "share",
    "short",
    "show",
    "shows",
    "side",
    "sign",
    "sir",
    "small",
    "something",
    "sometimes",
    "sound",
    "special",
    "sponsor",
    "start",
    "stories",
    "story",
    "subscribe",
    "support",
    "take",
    "tale",
    "talk",
    "talking",
    "team",
    "tell",
    "thing",
    "think",
    "thought",
    "time",
    "tip",
    "today",
    "together",
    "top",
    "topic",
    "training",
    "true",
    "truth",
    "understand",
    "unique",
    "use",
    "ustream",
    "video",
    "visit",
    "voice",
    "want",
    "way",
    "week",
    "weekly",
    "welcome",
    "well",
    "were",
    "what",
    "word",
    "work",
    "world",
    "would",
    "year",
    "years",
    "youll",
    "youre",
]

CORPORATES: List[str] = [
    "apple",
    "patreon",
    "spotify",
    "stitcher",
    "itunes",
]

STOPWORDS: Dict[str, List[str]] = {
    "en": ENGLISH_DAYS
    + ENGLISH_MONTHS
    + ENGLISH_NUMBERS
    + ENGLISH_MISC_WORDS
    + CORPORATES
}
