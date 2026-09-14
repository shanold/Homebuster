from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Iterable, Mapping


# Product catalog titles are not movie titles.  This module deliberately
# recognizes only metadata with strong positional/context signals so words
# that happen to be language/studio terms inside a real title survive.

_FORMAT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"4K(?:\s+Ultra\s+HD|\s+UHD)?|Ultra\s+HD|UHD", re.I), "4K UHD"),
    (re.compile(r"Blue?[- ]?ray", re.I), "Blu-ray"),
    (re.compile(r"HD[- ]?DVD", re.I), "HD DVD"),
    (re.compile(r"DVD", re.I), "DVD"),
    (re.compile(r"VHS", re.I), "VHS"),
)

_EDITION_PATTERN = re.compile(
    r"(?:(?:\d+)[- ]Disc\s+)?(?:"
    r"Special(?:\s+Collector'?s?)?\s+Edition|Collector'?s?\s+Edition|Limited\s+Edition|"
    r"Anniversary\s+Edition|Deluxe\s+Edition|Ultimate\s+Edition|Platinum\s+Edition|"
    r"Diamond\s+Edition|Signature\s+Collection|Criterion\s+Collection|"
    r"Extended(?:\s+(?:Edition|Cut))?|Director'?s\s+Cut|Theatrical\s+Cut|Final\s+Cut|"
    r"Unrated(?:\s+Edition)?|Uncut(?:\s+Edition)?|Remastered(?:\s+Edition)?|"
    r"Restored(?:\s+Edition)?|SteelBook|Widescreen|Full\s+Screen"
    r")",
    re.I,
)

_DISC_COUNT_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_DISC_PATTERN = re.compile(
    r"(?P<count>\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    r"[- ]?(?:Disc|Disk)s?(?:\s+(?:Set|Collection))?",
    re.I,
)


def _disc_count(match: re.Match[str]) -> int:
    token = match.group("count").lower()
    return int(token) if token.isdigit() else _DISC_COUNT_WORDS[token]

_TV_SET_SUFFIX_PATTERN = re.compile(
    r"(?:\s*[-–—,:;|]\s*|\s+)(?P<edition>(?:"
    r"(?:The\s+)?Complete\s+(?:(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth|\d{1,2}(?:st|nd|rd|th)?)\s+Season|Series)(?:\s+Box\s*Set)?|"
    r"Season\s+(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)(?:\s*[-–]\s*(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve))?(?:\s+(?:Collection|Box\s*Set))?|"
    r"Seasons\s+(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)\s*[-–]\s*(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)(?:\s+(?:Collection|Box\s*Set))?|"
    r"Series\s+(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)(?:\s*[-–]\s*(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve))?(?:\s+(?:Collection|Box\s*Set))?|"
    r"Complete\s+Series(?:\s+(?:Collection|Box\s*Set))?|"
    r"Complete\s+Collection(?:\s+Box\s*Set)?|"
    r"Box\s*Set|"
    r"Collection"
    r"))\s*$",
    re.I,
)


def _tv_set_suffix(value: str) -> re.Match[str] | None:
    match = _TV_SET_SUFFIX_PATTERN.search(_normalize_spaces(value))
    if not match:
        return None
    # Do not reinterpret a standalone title such as "The Collection" as copy metadata.
    title_part = _strip_outer_separators(_normalize_spaces(value)[:match.start()])
    if not title_part or title_part.casefold() in {"the", "a", "an"}:
        return None
    return match


def _tv_set_search_title(value: str) -> str:
    match = _tv_set_suffix(value)
    if not match:
        return _normalize_spaces(value)
    return _strip_outer_separators(_normalize_spaces(value)[:match.start()])


def _tv_set_edition(value: str) -> str | None:
    match = _tv_set_suffix(value)
    return _normalize_spaces(match.group("edition")) if match else None

_TV_SET_EDITION_PATTERN = re.compile(
    r"(?P<edition>(?:"
    r"(?:The\s+)?Complete\s+(?:(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth|\d{1,2}(?:st|nd|rd|th)?)\s+Season|Series)(?:\s+Box\s*Set)?|"
    r"Season\s+(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)(?:\s*[-–]\s*(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve))?(?:\s+(?:Collection|Box\s*Set))?|"
    r"Seasons\s+(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)\s*[-–]\s*(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)(?:\s+(?:Collection|Box\s*Set))?|"
    r"Series\s+(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)(?:\s*[-–]\s*(?:\d{1,2}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve))?(?:\s+(?:Collection|Box\s*Set))?|"
    r"Complete\s+Series(?:\s+(?:Collection|Box\s*Set))?|"
    r"Complete\s+Collection(?:\s+Box\s*Set)?|"
    r"Box\s*Set|Collection"
    r"))", re.I,
)


