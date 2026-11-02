"""Retrieval over the onboarding FAQ (the retrieval half of the RAG chatbot).

Uses TF-IDF with cosine similarity implemented in pure Python, so no vector database is needed
for a small FAQ. See ChatService for the generation half.
"""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    "a an and are as at be by can do does for from how i in is it my of on or the this to was what when where which who why with you your "
    "el la los las un una unos unas de del al en que es mi mis tu tus por para con se su como cual cuales donde lo le les me puedo puede hay si y o".split()
)


@dataclass(frozen=True)
class FaqEntry:
    question: str
    answer: str

    @property
    def text(self) -> str:
        return f"{self.question}\n{self.answer}"


def _strip_accents(text: str) -> str:
    """"Qué" and "que", "documentó" and "documento" must match: compare words without accents."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_PATTERN.findall(_strip_accents(text.lower())) if t not in _STOP_WORDS and len(t) > 1]


def load_faq(path: Path) -> list[FaqEntry]:
    entries: list[FaqEntry] = []
    for block in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.MULTILINE)[1:]:
        question, _, answer = block.partition("\n")
        entries.append(FaqEntry(question.strip(), answer.strip()))
    return entries


class FaqRetriever:
    """TF-IDF search over the FAQ.

    `entries` is the FAQ in the default language (English). `translations` maps a language code to the same FAQ in
    that language, entry by entry in the same order. Every entry is indexed with the text of ALL its languages, so a
    question written in Spanish finds the right entry even on the English screen (and the other way round), and the
    result is returned in the language the caller asks for.
    """

    def __init__(self, entries: list[FaqEntry], translations: dict[str, list[FaqEntry]] | None = None):
        self._entries = entries
        self._by_language = {"en": entries, **(translations or {})}
        for language, translated in self._by_language.items():
            if len(translated) != len(entries):
                raise ValueError(f"The '{language}' FAQ has {len(translated)} entries, expected {len(entries)}.")
        index_texts = [
            "\n".join(translated[i].text for translated in self._by_language.values()) for i in range(len(entries))
        ]
        self._doc_tokens = [Counter(tokenize(text)) for text in index_texts]
        document_frequency: Counter[str] = Counter()
        for tokens in self._doc_tokens:
            document_frequency.update(tokens.keys())
        total = len(entries)
        self._idf = {
            term: math.log((1 + total) / (1 + freq)) + 1 for term, freq in document_frequency.items()
        }
        self._doc_vectors = [self._vectorize(tokens) for tokens in self._doc_tokens]

    def search(self, query: str, top_k: int = 3, min_score: float = 0.08, language: str = "en") -> list[FaqEntry]:
        query_vector = self._vectorize(Counter(tokenize(query)))
        if not query_vector:
            return []
        answers = self._by_language.get(language, self._entries)
        scored = [
            (self._cosine(query_vector, doc_vector), entry)
            for doc_vector, entry in zip(self._doc_vectors, answers)
        ]
        scored = [item for item in scored if item[0] >= min_score]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def _vectorize(self, tokens: Counter[str]) -> dict[str, float]:
        return {t: count * self._idf[t] for t, count in tokens.items() if t in self._idf}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
        norm_a = math.sqrt(sum(w * w for w in a.values()))
        norm_b = math.sqrt(sum(w * w for w in b.values()))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
