SELECT
    ticket_id
    , category
    , urgency
    , sentiment
    , churn_signal
    , language
    , NULLIF(trap, '') AS trap
FROM {{ ref('golden_ticket_labels') }}
