-- Mini KYC - stored procedures (MySQL 8+)
-- The application persists and reads onboarding data ONLY through these procedures.
-- Idempotent: each procedure is dropped and recreated.
-- String parameters declare the table collation explicitly: managed MySQL services (e.g. Aiven)
-- default to utf8mb4_0900_ai_ci, which otherwise raises "Illegal mix of collations" (error 1267).
-- Reads go through the v_onboarding_details view (see schema.sql), so every read returns the same columns.
-- Run with the mysql CLI:  mysql -u root -p mini_kyc < database/stored_procedures.sql

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_get_onboarding_by_id$$
CREATE PROCEDURE sp_get_onboarding_by_id(IN p_onboarding_id BIGINT UNSIGNED)
BEGIN
    SELECT * FROM v_onboarding_details WHERE id = p_onboarding_id;
END$$

DROP PROCEDURE IF EXISTS sp_list_onboardings_by_email$$
CREATE PROCEDURE sp_list_onboardings_by_email(IN p_email VARCHAR(254) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci, IN p_limit INT)
BEGIN
    SELECT *
      FROM v_onboarding_details
     WHERE email = p_email
     ORDER BY created_at DESC, id DESC
     LIMIT p_limit;
END$$

-- Records waiting for an operator: flagged NEEDS_REVIEW and without a decision yet (oldest first).
DROP PROCEDURE IF EXISTS sp_list_pending_reviews$$
CREATE PROCEDURE sp_list_pending_reviews(IN p_limit INT)
BEGIN
    SELECT *
      FROM v_onboarding_details
     WHERE effective_status = 'NEEDS_REVIEW'
     ORDER BY created_at ASC, id ASC
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
    IF EXISTS (SELECT 1 FROM onboarding_erasures WHERE onboarding_id = p_onboarding_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This record was anonymized and cannot be reviewed';
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

-- ---------------------------------------------------------------------------------------------
-- Admin dashboard
-- ---------------------------------------------------------------------------------------------

-- Totals by effective status (one row).
DROP PROCEDURE IF EXISTS sp_admin_stats$$
CREATE PROCEDURE sp_admin_stats()
BEGIN
    SELECT COUNT(*) AS total,
           COALESCE(SUM(effective_status = 'VERIFIED'), 0) AS verified,
           COALESCE(SUM(effective_status = 'NEEDS_REVIEW'), 0) AS needs_review,
           COALESCE(SUM(effective_status = 'APPROVED'), 0) AS approved,
           COALESCE(SUM(effective_status = 'REJECTED'), 0) AS rejected,
           COALESCE(SUM(effective_status = 'ERASED'), 0) AS erased,
           COALESCE(AVG(ocr_confidence), 0) AS avg_confidence
      FROM v_onboarding_details;
END$$

-- Registrations per UTC day for the last p_days days (days without registrations are not returned).
DROP PROCEDURE IF EXISTS sp_admin_daily_counts$$
CREATE PROCEDURE sp_admin_daily_counts(IN p_days INT)
BEGIN
    SELECT DATE(created_at) AS day, COUNT(*) AS total
      FROM onboarding_records
     WHERE created_at >= DATE_SUB(UTC_DATE(), INTERVAL (p_days - 1) DAY)
     GROUP BY DATE(created_at)
     ORDER BY day;
END$$

-- Filtered, paginated listing. Empty p_status / p_query and NULL dates mean "no filter".
-- total_count is the number of matching rows before LIMIT (used for pagination).
DROP PROCEDURE IF EXISTS sp_admin_search$$
CREATE PROCEDURE sp_admin_search(
    IN p_status    VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_query     VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_date_from DATE,
    IN p_date_to   DATE,
    IN p_limit     INT,
    IN p_offset    INT
)
BEGIN
    SELECT v.*, COUNT(*) OVER () AS total_count
      FROM v_onboarding_details v
     WHERE (p_status = '' OR v.effective_status = p_status)
       AND (p_query = ''
            OR v.email LIKE CONCAT('%', p_query, '%')
            OR v.full_name LIKE CONCAT('%', p_query, '%')
            OR v.document_number LIKE CONCAT('%', p_query, '%'))
       AND (p_date_from IS NULL OR v.created_at >= p_date_from)
       AND (p_date_to IS NULL OR v.created_at < DATE_ADD(p_date_to, INTERVAL 1 DAY))
     ORDER BY v.created_at DESC, v.id DESC
     LIMIT p_limit OFFSET p_offset;
END$$

-- Audit trail of one record: registration, reasons for review, operator decision, erasure.
DROP PROCEDURE IF EXISTS sp_list_onboarding_events$$
CREATE PROCEDURE sp_list_onboarding_events(IN p_onboarding_id BIGINT UNSIGNED)
BEGIN
    SELECT 'REGISTERED' AS event_type, NULL AS actor, o.status AS detail, o.created_at AS occurred_at, 1 AS sort_order
      FROM onboarding_records o
     WHERE o.id = p_onboarding_id
    UNION ALL
    SELECT 'FLAGGED', NULL, f.code, f.created_at, 2
      FROM onboarding_flags f
     WHERE f.onboarding_id = p_onboarding_id
    UNION ALL
    SELECT rv.decision, rv.reviewer, rv.review_comment, rv.created_at, 3
      FROM onboarding_reviews rv
     WHERE rv.onboarding_id = p_onboarding_id
    UNION ALL
    SELECT 'ANONYMIZED', er.erased_by, er.reason, er.created_at, 4
      FROM onboarding_erasures er
     WHERE er.onboarding_id = p_onboarding_id
     ORDER BY occurred_at, sort_order;
END$$

-- Personal data erasure. Replaces the name, document number, email, photo hash and file name, drops the
-- operator's free-text comment, and records who did it and why. The row itself stays for statistics and audit.
-- Atomic: locks the record first. Refuses unknown or already anonymized records.
DROP PROCEDURE IF EXISTS sp_anonymize_onboarding$$
CREATE PROCEDURE sp_anonymize_onboarding(
    IN p_onboarding_id BIGINT UNSIGNED,
    IN p_actor         VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    IN p_reason        VARCHAR(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
)
BEGIN
    DECLARE v_customer_id     BIGINT UNSIGNED;
    DECLARE v_new_customer_id BIGINT UNSIGNED;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT customer_id INTO v_customer_id FROM onboarding_records WHERE id = p_onboarding_id FOR UPDATE;

    IF v_customer_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Onboarding record not found';
    END IF;
    IF EXISTS (SELECT 1 FROM onboarding_erasures WHERE onboarding_id = p_onboarding_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This record was already anonymized';
    END IF;

    -- A throw-away customer keeps the foreign key valid without keeping the real email.
    INSERT INTO customers (email, created_at)
    VALUES (CONCAT('erased-', p_onboarding_id, '@anonymized.invalid'), UTC_TIMESTAMP());
    SET v_new_customer_id = LAST_INSERT_ID();

    UPDATE onboarding_records
       SET customer_id       = v_new_customer_id,
           full_name         = '[erased]',
           document_number   = CONCAT('ERASED-', p_onboarding_id),
           image_sha256      = SHA2(CONCAT('erased:', p_onboarding_id), 256),
           original_filename = NULL
     WHERE id = p_onboarding_id;

    UPDATE onboarding_reviews SET review_comment = NULL WHERE onboarding_id = p_onboarding_id;

    -- The real customer disappears when this was their last record.
    DELETE FROM customers
     WHERE id = v_customer_id
       AND NOT EXISTS (SELECT 1 FROM onboarding_records WHERE customer_id = v_customer_id);

    INSERT INTO onboarding_erasures (onboarding_id, erased_by, reason, created_at)
    VALUES (p_onboarding_id, p_actor, p_reason, UTC_TIMESTAMP());

    COMMIT;

    CALL sp_get_onboarding_by_id(p_onboarding_id);
END$$

-- Ids of the records older than p_days days whose personal data has not been erased yet (retention policy).
DROP PROCEDURE IF EXISTS sp_list_expired_onboardings$$
CREATE PROCEDURE sp_list_expired_onboardings(IN p_days INT, IN p_limit INT)
BEGIN
    SELECT o.id
      FROM onboarding_records o
      LEFT JOIN onboarding_erasures er ON er.onboarding_id = o.id
     WHERE er.onboarding_id IS NULL
       AND o.created_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL p_days DAY)
     ORDER BY o.id
     LIMIT p_limit;
END$$

DELIMITER ;
