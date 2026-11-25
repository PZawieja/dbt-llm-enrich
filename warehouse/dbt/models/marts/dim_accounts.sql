SELECT
    a.account_id
    , a.account_name
    , a.country
    , a.plan
    , a.seats
    , a.signed_up_on
    , COUNT(t.ticket_id) AS tickets
    , COUNT(t.ticket_id) FILTER (WHERE t.churn_signal) AS churn_signal_tickets
FROM {{ ref('stg_accounts') }} AS a
LEFT JOIN {{ ref('fct_tickets') }} AS t
    ON a.account_id = t.account_id
GROUP BY ALL
