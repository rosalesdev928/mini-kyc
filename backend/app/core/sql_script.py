"""Minimal SQL script splitter (no third-party dependencies)."""


def split_sql_script(script: str) -> list[str]:
    """Split a SQL script into statements, honouring `DELIMITER` commands.

    Needed because stored procedure bodies contain semicolons. Lines that start with `--`
    outside a statement are treated as comments and skipped.
    """
    statements: list[str] = []
    delimiter = ";"
    buffer: list[str] = []

    for line in script.splitlines():
        stripped = line.strip()
        if not buffer and (not stripped or stripped.startswith("--")):
            continue
        if not buffer and stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split(None, 1)[1].strip()
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            statement = "\n".join(buffer).rstrip()
            statement = statement[: -len(delimiter)].rstrip()
            if statement:
                statements.append(statement)
            buffer = []

    if buffer and "\n".join(buffer).strip():
        statements.append("\n".join(buffer).strip())
    return statements
