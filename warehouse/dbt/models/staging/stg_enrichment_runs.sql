SELECT
    run_id
    , started_at
    , finished_at
    , mode
    , prompt_version
    , prompt_hash
    , model
    , tickets_seen
    , distinct_texts
    , cache_hits
    , sent
    , succeeded
    , errored
    , input_tokens
    , output_tokens
    , cost_usd
    , batch_id
FROM READ_JSON(
    '{{ var("runs_path") }}'
    , format = 'newline_delimited'
    , columns = {
        run_id: 'VARCHAR'
        , started_at: 'TIMESTAMP'
        , finished_at: 'TIMESTAMP'
        , mode: 'VARCHAR'
        , prompt_version: 'VARCHAR'
        , prompt_hash: 'VARCHAR'
        , model: 'VARCHAR'
        , tickets_seen: 'INTEGER'
        , distinct_texts: 'INTEGER'
        , cache_hits: 'INTEGER'
        , sent: 'INTEGER'
        , succeeded: 'INTEGER'
        , errored: 'INTEGER'
        , input_tokens: 'BIGINT'
        , output_tokens: 'BIGINT'
        , cost_usd: 'DECIMAL(12, 6)'
        , batch_id: 'VARCHAR'
    }
)