def _tv_set_edition_from_leftover(value: str) -> str | None:
    cleaned = _normalize_spaces(value)
    for pattern, _ in _FORMAT_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = _DISC_PATTERN.sub(" ", cleaned)
    cleaned = _REGION_PATTERN.sub(" ", cleaned)
    cleaned = _PACKAGING_PATTERN.sub(" ", cleaned)
    cleaned = _VIDEO_STANDARD_PATTERN.sub(" ", cleaned)
    cleaned = _CATALOG_CATEGORY_PATTERN.sub(" ", cleaned) if '_CATALOG_CATEGORY_PATTERN' in globals() else cleaned
    cleaned = _normalize_spaces(cleaned)
    match = _TV_SET_EDITION_PATTERN.search(cleaned)
    return _normalize_spaces(match.group("edition")) if match else None

_REGION_PATTERN = re.compile(
    r"(?:Region\s*(?P<region>[1-8ABC])|(?P<free>Region[- ]?Free|All\s+Regions?))",
    re.I,
)
_VIDEO_STANDARD_PATTERN = re.compile(r"(?:NTSC|PAL)", re.I)
_PACKAGING_PATTERN = re.compile(
    r"(?:Digital\s+Copy|Includes?\s+Digital(?:\s+Copy)?|Combo\s+Pack|"
    r"Blu[- ]?ray\s*\+\s*Digital|DVD\s*\+\s*Digital)",
    re.I,
)
_YEAR_PATTERN = re.compile(r"(?:19|20)\d{2}")

_LANGUAGE_CANONICAL = {
    "english": "English",
    "spanish": "Spanish",
    "french": "French",
    "german": "German",
    "italian": "Italian",
    "portuguese": "Portuguese",
    "japanese": "Japanese",
    "korean": "Korean",
    "chinese": "Chinese",
    "mandarin": "Mandarin",
    "cantonese": "Cantonese",
    "dutch": "Dutch",
    "russian": "Russian",
    "polish": "Polish",
    "arabic": "Arabic",
    "hindi": "Hindi",
    "swedish": "Swedish",
    "norwegian": "Norwegian",
    "danish": "Danish",
    "finnish": "Finnish",
}
_LANGUAGE_WORDS = "|".join(sorted((re.escape(k) for k in _LANGUAGE_CANONICAL), key=len, reverse=True))
_LANGUAGE_SEQUENCE_PATTERN = re.compile(
    rf"(?P<languages>(?:{_LANGUAGE_WORDS})(?:\s*(?:/|\+|&|,)\s*(?:{_LANGUAGE_WORDS}))*)",
    re.I,
)
_LANGUAGE_LABELED_PATTERN = re.compile(
    rf"(?:Languages?|Audio)\s*[:=-]\s*(?P<languages>(?:{_LANGUAGE_WORDS})(?:\s*(?:/|\+|&|,)\s*(?:{_LANGUAGE_WORDS}))*)|"
    rf"(?P<languages_suffix>(?:{_LANGUAGE_WORDS})(?:\s*(?:/|\+|&|,)\s*(?:{_LANGUAGE_WORDS}))*)\s+Languages?",
    re.I,
)

_CATALOG_CATEGORIES = (
    "Action & Adventure",
    "Action and Adventure",
    "Science Fiction & Fantasy",
    "Sci-Fi & Fantasy",
    "Kids & Family",
    "Mystery & Thriller",
    "Music & Musicals",
    "Anime & Animation",
    "Animation",
    "Comedy",
    "Drama",
    "Horror",
    "Documentary",
    "Romance",
    "Western",
    "Sports",
)
_CATALOG_CATEGORY_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(value) for value in sorted(_CATALOG_CATEGORIES, key=len, reverse=True)) + r")",
    re.I,
)

_KNOWN_DISTRIBUTORS = (
    "Sony Pictures Home Entertainment",
    "Sony Pictures",
    "Warner Bros. Home Entertainment",
    "Warner Bros Home Entertainment",
    "Warner Home Video",
    "Universal Studios Home Entertainment",
    "Universal Pictures Home Entertainment",
    "Paramount Home Entertainment",
    "Buena Vista Home Entertainment",
    "Walt Disney Studios Home Entertainment",
    "20th Century Fox Home Entertainment",
    "Twentieth Century Fox Home Entertainment",
    "MGM Home Entertainment",
    "Lionsgate Home Entertainment",
    "Lions Gate Home Entertainment",
    "Shout! Factory",
    "Shout Factory",
)


@dataclass(frozen=True)
class BarcodeParseResult:
    raw_title: str
    title: str
    fallback_title: str
    year: int | None = None
    formats: tuple[str, ...] = ()
    language: str | None = None
    edition: str | None = None
    region: str | None = None
    disc_count: int | None = None
    distributor: str | None = None
    category: str | None = None

    @property
    def format(self) -> str | None:
        return " + ".join(self.formats) if self.formats else None

    def as_dict(self) -> dict:
        return {
            "raw_title": self.raw_title,
            "title": self.title,
            "fallback_title": self.fallback_title,
            "year": self.year,
            "formats": list(self.formats),
            "format": self.format,
            "language": self.language,
            "edition": self.edition,
            "region": self.region,
            "disc_count": self.disc_count,
            "distributor": self.distributor,
            "category": self.category,
        }


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _canonical_format(value: str) -> str | None:
    value = _normalize_spaces(value)
    for pattern, canonical in _FORMAT_PATTERNS:
        if pattern.fullmatch(value):
            return canonical
    return None


