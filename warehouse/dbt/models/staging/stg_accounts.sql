SELECT
    account_id
    , account_name
    , country
    , plan
    , seats
    , signed_up_on
FROM {{ ref('raw_accounts') }}
