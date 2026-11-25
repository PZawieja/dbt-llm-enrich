-- Redact before hashing: the hash is the cache key and the redacted text is
-- exactly what reaches the model, so no email or phone number leaves the warehouse.
WITH redacted AS (
    SELECT
        ticket_id
        , account_id
        , channel
        , created_at
        , updated_at
        , TRIM(subject) AS subject
        , REGEXP_REPLACE(
            REGEXP_REPLACE(
                TRIM(body), '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[email]', 'g'
            )
            , '\+\d[\d ()-]{6,}\d'
            , '[phone]'
            , 'g'
        ) AS body_redacted
    FROM {{ ref('raw_tickets') }}
)

SELECT
    ticket_id
    , account_id
    , channel
    , created_at
    , updated_at
    , subject
    , body_redacted
    , 'Subject: ' || subject || CHR(10) || CHR(10) || body_redacted AS ticket_text
    , SHA256('Subject: ' || subject || CHR(10) || CHR(10) || body_redacted) AS content_hash
FROM redacted
