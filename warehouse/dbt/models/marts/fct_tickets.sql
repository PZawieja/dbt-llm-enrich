SELECT
    t.ticket_id
    , t.account_id
    , t.channel
    , t.created_at
    , t.updated_at
    , t.subject
    , t.content_hash
    , c.classification_status
    , c.category
    , c.urgency
    , c.sentiment
    , c.churn_signal
    , c.language
    , c.prompt_version
    , c.model
    , c.run_id
FROM {{ ref('stg_tickets') }} AS t
INNER JOIN {{ ref('int_ticket_classifications') }} AS c
    ON t.ticket_id = c.ticket_id