def _canonical_format_sequence(value: str) -> tuple[str, ...]:
    parts = re.split(r"\s*(?:/|\+|&)\s*", _normalize_spaces(value))
    if not parts:
        return ()
    formats: list[str] = []
    for part in parts:
        canonical = _canonical_format(part)
        if not canonical:
            return ()
        if canonical not in formats:
            formats.append(canonical)
    return tuple(formats)


def _canonical_languages(value: str) -> str | None:
    match = _LANGUAGE_SEQUENCE_PATTERN.fullmatch(_normalize_spaces(value))
    if not match:
        return None
    names = re.split(r"\s*(?:/|\+|&|,)\s*", match.group("languages"))
    canonical: list[str] = []
    for name in names:
        item = _LANGUAGE_CANONICAL.get(name.lower())
        if item and item not in canonical:
            canonical.append(item)
    return " + ".join(canonical) if canonical else None


def _canonical_labeled_languages(value: str) -> str | None:
    match = _LANGUAGE_LABELED_PATTERN.fullmatch(_normalize_spaces(value))
    if not match:
        return None
    return _canonical_languages(match.group("languages") or match.group("languages_suffix") or "")


def _bare_language_suffix_is_metadata(value: str, match: re.Match[str], raw: str) -> bool:
    text = _normalize_spaces(match.group(0))
    # Multiple languages are overwhelmingly catalog metadata.
    if re.search(r"[/+&,]", text):
        return True
    prefix = _strip_outer_separators(value[:match.start()])
    # A single bare language is only trusted when product context appears
    # before it in the original catalog title.  This lets "DVD English"
    # parse as metadata while protecting "Johnny English DVD".
    language_text = _normalize_spaces(match.group(0))
    occurrences = list(re.finditer(rf"(?<![A-Za-z]){re.escape(language_text)}(?![A-Za-z])", raw, re.I))
    language_pos = occurrences[-1].start() if occurrences else None
    if language_pos is not None:
        for pattern, _ in _FORMAT_PATTERNS:
            if any(fmt.end() <= language_pos for fmt in pattern.finditer(raw)):
                return True
        if any(region.end() <= language_pos for region in _REGION_PATTERN.finditer(raw)):
            return True
        if any(pack.end() <= language_pos for pack in _PACKAGING_PATTERN.finditer(raw)):
            return True
    # Also accept a still-visible product token immediately before it.
    for pattern, _ in _FORMAT_PATTERNS:
        if _suffix_match(prefix, pattern):
            return True
    return bool(_suffix_match(prefix, _PACKAGING_PATTERN) or _suffix_match(prefix, _REGION_PATTERN))


def _canonical_region(value: str) -> str | None:
    match = _REGION_PATTERN.fullmatch(_normalize_spaces(value))
    if not match:
        return None
    if match.group("free"):
        return "Region Free"
    token = match.group("region").upper()
    return f"Region {token}"


def _strip_outer_separators(value: str) -> str:
    return _normalize_spaces(value).strip(" -–—:;+/,|")


