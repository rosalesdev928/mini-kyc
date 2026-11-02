-- Mini KYC - stored procedures (MySQL 8+)
-- The application persists and reads onboarding data ONLY through these procedures.
-- Idempotent: each procedure is dropped and recreated.
-- String parameters declare the table collation explicitly: managed MySQL services (e.g. Aiven)
-- default to utf8mb4_0900_ai_ci, which otherwise raises "Illegal mix of collations" (error 1267).
-- Run with the mysql CLI:  mysql -u root -p mini_kyc < database/stored_procedures.sql

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_get_onboarding_by_id$$
CREATE PROCEDURE sp_get_onboarding_by_id(IN p_onboarding_id BIGINT UNSIGNED)
BEGIN
    SELECT o.id,
           c.email,
           dt.code AS document_type,
           o.full_name,
           o.document_number,
           o.ocr_confidence,
           o.status,
           o.original_filename,
           o.created_at,
           (SELECT GROUP_CONCAT(f.code ORDER BY f.id SEPARATOR ',')
              FROM onboarding_flags f
             WHERE f.onboarding_id = o.id) AS flags,
           rv.decision AS review_decision,
           rv.reviewer AS reviewed_by,
           rv.review_comment,
           rv.created_at AS reviewed_at
      FROM onboarding_records o
      JOIN customers c ON c.id = o.customer_id
      JOIN document_types dt ON dt.id = o.document_type_id
      LEFT JOIN onboarding_reviews rv
        ON rv.id = (SELECT MAX(r2.id) FROM onboarding_reviews r2 WHERE r2.onboarding_id = o.id)
     WHERE o.id = p_onboarding_id;
END$$

DROP PROCEDURE IF EXISTS sp_list_onboardings_by_email$$
CREATE PROCEDURE sp_list_onboardings_by_email(IN p_email VARCHAR(254) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci, IN p_limit INT)
BEGIN
    SELECT o.id,
           c.email,
           dt.code AS document_type,
           o.full_name,
           o.document_number,
           o.ocr_confidence,
           o.status,
           o.original_filename,
           o.created_at,
           (SELECT GROUP_CONCAT(f.code ORDER BY f.id SEPARATOR ',')
              FROM onboarding_flags f
             WHERE f.onboarding_id = o.id) AS flags,
           rv.decision AS review_decision,
           rv.reviewer AS reviewed_by,
           rv.review_comment,
           rv.created_at AS reviewed_at
      FROM onboarding_records o
      JOIN customers c ON c.id = o.customer_id
      JOIN document_types dt ON dt.id = o.document_type_id
      LEFT JOIN onboarding_reviews rv
        ON rv.id = (SELECT MAX(r2.id) FROM onboarding_reviews r2 WHERE r2.onboarding_id = o.id)
     WHERE c.email = p_email
     ORDER BY o.created_at DESC, o.id DESC
     LIMIT p_limit;
END$$

-- Records waiting for an operator: flagged NEEDS_REVIEW and without a decision yet (oldest first).
DROP PROCEDURE IF EXISTS sp_list_pending_reviews$$
CREATE PROCEDURE sp_list_pending_reviews(IN p_limit INT)
BEGIN
    SELECT o.id,
           c.email,
           dt.code AS document_type,
           o.full_name,
           o.document_number,
           o.ocr_confidence,
           o.status,
           o.original_filename,
           o.created_at,
           (SELECT GROUP_CONCAT(f.code ORDER BY f.id SEPARATOR ',')
              FROM onboarding_flags f
             WHERE f.onboarding_id = o.id) AS flags,
           rv.decision AS review_decision,
           rv.reviewer AS reviewed_by,
           rv.review_comment,
           rv.created_at AS reviewed_at
      FROM onboarding_records o
      JOIN customers c ON c.id = o.customer_id
      JOIN document_types dt ON dt.id = o.document_type_id
      LEFT JOIN onboarding_reviews rv
        ON rv.id = (SELECT MAX(r2.id) FROM onboarding_reviews r2 WHERE r2.onboarding_id = o.id)
     WHERE o.status = 'NEEDS_REVIEW' AND rv.id IS NULL
     ORDER BY o.created_at ASC, o.id ASC
     LIMIT p_limit;
