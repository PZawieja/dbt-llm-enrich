-- read_json with an explicit column list so a fresh clone with an empty cache
-- still builds.
SELECT
    cache_key
    , content_hash
    , prompt_version
    , prompt_hash
    , model
    , category
    , urgency
    , sentiment
    , churn_signal
    , language
    , run_id
    , classified_at
    , input_tokens
    , output_tokens
FROM READ_JSON(
    '{{ var("classifications_path") }}'
    , format = 'newline_delimited'
    , columns = {
        cache_key: 'VARCHAR'
        , content_hash: 'VARCHAR'
        , prompt_version: 'VARCHAR'
        , prompt_hash: 'VARCHAR'
        , model: 'VARCHAR'
        , category: 'VARCHAR'
        , urgency: 'VARCHAR'
        , sentiment: 'VARCHAR'
        , churn_signal: 'BOOLEAN'
        , language: 'VARCHAR'
        , run_id: 'VARCHAR'
        , classified_at: 'TIMESTAMP'
        , input_tokens: 'INTEGER'
        , output_tokens: 'INTEGER'
    }
)
