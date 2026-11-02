"""Retrieval over the onboarding FAQ (the retrieval half of the RAG chatbot).

Uses TF-IDF with cosine similarity implemented in pure Python, so no vector database is needed
for a small FAQ. See ChatService for the generation half.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_TOKEN_PATTERN = re.compile(r"[a-záéíóúñü0-9]+")
_STOP_WORDS = frozenset(
    "a an and are as at be by can do does for from how i in is it my of on or the this to was what when where which who why with you your "
    "el la los las un una de del en que es mi por para con se su como cual donde".split()
)


@dataclass(frozen=True)
class FaqEntry:
    question: str
    answer: str

    @property
    def text(self) -> str:
        return f"{self.question}\n{self.answer}"


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_PATTERN.findall(text.lower()) if t not in _STOP_WORDS and len(t) > 1]


def load_faq(path: Path) -> list[FaqEntry]:
    entries: list[FaqEntry] = []
    for block in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.MULTILINE)[1:]:
        question, _, answer = block.partition("\n")
        entries.append(FaqEntry(question.strip(), answer.strip()))
    return entries


class FaqRetriever:
    def __init__(self, entries: list[FaqEntry]):
        self._entries = entries
        self._doc_tokens = [Counter(tokenize(entry.text)) for entry in entries]
        document_frequency: Counter[str] = Counter()
        for tokens in self._doc_tokens:
            document_frequency.update(tokens.keys())
        total = len(entries)
        self._idf = {
            term: math.log((1 + total) / (1 + freq)) + 1 for term, freq in document_frequency.items()
        }
        self._doc_vectors = [self._vectorize(tokens) for tokens in self._doc_tokens]

    def search(self, query: str, top_k: int = 3, min_score: float = 0.08) -> list[FaqEntry]:
        query_vector = self._vectorize(Counter(tokenize(query)))
        if not query_vector:
            return []
        scored = [
            (self._cosine(query_vector, doc_vector), entry)
            for doc_vector, entry in zip(self._doc_vectors, self._entries)
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
