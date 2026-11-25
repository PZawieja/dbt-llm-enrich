import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

import yaml

SEED = 20261215
ROOT = Path(__file__).parent
SEEDS_DIR = ROOT / "dbt" / "seeds"
START = datetime(2026, 5, 1, 7, 0)
END = datetime(2026, 10, 31, 19, 0)
N_TICKETS = 600
N_ACCOUNTS = 80
N_DUPLICATES = 30
N_EDITS = 20
N_INJECTIONS = 12
GOLDEN_SIZE = 150
GOLDEN_NATIVE = 24

CATEGORY_WEIGHTS = {
    "billing": 18,
    "bug": 20,
    "access": 14,
    "feature_request": 12,
    "how_to": 14,
    "cancellation": 8,
    "data_export": 7,
    "other": 7,
}

COUNTRIES = [
    ("US", "en", 26),
    ("GB", "en", 12),
    ("IE", "en", 4),
    ("NL", "en", 6),
    ("DE", "de", 10),
    ("FR", "fr", 8),
    ("ES", "es", 7),
    ("PL", "pl", 7),
]
NATIVE_LANGUAGE_SHARE = 0.25

PLANS = ["Starter", "Growth", "Scale"]

T = yaml.safe_load((ROOT / "ticket_templates.yml").read_text())
EN = T["en"]
NATIVE = T["native"]
GREETINGS = T["greetings"]
SIGNOFFS = T["signoffs"]
PHONES = T["phones"]
CHURN_PHRASES = T["churn_phrases"]
INJECTIONS = T["injections"]
EDIT_UPDATES = T["edit_updates"]
N = T["names"]
NAME_A, NAME_B = N["company_words_a"], N["company_words_b"]
FIRST, LAST = N["first_names"], N["last_names"]
FEATURES, CLIENTS = N["features"], N["clients"]
CHURN_ELIGIBLE = {"billing", "bug", "access", "feature_request"}
INJECTION_SOURCES = {"bug", "access", "billing"}
EDIT_SOURCES = {"billing", "bug", "access", "data_export"}


def fill(text: str, rng: random.Random, plan: str, language: str) -> str:
    day = START + timedelta(days=rng.randint(0, 180))
    amount = rng.choice([29, 49, 79, 129, 249, 499])
    return text.format(
        plan=plan,
        date=day.strftime("%d %B") if language == "en" else day.strftime("%d.%m.%Y"),
        amount=f"{amount}.00" if language == "en" else f"{amount},00",
        client=rng.choice(CLIENTS),
        feature=rng.choice(FEATURES).capitalize(),
        invoice=f"INV-2026-{rng.randint(100, 999):04d}",
    )


def make_accounts(rng: random.Random) -> list[dict]:
    weights = [w for _, _, w in COUNTRIES]
    names = [f"{a} {b}" for a in NAME_A for b in NAME_B]
    rng.shuffle(names)
    accounts = []
    for i in range(N_ACCOUNTS):
        country, language, _ = rng.choices(COUNTRIES, weights=weights)[0]
        accounts.append(
            {
                "account_id": f"A-{1001 + i}",
                "account_name": names[i],
                "country": country,
                "native_language": language,
                "plan": rng.choices(PLANS, weights=[45, 40, 15])[0],
                "seats": rng.randint(1, 40),
                "signed_up_on": (
                    datetime(2023, 1, 1) + timedelta(days=rng.randint(0, 1150))
                ).date(),
            }
        )
    return accounts


def pick_language(rng: random.Random, account: dict, category: str) -> str:
    native = account["native_language"]
    if native == "en" or category not in NATIVE[native]:
        return "en"
    return native if rng.random() < NATIVE_LANGUAGE_SHARE else "en"


def make_ticket(rng: random.Random, n: int, account: dict, created: datetime) -> dict:
    category = rng.choices(list(CATEGORY_WEIGHTS), weights=CATEGORY_WEIGHTS.values())[0]
    language = pick_language(rng, account, category)
    templates = EN[category] if language == "en" else NATIVE[language][category]
    tpl = rng.choice(templates)
    subject, core = tpl["subject"], tpl["body"]
    urgency, sentiment = tpl["urgency"], tpl["sentiment"]
    churn = category == "cancellation"
    parts = [fill(core, rng, account["plan"], language)]
    eligible = category in CHURN_ELIGIBLE and sentiment != "positive"
    if language == "en" and eligible and rng.random() < 0.14:
        parts.append(rng.choice(CHURN_PHRASES))
        churn = True
        sentiment = "negative"
    first, last = rng.choice(FIRST), rng.choice(LAST)
    slug = account["account_name"].lower().replace(" & ", "-").replace(" ", "")
    contact = f"{first.lower()}@{slug}.example"
    if rng.random() < 0.3:
        contact += " / " + PHONES[account["country"]].format(
            nn=f"{rng.randint(0, 99):02d}"
        )
    greeting = rng.choice(GREETINGS[language])
    body = "\n\n".join(
        p
        for p in [
            greeting,
            " ".join(parts),
            f"{rng.choice(SIGNOFFS[language])}\n{first} {last}\n{contact}",
        ]
        if p
    )
    if rng.random() < 0.06:
        body = body.lower()
    return {
        "ticket_id": f"T-{10001 + n}",
        "account_id": account["account_id"],
        "channel": rng.choices(["email", "web_form", "chat"], weights=[55, 30, 15])[0],
        "created_at": created,
        "updated_at": created,
        "subject": subject,
        "body": body,
        "_category": category,
        "_urgency": urgency,
        "_sentiment": sentiment,
        "_churn_signal": churn,
        "_language": language,
        "_trap": "",
    }


