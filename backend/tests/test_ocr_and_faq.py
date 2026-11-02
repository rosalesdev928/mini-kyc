from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.errors import ExtractionFailedError
from app.core.sql_script import split_sql_script
from app.prompts import CHAT_PROMPT_TEMPLATE, OCR_SYSTEM_INSTRUCTION, OCR_USER_PROMPT
from app.services.chat_service import NO_ANSWER, ChatService
from app.services.faq_service import FaqRetriever, load_faq
from app.services.ocr_service import parse_model_output

ROOT = Path(__file__).resolve().parents[2]
FAQ = load_faq(ROOT / "backend" / "app" / "data" / "faq.md")


def test_parse_valid_model_output():
    result = parse_model_output(
        '{"is_identity_document": true, "is_legible": true, "document_type": "DNI",'
        ' "full_name": " Maria Fernandez ", "document_number": "70154892", "confidence": 0.98}'
    )
    assert result.full_name == "Maria Fernandez"
    assert result.document_number == "70154892"
    assert result.confidence == 0.98


def test_parse_tolerates_markdown_code_fences():
    fenced = (
        '```json\n{"is_identity_document": true, "is_legible": false, "document_type": "OTHER",'
        ' "full_name": null, "document_number": null, "confidence": 0.1}\n```'
    )
    assert parse_model_output(fenced).full_name is None


@pytest.mark.parametrize("bad", ["not json", "{}", '{"is_identity_document": true, "is_legible": true, "confidence": 7}'])
def test_parse_rejects_malformed_output(bad):
    with pytest.raises(ExtractionFailedError):
        parse_model_output(bad)


def test_faq_retrieval_finds_the_right_entry():
    retriever = FaqRetriever(FAQ)
    top = retriever.search("why was my photo rejected as blurry?")[0]
    assert "blurry" in top.question.lower()
    assert retriever.search("which file formats can I upload")[0].question.startswith("Which image formats")


def test_chat_without_matching_context_does_not_invent_answers():
    service = ChatService(FaqRetriever(FAQ), Settings(gemini_api_key=""))
    assert service.answer("what is the airspeed velocity of a swallow").answer == NO_ANSWER


def test_chat_falls_back_to_faq_text_without_llm():
    service = ChatService(FaqRetriever(FAQ), Settings(gemini_api_key=""))
    response = service.answer("Do you store my document photo?")
    assert "not saved" in response.answer
    assert response.sources


def test_sql_script_splitter_handles_delimiters():
    script = (
        "-- comment\nCREATE TABLE t (id INT);\n\nDELIMITER $$\n"
        "DROP PROCEDURE IF EXISTS p$$\nCREATE PROCEDURE p()\nBEGIN\n  SELECT 1;\n  SELECT 2;\nEND$$\nDELIMITER ;\n"
    )
    statements = split_sql_script(script)
    assert len(statements) == 3
    assert statements[0] == "CREATE TABLE t (id INT)"
    assert statements[2].startswith("CREATE PROCEDURE p()") and "SELECT 2;" in statements[2]


def test_real_sql_files_produce_expected_statements():
    schema = split_sql_script((ROOT / "database" / "schema.sql").read_text())
    procedures = split_sql_script((ROOT / "database" / "stored_procedures.sql").read_text())
    assert sum(s.startswith("CREATE TABLE") for s in schema) == 6
    assert sum(s.startswith("CREATE OR REPLACE VIEW v_onboarding_details") for s in schema) == 1
    assert sum(s.startswith("CREATE PROCEDURE") for s in procedures) == 13
    assert not any("DELIMITER" in s for s in procedures)


def test_every_procedure_the_repository_calls_exists_in_the_sql_file():
    """The API and the database scripts are written separately: this catches a renamed or missing procedure
    without needing a running MySQL."""
    import re

    repository = (ROOT / "backend" / "app" / "repositories" / "onboarding_repository.py").read_text()
    procedures = (ROOT / "database" / "stored_procedures.sql").read_text()
    called = set(re.findall(r'"(sp_[a-z_]+)"', repository))
    defined = set(re.findall(r"CREATE PROCEDURE (sp_[a-z_]+)", procedures))
    assert called and called <= defined, called - defined


def test_the_read_model_exposes_every_column_the_repository_maps():
    schema = (ROOT / "database" / "schema.sql").read_text()
    for column in ("effective_status", "erased_at", "review_decision", "reviewed_by", "flags", "document_type"):
        assert f"AS {column}" in schema, column


def test_every_text_parameter_of_the_procedures_declares_its_collation():
    """Regression test: managed MySQL defaults to utf8mb4_0900_ai_ci and mixing it with the tables'
    utf8mb4_unicode_ci raised "Illegal mix of collations" (error 1267) in production."""
    import re

    procedures = (ROOT / "database" / "stored_procedures.sql").read_text()
    text_params = re.findall(r"\bIN\s+\w+\s+((?:VARCHAR|CHAR)\(\d+\)[^,)\n]*)", procedures)
    assert len(text_params) >= 12
    assert all("COLLATE utf8mb4_unicode_ci" in param for param in text_params), text_params


def test_prompts_md_lists_every_runtime_prompt():
    """PROMPTS.md must contain the exact prompts the application sends (a graded deliverable)."""
    text = (ROOT / "PROMPTS.md").read_text(encoding="utf-8")
    for prompt in (OCR_SYSTEM_INSTRUCTION, OCR_USER_PROMPT, CHAT_PROMPT_TEMPLATE):
        assert prompt in text
