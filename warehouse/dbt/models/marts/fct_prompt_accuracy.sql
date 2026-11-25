-- One row per prompt version and label: how often that version agrees with the
-- hand-reviewed golden labels. Every version still in the cache is scored, so a
-- prompt change shows up here as a before and after.
WITH golden AS (
    SELECT
        g.*
        , t.content_hash
    FROM {{ ref('stg_golden_ticket_labels') }} AS g
    INNER JOIN {{ ref('stg_tickets') }} AS t
        ON g.ticket_id = t.ticket_id
)

, predictions AS (
    SELECT *
    FROM {{ ref('stg_llm_classifications') }}
    WHERE model = '{{ var("model") }}'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY prompt_version, content_hash ORDER BY classified_at DESC
    ) = 1
)

, scored AS (
    SELECT
        p.prompt_version
        , g.ticket_id
        , g.trap
        , p.category = g.category AS category_ok
        , p.urgency = g.urgency AS urgency_ok
        , p.sentiment = g.sentiment AS sentiment_ok
        , p.churn_signal = g.churn_signal AS churn_signal_ok
        , p.language = g.language AS language_ok
    FROM golden AS g
    INNER JOIN predictions AS p
        ON g.content_hash = p.content_hash
)

, unpivoted AS (
    UNPIVOT scored
    ON category_ok, urgency_ok, sentiment_ok, churn_signal_ok, language_ok
    INTO NAME label_column VALUE is_correct
)

SELECT
    prompt_version
    , REPLACE(label_column, '_ok', '') AS label_name
    , COUNT(*) AS golden_tickets
    , COUNT(*) FILTER (WHERE is_correct) AS correct
    , ROUND(COUNT(*) FILTER (WHERE is_correct) / COUNT(*), 4) AS accuracy
    , ROUND(
        COUNT(*) FILTER (WHERE is_correct AND trap = 'injection')
        / NULLIF(COUNT(*) FILTER (WHERE trap = 'injection'), 0)
        , 4
    ) AS injection_accuracy
FROM unpivoted
GROUP BY ALL
