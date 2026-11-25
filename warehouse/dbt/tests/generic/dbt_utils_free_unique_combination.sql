{% test dbt_utils_free_unique_combination(model, columns) %}
SELECT {{ columns | join(', ') }}
FROM {{ model }}
GROUP BY {{ columns | join(', ') }}
HAVING COUNT(*) > 1
{% endtest %}
