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

-- Why a record needs a human look (LOW_CONFIDENCE, INVALID_DOCUMENT_NUMBER, DUPLICATE_DOCUMENT, DUPLICATE_IMAGE). 1 record : N flags.
CREATE TABLE IF NOT EXISTS onboarding_flags (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    onboarding_id  BIGINT UNSIGNED NOT NULL,
    code           VARCHAR(40)     NOT NULL,
    created_at     DATETIME        NOT NULL,
    PRIMARY KEY (id),
    KEY ix_flags_onboarding (onboarding_id),
    CONSTRAINT fk_flags_onboarding FOREIGN KEY (onboarding_id) REFERENCES onboarding_records (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Operator decisions on records flagged NEEDS_REVIEW. Kept as history (the latest decision wins). 1 record : N reviews.
CREATE TABLE IF NOT EXISTS onboarding_reviews (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    onboarding_id   BIGINT UNSIGNED NOT NULL,
    decision        ENUM ('APPROVED', 'REJECTED') NOT NULL,
    reviewer        VARCHAR(100)    NOT NULL,
    review_comment  VARCHAR(500)    NULL,
    created_at      DATETIME        NOT NULL,
    PRIMARY KEY (id),
    KEY ix_reviews_onboarding (onboarding_id),
    CONSTRAINT fk_reviews_onboarding FOREIGN KEY (onboarding_id) REFERENCES onboarding_records (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Personal data erasure ("right to be forgotten"). The onboarding row is kept so that counts and the audit trail
-- survive, but its personal data is replaced by the erasure procedure. 1 record : 0..1 erasure.
CREATE TABLE IF NOT EXISTS onboarding_erasures (
    onboarding_id  BIGINT UNSIGNED NOT NULL,
    erased_by      VARCHAR(100)    NOT NULL,
    reason         VARCHAR(200)    NULL,
    created_at     DATETIME        NOT NULL,
    PRIMARY KEY (onboarding_id),
    CONSTRAINT fk_erasures_onboarding FOREIGN KEY (onboarding_id) REFERENCES onboarding_records (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- One flat read model: the record with its customer, document type, reasons for review, latest operator decision
-- and erasure. effective_status is the single place that decides which status the outside world sees:
-- ERASED beats the operator decision, which beats the automatic status.
-- The explicit collation keeps comparisons with the procedure parameters safe on any server default.
CREATE OR REPLACE VIEW v_onboarding_details AS
SELECT o.id AS id,
       c.email AS email,
       dt.code AS document_type,
       o.full_name AS full_name,
       o.document_number AS document_number,
       o.ocr_confidence AS ocr_confidence,
       o.status AS status,
       o.original_filename AS original_filename,
       o.created_at AS created_at,
       (SELECT GROUP_CONCAT(f.code ORDER BY f.id SEPARATOR ',')
          FROM onboarding_flags f
         WHERE f.onboarding_id = o.id) AS flags,
       rv.decision AS review_decision,
       rv.reviewer AS reviewed_by,
       rv.review_comment AS review_comment,
       rv.created_at AS reviewed_at,
       er.created_at AS erased_at,
       CONVERT(
           CASE WHEN er.onboarding_id IS NOT NULL THEN 'ERASED'
                WHEN rv.decision IS NOT NULL THEN rv.decision
                ELSE o.status
           END USING utf8mb4) COLLATE utf8mb4_unicode_ci AS effective_status
  FROM onboarding_records o
  JOIN customers c ON c.id = o.customer_id
  JOIN document_types dt ON dt.id = o.document_type_id
  LEFT JOIN onboarding_reviews rv
    ON rv.id = (SELECT MAX(r2.id) FROM onboarding_reviews r2 WHERE r2.onboarding_id = o.id)
  LEFT JOIN onboarding_erasures er ON er.onboarding_id = o.id;
