{% test min_accuracy(model, column_name, golden, golden_column, threshold) %}
-- A golden ticket with no prediction counts as wrong: a missing result is not
-- a right answer.
WITH scored AS (
    SELECT COALESCE(m.{{ column_name }} = g.{{ golden_column }}, FALSE) AS is_correct
    FROM {{ golden }} AS g
    LEFT JOIN {{ model }} AS m
        ON g.ticket_id = m.ticket_id
)

SELECT
    COUNT(*) AS golden_tickets
    , COUNT(*) FILTER (WHERE is_correct) AS correct
    , COUNT(*) FILTER (WHERE is_correct) / COUNT(*) AS accuracy
FROM scored
HAVING COUNT(*) FILTER (WHERE is_correct) / COUNT(*) < {{ threshold }}
{% endtest %}
