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
    , DATEDIFF('second', started_at, finished_at) AS wall_seconds
    , ROUND(cache_hits / NULLIF(distinct_texts, 0), 4) AS cache_hit_rate
    , ROUND(1000 * cost_usd / NULLIF(succeeded, 0), 4) AS cost_per_1k_classified_usd
FROM {{ ref('stg_enrichment_runs') }}
