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
    (re.compile(r"Blu[- ]?ray", re.I), "Blu-ray"),
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

_DISC_PATTERN = re.compile(r"(?P<count>\d{1,2})[- ]Disc(?:\s+(?:Set|Collection))?", re.I)
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
            state["disc_count"] = state.get("disc_count") or int(disc.group("count"))
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
    for match in re.finditer(r"4K(?:\s+Ultra\s+HD|\s+UHD)?|Ultra\s+HD|UHD|Blu[- ]?ray|HD[- ]?DVD|DVD|VHS", raw, re.I):
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
                state["disc_count"] = state["disc_count"] or int(disc_prefix.group("count"))
                edition = _strip_outer_separators(edition[disc_prefix.end():])
            if edition and edition not in editions:
                editions.insert(0, edition)
            value = _strip_outer_separators(value[:edition_match.start()])
            continue

        disc_match = _suffix_match(value, _DISC_PATTERN)
        if disc_match:
            state["disc_count"] = state["disc_count"] or int(disc_match.group("count"))
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


def _normalized_title(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    asciiish = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", asciiish.lower()).strip()


def _number_tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\b\d+\b", _normalized_title(value)))


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
