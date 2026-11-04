# P0 — Mortgage Market Entry: HMDA Data Warehouse

## Business Case
**Lakeshore Bank USA** is the US arm of a fictional Canadian bank. It writes home-purchase mortgages in New York today, and its board has approved a push into one new state in 2027. The two candidates are **Ohio** and **North Carolina**.

The Chief Lending Officer needs three things before choosing a state: where buyers are applying, who Lakeshore would be competing against, and what it would take to win business. The Fair Lending Officer adds a fourth condition. Lakeshore must not walk into a market where approval gaps between neighbourhoods would expose it to regulatory risk.

**What that means.** US fair lending law (the Fair Housing Act, the Equal Credit Opportunity Act and the Community Reinvestment Act) bars lenders from treating neighbourhoods differently because of who lives there. Regulators check for this with the same HMDA data used here: they compare a bank's approval rates and application volumes in lower-income and majority-minority census tracts against richer ones, and against what other lenders in the same area achieve. A large unexplained gap can lead to a redlining investigation, fines, and a poor CRA rating that blocks future mergers and branch openings. The county shortlist must weigh fair lending exposure alongside demand and pricing. A county with strong demand but a severe neighbourhood approval gap is not automatically ruled out, but it carries a compliance cost that Question 5 is meant to measure.

The answer comes from three years of public federal mortgage data (HMDA, 2023 to 2025), covering every home-purchase application made in both states.

**The five questions**

1. **Demand:** Which counties have the most home-purchase applications, and where are they growing fastest?
2. **Competition:** Which lenders hold each market, and how has the competitive field changed as lenders merged, renamed or switched regulators?
3. **Approval:** Why are applications denied, and how does that differ by loan product (conventional, FHA, VA)?
4. **Pricing:** Where are borrowers paying the most above the benchmark rate, signalling room for a competitive new entrant?
5. **Risk:** Where do approval rates differ sharply between lower- and higher-income neighbourhoods, which Lakeshore would need to plan around?

**The deliverable** is a recommendation: which state to enter, the five counties to start in, and the loan products to lead with.

## Non-sensitive by design

The public HMDA files are already modified to protect privacy (for example, loan amounts are rounded to $10,000 bands). This project goes further: it leaves out every column that describes the applicant's demographics, so no finding or recommendation rests on who an applicant is. Race, ethnicity, sex and age are all protected under US fair lending law, and the client's questions do not need them.

Columns dropped deliberately:

| Group | Raw columns |
| --- | --- |
| Race | `derived_race`, `applicant_race-1` to `-5`, `co-applicant_race-1` to `-5`, `applicant_race_observed`, `co-applicant_race_observed` |
| Ethnicity | `derived_ethnicity`, `applicant_ethnicity-1` to `-5`, `co-applicant_ethnicity-1` to `-5`, `applicant_ethnicity_observed`, `co-applicant_ethnicity_observed` |
| Sex | `derived_sex`, `applicant_sex`, `co-applicant_sex`, `applicant_sex_observed`, `co-applicant_sex_observed` |
| Age | `applicant_age`, `co-applicant_age`, `applicant_age_above_62`, `co-applicant_age_above_62` |

None of these columns are listed in `lar_columns` in `config.yaml`, so they never reach BigQuery, staging or the rejects table. The duplicate check briefly reads whole raw rows in memory, so two applications that differ only in these columns are not mistaken for duplicates, but nothing from those columns is stored.

What remains describes the neighbourhood, not the person: `tract_to_msa_income_percentage`, `tract_minority_population_percent` and `tract_population` are census-tract figures. The fair-lending question (Q5) compares approval rates between lower- and higher-income tracts. Results are reported as an *approval gap*, never as discrimination: the data cannot show cause.

## Dataset

