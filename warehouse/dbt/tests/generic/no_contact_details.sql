{% test no_contact_details(model, column_name) %}
SELECT {{ column_name }}
FROM {{ model }}
WHERE
    REGEXP_MATCHES({{ column_name }}, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
    OR REGEXP_MATCHES({{ column_name }}, '\+\d[\d ()-]{6,}\d')
{% endtest %}
