-- Tickets with no result for the current prompt stay in as 'missing'. Dropping
-- them would quietly shrink every count downstream.
WITH current_results AS (
    SELECT *
    FROM {{ ref('stg_llm_classifications') }}
    WHERE
        prompt_version = '{{ var("prompt_version") }}'
        AND model = '{{ var("model") }}'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY content_hash ORDER BY classified_at DESC) = 1
)

SELECT
    t.ticket_id
    , t.content_hash
    , c.prompt_version
    , c.prompt_hash
    , c.model
    , c.category
    , c.urgency
    , c.sentiment
    , c.churn_signal
    , c.language
    , c.run_id
    , c.classified_at
    , CASE WHEN c.content_hash IS NULL THEN 'missing' ELSE 'classified' END
        AS classification_status
FROM {{ ref('stg_tickets') }} AS t
LEFT JOIN current_results AS c
    ON t.content_hash = c.content_hash