def inject(rng: random.Random, ticket: dict, line: str) -> None:
    head, sep, signoff = ticket["body"].rpartition("\n\n")
    ticket["body"] = f"{head}\n\n{line}{sep}{signoff}"
    ticket["_trap"] = "injection"


def build(before_edits: bool) -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)
    accounts = make_accounts(rng)
    span = (END - START).total_seconds()
    times = sorted(
        START + timedelta(seconds=rng.random() * span) for _ in range(N_TICKETS)
    )
    tickets = [
        make_ticket(rng, i, rng.choice(accounts), times[i])
        for i in range(N_TICKETS - N_DUPLICATES)
    ]

    injectable = [
        t
        for t in tickets
        if t["_category"] in INJECTION_SOURCES and t["_urgency"] == "high"
    ]
    for i, t in enumerate(rng.sample(injectable, N_INJECTIONS)):
        inject(rng, t, INJECTIONS[i % len(INJECTIONS)])

    for _ in range(N_DUPLICATES):
        original = rng.choice(
            [t for t in tickets[: len(tickets) // 2] if not t["_trap"]]
        )
        dup = dict(original)
        dup["ticket_id"] = f"T-{10001 + len(tickets)}"
        dup["created_at"] = original["created_at"] + timedelta(
            minutes=rng.randint(2, 90)
        )
        dup["updated_at"] = dup["created_at"]
        dup["channel"] = rng.choice(["email", "web_form"])
        dup["_trap"] = "duplicate"
        tickets.append(dup)

    editable = [t for t in tickets if t["_category"] in EDIT_SOURCES and not t["_trap"]]
    for t in rng.sample(editable, N_EDITS):
        t["_trap"] = "edited"
        if before_edits:
            continue
        t["body"] = f"{t['body']}\n\n{rng.choice(EDIT_UPDATES)}"
        t["updated_at"] = t["created_at"] + timedelta(days=rng.randint(1, 4))
        t["_urgency"] = "high"
        t["_sentiment"] = "negative"

    tickets.sort(key=lambda t: t["created_at"])
    return accounts, tickets


def golden_sample(tickets: list[dict]) -> list[dict]:
    rng = random.Random(SEED + 1)
    injections = [t for t in tickets if t["_trap"] == "injection"]
    native = [
        t
        for t in tickets
        if t["_language"] != "en" and t not in injections and t["_trap"] != "duplicate"
    ]
    must = injections + rng.sample(native, GOLDEN_NATIVE)
    rest = [
        t
        for t in tickets
        if t not in must and t["_language"] == "en" and t["_trap"] != "duplicate"
    ]
    by_cat: dict[str, list[dict]] = {}
    for t in rest:
        by_cat.setdefault(t["_category"], []).append(t)
    picked = list(must)
    per_cat = (GOLDEN_SIZE - len(picked)) // len(by_cat)
    for cat in sorted(by_cat):
        picked += rng.sample(by_cat[cat], min(per_cat, len(by_cat[cat])))
    leftovers = [t for t in rest if t not in picked]
    picked += rng.sample(leftovers, GOLDEN_SIZE - len(picked))
    return sorted(picked, key=lambda t: t["ticket_id"])


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--before-edits",
        action="store_true",
        help="write tickets as they were before 20 customers added an update",
    )
    parser.add_argument("--golden-candidates", type=Path)
    args = parser.parse_args()

    accounts, tickets = build(args.before_edits)
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        SEEDS_DIR / "raw_accounts.csv",
        accounts,
        ["account_id", "account_name", "country", "plan", "seats", "signed_up_on"],
    )
    write_csv(
        SEEDS_DIR / "raw_tickets.csv",
        tickets,
        [
            "ticket_id",
            "account_id",
            "channel",
            "created_at",
            "updated_at",
            "subject",
            "body",
        ],
    )
    if args.golden_candidates:
        rows = [
            {
                "ticket_id": t["ticket_id"],
                "category": t["_category"],
                "urgency": t["_urgency"],
                "sentiment": t["_sentiment"],
                "churn_signal": str(t["_churn_signal"]).lower(),
                "language": t["_language"],
                "trap": t["_trap"],
            }
            for t in golden_sample(tickets)
        ]
        write_csv(args.golden_candidates, rows, list(rows[0]))
    traps = {
        k: sum(t["_trap"] == k for t in tickets)
        for k in ("duplicate", "edited", "injection")
    }
    langs = {}
    for t in tickets:
        langs[t["_language"]] = langs.get(t["_language"], 0) + 1
    print(
        f"{len(accounts)} accounts, {len(tickets)} tickets, "
        f"traps {traps}, languages {langs}"
    )


if __name__ == "__main__":
    main()