def _suffix_match(value: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    # Require the metadata to be a suffix separated from the movie text. This
    # is what prevents e.g. "The English Patient" from becoming "The Patient".
    match = pattern.search(value)
    if not match or match.end() != len(value):
        return None
    if match.start() == 0:
        return match
    before = value[match.start() - 1]
    if before.isspace() or before in "-–—:;+/|([":
        return match
    return None


def _strip_known_distributor_suffix(value: str, hint: str | None) -> tuple[str, str | None]:
    candidates: list[str] = []
    if hint and _normalize_spaces(hint):
        candidates.append(_normalize_spaces(hint))
    candidates.extend(_KNOWN_DISTRIBUTORS)
    # Longest first avoids "Warner Home Video" fragments winning over a
    # longer hint supplied by the barcode provider.
    for distributor in sorted(dict.fromkeys(candidates), key=len, reverse=True):
        match = re.search(rf"(?:\s*[-–—:;|]\s*|\s+){re.escape(distributor)}\s*$", value, re.I)
        if match:
            return _strip_outer_separators(value[: match.start()]), distributor
    return value, None


def _strip_bracketed_metadata(
    value: str,
    formats: list[str],
    languages: list[str],
    editions: list[str],
    state: dict,
) -> str:
    bracket_re = re.compile(r"[\[(]([^\[\]()]{1,100})[\])]")

    def replace(match: re.Match[str]) -> str:
        content = _normalize_spaces(match.group(1))
        format_sequence = _canonical_format_sequence(content)
        if format_sequence:
            for fmt in format_sequence:
                if fmt not in formats:
                    formats.append(fmt)
            return " "
        lang = _canonical_languages(content) or _canonical_labeled_languages(content)
        if lang:
            for item in lang.split(" + "):
                if item not in languages:
                    languages.append(item)
            return " "
        region = _canonical_region(content)
        if region:
            state["region"] = state.get("region") or region
            return " "
        disc = _DISC_PATTERN.fullmatch(content)
        if disc:
            state["disc_count"] = state.get("disc_count") or _disc_count(disc)
            return " "
        if _EDITION_PATTERN.fullmatch(content):
            edition = _normalize_spaces(content)
            if edition not in editions:
                editions.append(edition)
            return " "
        if _VIDEO_STANDARD_PATTERN.fullmatch(content) or _PACKAGING_PATTERN.fullmatch(content):
            return " "
        year = _YEAR_PATTERN.fullmatch(content)
        if year:
            candidate = int(year.group(0))
            if 1900 <= candidate <= datetime.now().year + 1:
                state["year"] = state.get("year") or candidate
                return " "
        return match.group(0)

    return _normalize_spaces(bracket_re.sub(replace, value))


def _strip_safe_metadata(raw: str) -> str:
    """Less aggressive title used only as a TMDb fallback.

    It intentionally does not remove language or distributor phrases.
    """
    value = _normalize_spaces(raw)
    dummy_formats: list[str] = []
    dummy_languages: list[str] = []
    dummy_editions: list[str] = []
    state: dict = {}
    value = _strip_bracketed_metadata(value, dummy_formats, dummy_languages, dummy_editions, state)
    previous = None
    while value != previous:
        previous = value
        year = _suffix_match(value, _YEAR_PATTERN)
        if year:
            candidate = int(year.group(0))
            if 1900 <= candidate <= datetime.now().year + 1:
                value = _strip_outer_separators(value[:year.start()])
                continue
        for pattern, _ in _FORMAT_PATTERNS:
            match = _suffix_match(value, pattern)
            if match:
                value = _strip_outer_separators(value[:match.start()])
                break
        else:
            match = _suffix_match(value, _EDITION_PATTERN)
            if match:
                value = _strip_outer_separators(value[:match.start()])
                continue
            match = _suffix_match(value, _DISC_PATTERN)
            if match:
                value = _strip_outer_separators(value[:match.start()])
                continue
            match = _suffix_match(value, _REGION_PATTERN)
            if match:
                value = _strip_outer_separators(value[:match.start()])
                continue
            match = _suffix_match(value, _VIDEO_STANDARD_PATTERN)
            if match:
                value = _strip_outer_separators(value[:match.start()])
                continue
            match = _suffix_match(value, _PACKAGING_PATTERN)
            if match:
                value = _strip_outer_separators(value[:match.start()])
                continue
            break
    return _strip_outer_separators(value) or _normalize_spaces(raw)


def parse_barcode_product_title(raw_title: str, distributor_hint: str | None = None) -> BarcodeParseResult:
    raw = _normalize_spaces(raw_title)
    if not raw:
        return BarcodeParseResult(raw_title="", title="", fallback_title="")

    fallback_title = _strip_safe_metadata(raw)
    value = raw
    formats: list[str] = []
    format_order: list[str] = []
    for match in re.finditer(r"4K(?:\s+Ultra\s+HD|\s+UHD)?|Ultra\s+HD|UHD|Blue?[- ]?ray|HD[- ]?DVD|DVD|VHS", raw, re.I):
        canonical = _canonical_format(match.group(0))
        if canonical and canonical not in format_order:
            format_order.append(canonical)
    languages: list[str] = []
    editions: list[str] = []
    state: dict = {"year": None, "region": None, "disc_count": None}
    distributor: str | None = None
    category: str | None = None

    value = _strip_bracketed_metadata(value, formats, languages, editions, state)

    # Peel recognized catalog metadata from right to left.  A store may put
    # these in nearly any order, so removing one can expose the next.
    previous = None
    while value != previous:
        previous = value

        year_match = _suffix_match(value, _YEAR_PATTERN)
        if year_match:
            candidate = int(year_match.group(0))
            if 1900 <= candidate <= datetime.now().year + 1:
                state["year"] = state["year"] or candidate
                value = _strip_outer_separators(value[:year_match.start()])
                continue

        edition_match = _suffix_match(value, _EDITION_PATTERN)
        if edition_match:
            edition = _normalize_spaces(edition_match.group(0))
            # Split disc-count prefix from edition now that Homebuster has a
            # dedicated disc_count field.
            disc_prefix = _DISC_PATTERN.match(edition)
            if disc_prefix:
                state["disc_count"] = state["disc_count"] or _disc_count(disc_prefix)
                edition = _strip_outer_separators(edition[disc_prefix.end():])
            if edition and edition not in editions:
                editions.insert(0, edition)
            value = _strip_outer_separators(value[:edition_match.start()])
            continue

        disc_match = _suffix_match(value, _DISC_PATTERN)
        if disc_match:
            state["disc_count"] = state["disc_count"] or _disc_count(disc_match)
            value = _strip_outer_separators(value[:disc_match.start()])
            continue

        region_match = _suffix_match(value, _REGION_PATTERN)
        if region_match:
            state["region"] = state["region"] or _canonical_region(region_match.group(0))
            value = _strip_outer_separators(value[:region_match.start()])
            continue

        standard_match = _suffix_match(value, _VIDEO_STANDARD_PATTERN)
        if standard_match:
            value = _strip_outer_separators(value[:standard_match.start()])
            continue

        packaging_match = _suffix_match(value, _PACKAGING_PATTERN)
        if packaging_match:
            value = _strip_outer_separators(value[:packaging_match.start()])
            continue

        category_match = _suffix_match(value, _CATALOG_CATEGORY_PATTERN)
        if category_match:
            category = category or _normalize_spaces(category_match.group(0))
            value = _strip_outer_separators(value[:category_match.start()])
            continue

        stripped, found_distributor = _strip_known_distributor_suffix(value, distributor_hint)
        if found_distributor:
            distributor = distributor or found_distributor
            value = stripped
            continue

        labeled_language_match = _suffix_match(value, _LANGUAGE_LABELED_PATTERN)
        if labeled_language_match:
            language = _canonical_labeled_languages(labeled_language_match.group(0))
            if language:
                for item in language.split(" + "):
                    if item not in languages:
                        languages.append(item)
                value = _strip_outer_separators(value[:labeled_language_match.start()])
                continue

        language_match = _suffix_match(value, _LANGUAGE_SEQUENCE_PATTERN)
        if language_match and _bare_language_suffix_is_metadata(value, language_match, raw):
            language = _canonical_languages(language_match.group(0))
            if language:
                for item in language.split(" + "):
                    if item not in languages:
                        languages.append(item)
                value = _strip_outer_separators(value[:language_match.start()])
                continue

        removed_format = False
        for pattern, canonical in _FORMAT_PATTERNS:
            format_match = _suffix_match(value, pattern)
            if format_match:
                if canonical not in formats:
                    formats.append(canonical)
                value = _strip_outer_separators(value[:format_match.start()])
                removed_format = True
                break
        if removed_format:
            continue

    title = _strip_outer_separators(value)
    if not title or title.lower() in {"the", "a", "an"}:
        # Fail safely.  A parser that cannot leave a plausible title should
        # not destroy the provider's text.
        title = raw
        fallback_title = raw
        formats = []
        languages = []
        editions = []
        distributor = None
        category = None
        state = {"year": None, "region": None, "disc_count": None}

    if formats:
        detected = set(formats)
        formats = [fmt for fmt in format_order if fmt in detected] or formats

    return BarcodeParseResult(
        raw_title=raw,
        title=title,
        fallback_title=fallback_title,
        year=state["year"],
        formats=tuple(formats),
        language=" + ".join(languages) if languages else None,
        edition=" ".join(editions) if editions else None,
        region=state["region"],
        disc_count=state["disc_count"],
        distributor=distributor,
        category=category,
    )



def _strip_canonical_title(raw: str, canonical_title: str) -> str:
    """Remove a confirmed movie title from product text, tolerating punctuation/typos."""
    raw = _normalize_spaces(raw)
    canonical = _normalize_spaces(canonical_title)
    if not raw or not canonical:
        return raw

    words = re.findall(r"[A-Za-z0-9]+", canonical)
    if words:
        flexible = r"(?<![A-Za-z0-9])" + r"[^A-Za-z0-9]+".join(re.escape(w) for w in words) + r"(?![A-Za-z0-9])"
        match = re.search(flexible, raw, re.I)
        if match:
            return _strip_outer_separators(raw[:match.start()] + " " + raw[match.end():])

    # A legacy title can contain a small typo (Tale/Tail).  If the beginning
    # of the product description is an overwhelmingly close token match to the
    # TMDb-confirmed title, treat those leading tokens as the title anchor.
    canonical_tokens = re.findall(r"[A-Za-z0-9]+", canonical)
    raw_tokens = list(re.finditer(r"[A-Za-z0-9]+", raw))
    if canonical_tokens and len(raw_tokens) >= len(canonical_tokens):
        candidate = " ".join(m.group(0) for m in raw_tokens[:len(canonical_tokens)])
        if SequenceMatcher(None, _normalized_title(candidate), _normalized_title(canonical)).ratio() >= 0.90:
            return _strip_outer_separators(raw[raw_tokens[len(canonical_tokens)-1].end():])
    return raw


def infer_copy_metadata_from_legacy_title(raw_title: str, canonical_title: str, media_type: str = "movie") -> dict:
    """Recover physical-copy metadata after TMDb confirms the movie title.

    Unlike the conservative title parser, this pass can search the leftover
    product description in any order because the canonical movie title has
    already been established.  It returns metadata only; it never mutates the
    title itself.
    """
    raw = _normalize_spaces(raw_title)
    leftover = _strip_canonical_title(raw, canonical_title)
    parsed = parse_barcode_product_title(raw)

    formats: list[str] = []
    for match in re.finditer(r"4K(?:\s+Ultra\s+HD|\s+UHD)?|Ultra\s+HD|UHD|Blue?[- ]?ray|HD[- ]?DVD|DVD|VHS", leftover, re.I):
        token = match.group(0)
        if re.fullmatch(r"Blue?[- ]?ray", token, re.I):
            canonical = "Blu-ray"
        else:
            canonical = _canonical_format(token)
        if canonical and canonical not in formats:
            formats.append(canonical)

    disc_match = _DISC_PATTERN.search(leftover)
    disc_count = _disc_count(disc_match) if disc_match else parsed.disc_count

    region_match = _REGION_PATTERN.search(leftover)
    region = _canonical_region(region_match.group(0)) if region_match else parsed.region

    language = parsed.language
    # Once the canonical title is removed, bare language words are safe to
    # treat as product metadata; title words such as Johnny English are gone.
    language_matches = []
    for match in _LANGUAGE_SEQUENCE_PATTERN.finditer(leftover):
        value = _canonical_languages(match.group(0))
        if value:
            for item in value.split(" + "):
                if item not in language_matches:
                    language_matches.append(item)
    if language_matches:
        language = " + ".join(language_matches)

    edition = parsed.edition
    if str(media_type or "movie").strip().lower() == "tv":
        tv_edition = _tv_set_edition(raw) or _tv_set_edition(leftover) or _tv_set_edition_from_leftover(leftover)
        if tv_edition:
            edition = tv_edition
    known_editions = list(_EDITION_PATTERN.finditer(leftover))
    if known_editions:
        # Prefer the most specific recognized edition text found outside the
        # confirmed movie title, regardless of where formats/disc info occurs.
        edition = max((_normalize_spaces(m.group(0)) for m in known_editions), key=len)
        prefix = _DISC_PATTERN.match(edition)
        if prefix:
            disc_count = disc_count or _disc_count(prefix)
            edition = _strip_outer_separators(edition[prefix.end():])
    elif not edition:
        # Unknown marketing editions do not need a dictionary entry. First
        # remove other independently detected copy metadata so words such as
        # "Blu-ray" or "two disk" cannot become part of the edition label.
        edition_source = leftover
        for pattern, _ in _FORMAT_PATTERNS:
            edition_source = pattern.sub(" ", edition_source)
        edition_source = re.sub(r"Blue?[- ]?ray", " ", edition_source, flags=re.I)
        edition_source = _DISC_PATTERN.sub(" ", edition_source)
        edition_source = _REGION_PATTERN.sub(" ", edition_source)
        edition_source = _PACKAGING_PATTERN.sub(" ", edition_source)
        edition_source = _VIDEO_STANDARD_PATTERN.sub(" ", edition_source)
        edition_source = _CATALOG_CATEGORY_PATTERN.sub(" ", edition_source)
        for distributor_name in sorted(_KNOWN_DISTRIBUTORS, key=len, reverse=True):
            edition_source = re.sub(re.escape(distributor_name), " ", edition_source, flags=re.I)
        edition_source = re.sub(r"\s*[,;|:/+&-]\s*", " ", edition_source)
        edition_source = _normalize_spaces(edition_source)
        generic = re.search(
            r"(?<![A-Za-z0-9])(?P<edition>(?:[A-Za-z0-9'’.-]+\s+){0,3}[A-Za-z0-9'’.-]+\s+Edition)(?![A-Za-z0-9])",
            edition_source,
            re.I,
        )
        if generic:
            edition = _normalize_spaces(generic.group("edition"))

    return {
        "formats": tuple(formats) if formats else parsed.formats,
        "format": " + ".join(formats) if formats else parsed.format,
        "edition": edition,
        "language": language,
        "region": region,
        "disc_count": disc_count,
    }

def _normalized_title(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    asciiish = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", asciiish.lower()).strip()


def _number_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\b\d+\b", _normalized_title(value)))




def _append_unique_candidate(candidates: list[str], value: str) -> None:
    value = _strip_outer_separators(_normalize_spaces(value))
    if not value or value.lower() in {"the", "a", "an"}:
        return
    key = _normalized_title(value)
    if key and all(_normalized_title(existing) != key for existing in candidates):
        candidates.append(value)


def _strip_trailing_note(value: str) -> str:
    return re.sub(r"\s*[\[(][^\[\]()]{1,80}[\])]\s*$", "", value).strip()


def _strip_media_words(value: str) -> str:
    for pattern, _ in _FORMAT_PATTERNS:
        value = pattern.sub(" ", value)
    # Removing media tokens can leave punctuation/connectors behind, e.g.
    # "Beauty and the Beast, DVD and Blu-ray" -> "... , and".
    value = re.sub(r"(?:\s+(?:and|with)|\s*[,/&+\-]\s*)+$", "", value, flags=re.I)
    return value


def infer_legacy_title_year(raw_title: str) -> int | None:
    """Infer a release year from noisy metadata only when context makes it safe."""
    raw = _normalize_spaces(raw_title)
    if not raw:
        return None
    parsed = parse_barcode_product_title(raw)

    # A year embedded in a real title (e.g. "2001: A Space Odyssey") must not
    # automatically become a release year. Only trust an embedded year when
    # the same string also contains a strong product-metadata cue.
    has_product_context = bool(
        _EDITION_PATTERN.search(raw)
        or _PACKAGING_PATTERN.search(raw)
        or _REGION_PATTERN.search(raw)
        or _CATALOG_CATEGORY_PATTERN.search(raw)
        or any(pattern.search(raw) for pattern, _ in _FORMAT_PATTERNS)
        or any(distributor.lower() in raw.lower() for distributor in _KNOWN_DISTRIBUTORS)
    )
    if not has_product_context:
        return None
    if parsed.year is not None:
        return parsed.year

    matches = list(_YEAR_PATTERN.finditer(raw))
    if len(matches) != 1:
        return None
    candidate = int(matches[0].group(0))
    if 1900 <= candidate <= datetime.now().year + 1:
        return candidate
    return None


def _strip_known_metadata_anywhere(value: str) -> tuple[str, bool]:
    """Remove strong product metadata from anywhere for search-candidate use."""
    original = value
    value = _EDITION_PATTERN.sub(" ", value)
    value = _PACKAGING_PATTERN.sub(" ", value)
    value = _DISC_PATTERN.sub(" ", value)
    value = _REGION_PATTERN.sub(" ", value)
    value = _VIDEO_STANDARD_PATTERN.sub(" ", value)
    value = _CATALOG_CATEGORY_PATTERN.sub(" ", value)
    for pattern, _ in _FORMAT_PATTERNS:
        value = pattern.sub(" ", value)
    for distributor in sorted(_KNOWN_DISTRIBUTORS, key=len, reverse=True):
        value = re.sub(re.escape(distributor), " ", value, flags=re.I)
    inferred_year = infer_legacy_title_year(original)
    if inferred_year is not None:
        value = re.sub(rf"(?<!\d){inferred_year}(?!\d)", " ", value)
    value = re.sub(r"\s*[,;|:/+&\-]\s*", " ", value)
    value = re.sub(r"\b(?:and|with)\s*$", "", value, flags=re.I)
    value = _normalize_spaces(value)
    return value, _normalized_title(value) != _normalized_title(original)


def _strip_generic_edition(value: str) -> str:
    # Unknown marketing labels should not require a dictionary entry. This is
    # deliberately only a candidate transform, never destructive metadata parsing.
    return re.sub(
        r"(?:\s*[-–—,:;|]\s*|\s+)[A-Za-z0-9][A-Za-z0-9'’.-]*\s+Edition\s*$",
        "",
        value,
        flags=re.I,
    ).strip()


def generate_movie_title_candidates(raw_title: str) -> list[str]:
    """Generate conservative TMDb search titles from a noisy legacy title.

    Candidates are alternatives only: generating one never mutates the stored
    movie title. The structured barcode parser supplies known metadata cleanup,
    while generic transforms handle old imports that do not fit a strict list.
    """
    raw = _normalize_spaces(raw_title)
    if not raw:
        return []

    candidates: list[str] = []
    parsed = parse_barcode_product_title(raw)
    metadata_clean, changed = _strip_known_metadata_anywhere(raw)

    # Put the strongest cleanup options first because bulk repair deliberately
    # caps TMDb usage. A single unexplained marketing word after known metadata
    # gets one progressively shorter candidate; high-confidence scoring still
    # decides whether it is safe to accept.
    _append_unique_candidate(candidates, parsed.title)
    _append_unique_candidate(candidates, metadata_clean)
    words = metadata_clean.split()
    generic_clean = _strip_generic_edition(_strip_media_words(_strip_trailing_note(metadata_clean)))
    before_generic = len(candidates)
    _append_unique_candidate(candidates, generic_clean)
    if len(candidates) == before_generic and changed and len(words) >= 2:
        _append_unique_candidate(candidates, " ".join(words[:-1]))
    for value in (parsed.fallback_title, raw):
        _append_unique_candidate(candidates, value)

    # Apply generic transforms both to the raw title and to parser-produced
    # candidates so multiple kinds of noise can be removed progressively.
    for seed in list(candidates):
        note = _strip_trailing_note(seed)
        _append_unique_candidate(candidates, note)

        media = _strip_media_words(seed)
        _append_unique_candidate(candidates, media)

        edition = _strip_generic_edition(seed)
        _append_unique_candidate(candidates, edition)

        collection = re.sub(
            r"(?:\s*[-–—,:;|]\s*|\s+)Collection\s*$",
            "",
            seed,
            flags=re.I,
        )
        _append_unique_candidate(candidates, collection)

        combined = _strip_generic_edition(_strip_media_words(_strip_trailing_note(seed)))
        _append_unique_candidate(candidates, combined)

    # Additional shorter stems are late fallbacks for manual Identify. Bulk
    # repair sees only the first three candidates above.
    if changed and len(words) >= 4:
        max_trim = min(3, len(words) - 2)
        for trim in range(2, max_trim + 1):
            _append_unique_candidate(candidates, " ".join(words[:-trim]))

    return candidates[:12]


def _contains_strong_copy_metadata(value: str) -> bool:
    text = value or ""
    return bool(
        _EDITION_PATTERN.search(text)
        or _DISC_PATTERN.search(text)
        or _REGION_PATTERN.search(text)
        or _PACKAGING_PATTERN.search(text)
        or _VIDEO_STANDARD_PATTERN.search(text)
        or any(pattern.search(text) for pattern, _ in _FORMAT_PATTERNS)
    )


def search_ready_title_candidates(raw_title: str, media_type: str = "movie") -> list[str]:
    """Return search candidates, stripping TV set/season suffixes only in TV mode."""
    raw = _normalize_spaces(raw_title)
    candidates: list[str] = []
    is_tv = str(media_type or "movie").strip().lower() == "tv"
    if is_tv:
        tv_title = _tv_set_search_title(raw)
        if tv_title and _normalized_title(tv_title) != _normalized_title(raw):
            _append_unique_candidate(candidates, tv_title)
    for value in generate_movie_title_candidates(raw):
        if is_tv:
            _append_unique_candidate(candidates, _tv_set_search_title(value))
        _append_unique_candidate(candidates, value)
    if not candidates:
        return []
    clean = [value for value in candidates if not _contains_strong_copy_metadata(value)]
    noisy = [value for value in candidates if _contains_strong_copy_metadata(value)]
    return clean + noisy


def search_ready_movie_title_candidates(raw_title: str) -> list[str]:
    """Backward-compatible movie-only wrapper."""
    return search_ready_title_candidates(raw_title, media_type="movie")

def high_confidence_tmdb_match(query_titles: Iterable[str], query_year: int | None, results: Iterable[Mapping]) -> dict | None:
    """Choose only a decisive TMDb match across multiple search candidates."""
    queries = [q for q in query_titles if _normalized_title(q)]
    if not queries:
        return None
    try:
        year = int(query_year) if query_year not in (None, "") else None
    except (TypeError, ValueError):
        year = None

    scored: list[dict] = []
    for source in results:
        item = dict(source)
        title = str(item.get("title") or "")
        title_norm = _normalized_title(title)
        best_score = 0
        best_similarity = 0.0
        exact = False
        for query in queries:
            query_norm = _normalized_title(query)
            similarity = SequenceMatcher(None, query_norm, title_norm).ratio() if query_norm and title_norm else 0.0
            ranked = rank_tmdb_results(query, year, [item])
            score = int(ranked[0].get("match_score") or 0) if ranked else 0
            best_score = max(best_score, score)
            best_similarity = max(best_similarity, similarity)
            exact = exact or (query_norm == title_norm and bool(query_norm))
        item["match_score"] = best_score
        item["match_similarity"] = best_similarity
        item["match_exact"] = exact
        scored.append(item)

    scored.sort(key=lambda x: (-int(x.get("match_score") or 0), -float(x.get("match_similarity") or 0.0), str(x.get("title") or "").lower()))
    if not scored:
        return None
    top = scored[0]
    second = scored[1] if len(scored) > 1 else None
    top_score = int(top.get("match_score") or 0)
    second_score = int(second.get("match_score") or 0) if second else 0
    top_similarity = float(top.get("match_similarity") or 0.0)
    second_similarity = float(second.get("match_similarity") or 0.0) if second else 0.0

    if year is not None:
        if top_score >= 140 and (second is None or top_score - second_score >= 20):
            return top
        candidate_year = top.get("year")
        if isinstance(candidate_year, int) and candidate_year == year and top_similarity >= 0.92 and (second is None or top_similarity - second_similarity >= 0.08):
            return top
        return None

    if bool(top.get("match_exact")):
        if top_score >= 110 and (second is None or top_score - second_score >= 20):
            return top
        return None

    # Typo tolerance is deliberately narrow: long-ish titles only, >=92%
    # similarity, and a clear gap from the runner-up. This catches Tale/Tail
    # without turning broad stems such as 'Ace Ventura' into a guessed sequel.
    if len(_normalized_title(str(top.get("title") or ""))) >= 10 and top_similarity >= 0.92:
        if second is None or top_similarity - second_similarity >= 0.08:
            return top
    return None

def rank_tmdb_results(query_title: str, query_year: int | None, results: Iterable[Mapping]) -> list[dict]:
    query_norm = _normalized_title(query_title)
    query_numbers = _number_tokens(query_title)
    ranked: list[dict] = []

    for source in results:
        item = dict(source)
        candidate_title = str(item.get("title") or "")
        candidate_norm = _normalized_title(candidate_title)
        similarity = SequenceMatcher(None, query_norm, candidate_norm).ratio() if query_norm and candidate_norm else 0.0
        score = int(round(similarity * 70))
        if candidate_norm == query_norm and query_norm:
            score += 45
        elif candidate_norm.startswith(query_norm + " ") or query_norm.startswith(candidate_norm + " "):
            score += 8

        candidate_year = item.get("year")
        if query_year is not None and isinstance(candidate_year, int):
            difference = abs(candidate_year - query_year)
            if difference == 0:
                score += 35
            else:
                score -= min(30, 7 * difference)

        candidate_numbers = _number_tokens(candidate_title)
        if query_numbers != candidate_numbers and (query_numbers or candidate_numbers):
            score -= 18

        item["match_score"] = max(0, score)
        ranked.append(item)

    ranked.sort(key=lambda item: (-int(item.get("match_score") or 0), str(item.get("title") or "").lower()))
    return ranked


def best_match_score(results: Iterable[Mapping]) -> int:
    return max((int(item.get("match_score") or 0) for item in results), default=0)