Public loan-level mortgage data published under the Home Mortgage Disclosure Act (HMDA), from the FFIEC [HMDA Data Browser](https://ffiec.cfpb.gov/data-browser/) ([API documentation](https://ffiec.cfpb.gov/documentation/api/data-browser/)). No key is needed.

| Source | Format | Files | Becomes |
| --- | --- | --- | --- |
| Loan application register (LAR) | CSV, 99 columns | one per state and year: Ohio and North Carolina, 2023 to 2025 | `stg_lar` |
| HMDA filers (lender names) | JSON | one per state and year | `stg_filers` |
| [Census county FIPS reference](https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt) | pipe-delimited text | one | `stg_counties` |

The job keeps only home-purchase, first-lien, owner-occupied, single-family, non-business applications, and drops loans bought from other lenders (action 6). Those rules live in `filters` in `config.yaml`. Of 2,919,828 raw rows, 1,010,939 are in scope; 996,397 load into staging and 14,542 go to rejects.

## Running it from a fresh clone

Tested with Python 3.13; pandas 3 needs Python 3.11 or later.

**1. Install**

```bash
git clone https://github.com/2494-Gen-AI-CN/BadrAl-Dhaibani.git
cd BadrAl-Dhaibani/projects/P0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**2. Credentials**

The free [BigQuery sandbox](https://cloud.google.com/bigquery/docs/sandbox) is enough: a Google account, no billing account or credit card. Create a Google Cloud project, then:

```bash
cp .env.example .env               # .env is git-ignored; never commit it
# edit .env and set GCP_PROJECT=<your project id>
gcloud auth application-default login
```

Credentials come from your own gcloud login, never from a file in the repository. To use a service-account key instead, keep the key file outside the repository and point `GOOGLE_APPLICATION_CREDENTIALS` in `.env` at it.

**3. Download the raw files**

The raw files are not in the repository. This script fetches the 12 HMDA files and the county reference into `data/raw/` (about 1.1 GB):

```bash
./scripts/download.sh            # skips files that already exist
./scripts/download.sh --force    # re-download everything
python3 scripts/row_counts.py    # optional: check row counts against the HMDA API (about 30 s)
```

Every `match` column from `row_counts.py` should read `yes`.

**4. Run the ingestion job**

```bash
PYTHONPATH=src python -m hmda.run            # load new or changed files, skip the rest
PYTHONPATH=src python -m hmda.run --force    # reload every file
```

The job creates the `hmda_staging` dataset if it is missing, and exits non-zero if any file failed; the other files still load.

**5. Run the tests**

```bash
python -m pytest
```

None of the tests connect to BigQuery: the load is tested against an in-memory warehouse.

## How the load works

Each source file loads into its own table in `hmda_staging` (for example `stg_lar__lar_oh_2024`), which is replaced whole when the file changes. The views `stg_lar`, `stg_filers`, `stg_counties` and `rejects` stack those tables, so queries read one table each. The load uses no `DELETE` or `UPDATE` statements, which the BigQuery sandbox does not allow.

Every run appends one row per source file to `load_log`:

| Column | Meaning |
| --- | --- |
| `run_id` | when the run started, in UTC, e.g. `2026-11-03T16:40:21Z` |
| `source_name`, `file_sha256` | which file, and a fingerprint of its contents |
| `rows_read` | rows in the file |
| `rows_filtered` | rows outside the scope filter: counted, not rejected |
| `rows_rejected` | rows sent to `rejects`, with one count column per reason (`rows_missing_key`, `rows_duplicate`, ...) |
| `rows_loaded` | rows written to staging |
| `status`, `error` | `loaded`, `skipped` or `failed`, and the error message for a failed file |

**Running the job twice adds no data.** A file whose fingerprint matches its last successful load is skipped. The second run still appends one `skipped` row per file to `load_log`, as an audit trail, but staging is unchanged. A failed file is retried on the next run.

The skip check looks only at the file's contents. After changing the code or `config.yaml`, run with `--force` so every file is reloaded under the new rules.

## Cleansing rules

All cleaning happens in pandas, in `src/hmda/clean.py`. Each rule has pytest tests.

**Reject rules** send the row to `rejects` with the rule's name as `reject_reason` and the row's kept columns as JSON in `raw_record`. The first failing rule wins.

| Reason | Rule | Rows in the current load |
| --- | --- | --- |
| `missing_key` | `lei`, `county_code`, `census_tract` or `action_taken` is empty, `NA` or `Exempt` | 14,040 |
| `bad_lei` | `lei` is not 20 upper-case letters or digits | 0 |
| `tract_county_mismatch` | `census_tract` does not start with `county_code` | 0 |
| `bad_loan_amount` | `loan_amount` is not a number above 0 | 0 |
| `duplicate` | identical in every raw column to an earlier row in the same file (see below) | 502 |
| `duplicate_filer` | a second name for the same lender (`lei`) and year in a filers file; the first is kept | 0 |

**Fix rules** keep the row and clean the value:

| Field | Rule |
| --- | --- |
| Coded fields (`action_taken`, `loan_type`, denial reasons, ...) | `NA`, `Exempt`, empty, `1111`, `8888` and `9999` (HMDA's exempt / not-reported codes) become null |
| Continuous fields (`income`, `loan_amount`, `rate_spread`, ...) | `NA`, `Exempt` and empty become null; `8888` is kept because it can be a real value |
| Types | coded fields become integers, continuous fields decimals; keys (`lei`, `county_code`, `census_tract`) stay text |
| `income` | negative values become null; the row stays but drops out of income ratios |
| `debt_to_income_ratio` | HMDA mixes ranges (`20%-<30%`) with single values (`36` to `49`); all are mapped to `<20%`, `20%-<30%`, `30%-<36%`, `36%-<43%`, `43%-<50%`, `50%-60%`, `>60%`. An unknown value fails the file rather than guessing. |
| `interest_rate`, `rate_spread` | null unless the loan was originated (`action_taken = 1`), since rates only exist for originated loans |
| Filer names | leading and trailing spaces trimmed |
| Counties | only the states listed in `config.yaml` are kept; `county_code` is built from the state and county FIPS codes to match the LAR |
| Column names | hyphens become underscores for BigQuery (`denial_reason-1` → `denial_reason_1`) |

A file missing an expected column fails as a whole and is logged as `failed`. Apart from `loan_amount`, which is rejected, a non-numeric value in a numeric field becomes null rather than being rejected.

### The duplicate trap

HMDA has no application ID, and the public file rounds and buckets values to protect privacy (loan amounts to $10,000 bands, for example). Two genuine applications can therefore look identical. To keep that risk low, the duplicate rule compares all 99 raw columns, including the demographic columns the project otherwise drops, rather than only the columns kept. The current load rejects 502 rows as duplicates, 0.05% of in-scope rows. Some of these may be real applications that happen to match, so the true number of duplicate records is at most 502.

## Team

Tristan Nguyen and Badr Al-Dhaibani. This hand-in lives in Badr's learner repository; Tristan's is [2494-Gen-AI-CN/TristanNguyen](https://github.com/2494-Gen-AI-CN/TristanNguyen).
