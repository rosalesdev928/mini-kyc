-- Mini KYC - relational schema (MySQL 8+)
-- All timestamps are stored in UTC.
-- Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS customers (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email       VARCHAR(254)    NOT NULL,
    created_at  DATETIME        NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_customers_email (email)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS document_types (
    id    TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code  VARCHAR(20)      NOT NULL,
    name  VARCHAR(80)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_document_types_code (code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

INSERT IGNORE INTO document_types (code, name) VALUES
    ('DNI', 'National Identity Document (Peru)'),
    ('CE', 'Foreigner Card'),
    ('PASSPORT', 'Passport'),
    ('OTHER', 'Other identity document');

CREATE TABLE IF NOT EXISTS onboarding_records (
    id                 BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    customer_id        BIGINT UNSIGNED  NOT NULL,
    document_type_id   TINYINT UNSIGNED NOT NULL,
    full_name          VARCHAR(200)     NOT NULL,
    document_number    VARCHAR(30)      NOT NULL,
    ocr_confidence     DECIMAL(5, 2)    NOT NULL,
    status             ENUM ('VERIFIED', 'NEEDS_REVIEW') NOT NULL,
    image_sha256       CHAR(64)         NOT NULL,
    original_filename  VARCHAR(255)     NULL,
    created_at         DATETIME         NOT NULL,
    PRIMARY KEY (id),
    KEY ix_onboarding_customer (customer_id, created_at),
    KEY ix_onboarding_document_number (document_number),
    CONSTRAINT fk_onboarding_customer FOREIGN KEY (customer_id) REFERENCES customers (id),
    CONSTRAINT fk_onboarding_document_type FOREIGN KEY (document_type_id) REFERENCES document_types (id),
    CONSTRAINT ck_onboarding_confidence CHECK (ocr_confidence BETWEEN 0 AND 100)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