END$$

DROP PROCEDURE IF EXISTS sp_create_onboarding$$
CREATE PROCEDURE sp_create_onboarding(
    IN p_email              VARCHAR(254) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_document_type_code VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_full_name          VARCHAR(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_document_number    VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_ocr_confidence     DECIMAL(5, 2),
    IN p_status             VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_image_sha256       CHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_original_filename  VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    DECLARE v_customer_id      BIGINT UNSIGNED;
    DECLARE v_document_type_id TINYINT UNSIGNED;
    DECLARE v_onboarding_id    BIGINT UNSIGNED;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_status NOT IN ('VERIFIED', 'NEEDS_REVIEW') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid onboarding status';
    END IF;

    SELECT id INTO v_document_type_id FROM document_types WHERE code = p_document_type_code;
    IF v_document_type_id IS NULL THEN
        SELECT id INTO v_document_type_id FROM document_types WHERE code = 'OTHER';
    END IF;

    START TRANSACTION;

    INSERT INTO customers (email, created_at)
    VALUES (p_email, UTC_TIMESTAMP())
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);
    SET v_customer_id = LAST_INSERT_ID();

    INSERT INTO onboarding_records
        (customer_id, document_type_id, full_name, document_number,
         ocr_confidence, status, image_sha256, original_filename, created_at)
    VALUES
        (v_customer_id, v_document_type_id, p_full_name, p_document_number,
         p_ocr_confidence, p_status, p_image_sha256, p_original_filename, UTC_TIMESTAMP());
    SET v_onboarding_id = LAST_INSERT_ID();

    COMMIT;

    CALL sp_get_onboarding_by_id(v_onboarding_id);
END$$

DROP PROCEDURE IF EXISTS sp_add_onboarding_flag$$
CREATE PROCEDURE sp_add_onboarding_flag(
    IN p_onboarding_id BIGINT UNSIGNED,
    IN p_code          VARCHAR(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    INSERT INTO onboarding_flags (onboarding_id, code, created_at)
    VALUES (p_onboarding_id, p_code, UTC_TIMESTAMP());
END$$

-- Does the same document number / image already exist under ANOTHER email? (possible identity reuse)
DROP PROCEDURE IF EXISTS sp_find_duplicate_signals$$
CREATE PROCEDURE sp_find_duplicate_signals(
    IN p_document_number VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_image_sha256    CHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_email           VARCHAR(254) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    SELECT
        (SELECT COUNT(*)
           FROM onboarding_records o
           JOIN customers c ON c.id = o.customer_id
          WHERE o.document_number = p_document_number AND c.email <> p_email) AS same_number_other_email,
        (SELECT COUNT(*)
           FROM onboarding_records o
           JOIN customers c ON c.id = o.customer_id
          WHERE o.image_sha256 = p_image_sha256 AND c.email <> p_email) AS same_image_other_email;
END$$

-- Operator decision. Atomic: locks the record, checks it is still pending, stores the decision.
DROP PROCEDURE IF EXISTS sp_review_onboarding$$
CREATE PROCEDURE sp_review_onboarding(
    IN p_onboarding_id BIGINT UNSIGNED,
    IN p_decision      VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_reviewer      VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_comment       VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    DECLARE v_status VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_decision NOT IN ('APPROVED', 'REJECTED') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid review decision';
    END IF;

    START TRANSACTION;

    SELECT status INTO v_status FROM onboarding_records WHERE id = p_onboarding_id FOR UPDATE;

    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Onboarding record not found';
    END IF;
    IF v_status <> 'NEEDS_REVIEW' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only records pending review can be reviewed';
    END IF;
    IF EXISTS (SELECT 1 FROM onboarding_reviews WHERE onboarding_id = p_onboarding_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This record was already reviewed';
    END IF;

    INSERT INTO onboarding_reviews (onboarding_id, decision, reviewer, review_comment, created_at)
    VALUES (p_onboarding_id, p_decision, p_reviewer, p_comment, UTC_TIMESTAMP());

    COMMIT;

    CALL sp_get_onboarding_by_id(p_onboarding_id);
END$$

DELIMITER ;
