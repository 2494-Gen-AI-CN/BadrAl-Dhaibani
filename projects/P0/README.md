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

The public HMDA files are already modified to protect privacy (for example, loan amounts are rounded to $10,000 bands). This project goes further: it leaves out every column that describes the applicant's demographics, and the one that describes the neighbourhood's racial make-up, so no finding or recommendation rests on race, ethnicity, sex or age. All four are protected under US fair lending law, and the client's questions do not need them.

Columns dropped deliberately:

| Group | Raw columns |
| --- | --- |
| Race | `derived_race`, `applicant_race-1` to `-5`, `co-applicant_race-1` to `-5`, `applicant_race_observed`, `co-applicant_race_observed` |
| Ethnicity | `derived_ethnicity`, `applicant_ethnicity-1` to `-5`, `co-applicant_ethnicity-1` to `-5`, `applicant_ethnicity_observed`, `co-applicant_ethnicity_observed` |
| Sex | `derived_sex`, `applicant_sex`, `co-applicant_sex`, `applicant_sex_observed`, `co-applicant_sex_observed` |
| Age | `applicant_age`, `co-applicant_age`, `applicant_age_above_62`, `co-applicant_age_above_62` |
| Neighbourhood race and ethnicity | `tract_minority_population_percent`: the share of the census tract's residents who are not non-Hispanic white |

None of these columns are listed in `lar_columns` in `config.yaml`, so they never reach BigQuery, staging or the rejects table. The duplicate check briefly reads whole raw rows in memory, so two applications that differ only in these columns are not mistaken for duplicates, but nothing from those columns is stored.

A census tract is a small area the Census Bureau draws for statistics, usually 1,200 to 8,000 people, roughly a neighbourhood. `tract_minority_population_percent` is the same for every application in a tract and says nothing about the applicant, but it is still a measure of race and ethnicity, so it is left out with the applicant columns. It matters for a real fair lending review: regulators compare a bank's approvals in majority-minority tracts against other tracts. Lakeshore's compliance team would add it for that review. This project does not need it.

What remains describes the neighbourhood's income and size, not the person or the neighbourhood's racial make-up: `tract_to_msa_income_percentage` and `tract_population` are census-tract figures. The fair-lending question (Q5) compares approval rates between lower- and higher-income tracts. Results are reported as an *approval gap*, never as discrimination: the data cannot show cause.

## Dataset

Public loan-level mortgage data published under the Home Mortgage Disclosure Act (HMDA), from the FFIEC [HMDA Data Browser](https://ffiec.cfpb.gov/data-browser/) ([API documentation](https://ffiec.cfpb.gov/documentation/api/data-browser/)). No key is needed.
2
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

**5. Build the warehouse**

```bash
./scripts/build.sh
```

This runs `sql/build/*.sql` in order with the `bq` command-line tool, which comes with the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed for step 2. It creates the `hmda_dw` dataset if it is missing, rebuilds every table with `CREATE OR REPLACE`, and ends with checks that stop the build if any fail (see [The warehouse](#the-warehouse)). Rerunning it gives the same tables.

The analysis queries are in `sql/`, one file per question, and run on their own:

```bash
set -a; source .env; set +a
bq --project_id="$GCP_PROJECT" query --use_legacy_sql=false < sql/01_demand.sql
```

**6. Draw the charts**

```bash
PYTHONPATH=src python charts/make_charts.py             # query the warehouse, save CSVs and PNGs
PYTHONPATH=src python charts/make_charts.py --from-csv  # redraw from the saved CSVs, no BigQuery
```

The five PNGs land in `charts/`, and the data behind each one in `charts/data/` (see [Charts](#charts)).

**7. Run the tests**

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

`sql/00_load_log.sql` sums the latest successful load of each loan file. Its TOTAL row gives 2,919,828 rows read, 1,010,939 in scope, 14,542 rejected and 996,397 loaded.

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

## Features

Two columns are derived in Python (`src/hmda/features.py`, with pytest tests) and stored on every staging row, so the warehouse and the queries use them as they are.

| Feature | Rule | Used for |
| --- | --- | --- |
| `tract_income_band` | The tract's median family income as a % of its metro's median: below 80 is `Low/Moderate`, 80 to below 120 is `Middle`, 120 and up is `Upper` | Q5, the approval gap between lower- and higher-income neighbourhoods |
| `loan_to_income` | `loan_amount / (income × 1000)`, rounded to 2 places; `income` is reported in thousands of dollars | The correlation between how far buyers stretch and how often they are denied |

The 80% and 120% cut-offs are the low/moderate, middle and upper income levels regulators use in Community Reinvestment Act exams.

`tract_income_band` is null when the percentage is missing or 0. HMDA reports 0 for about 90 populated tracts a year whose census median income is not available (about 0.5% of rows), so 0 means unknown, not poor. `loan_to_income` is null when income is missing, zero or negative.

## The warehouse

`hmda_dw` is a star schema: one fact table with one row per application, and five dimensions it joins to through surrogate keys.

| Table | One row per | Rows | Holds |
| --- | --- | --- | --- |
| `fact_application` | application | 996,397 | outcome flags (`is_approved`, `is_denied`, `is_originated`), money fields, rate spread, both features |
| `dim_lender` | lender version | 1,377 | name and size tier, with `effective_from`, `effective_to` and `is_current` |
| `dim_geography` | census tract and metro area | 6,617 | tract, county name, state, metro area code |
| `dim_product` | loan type, lien and dwelling | 8 | `Conventional`, `FHA`, `VA`, `USDA`; site-built or manufactured home |
| `dim_outcome` | action taken and first denial reason | 15 | what happened, whether it was decided, and why it was denied |
| `dim_applicant_profile` | income, debt-to-income and loan-to-value band | 239 | bands with a sort order for charts |

Every code is mapped to a plain label in the dimensions, so no query or chart shows that loan type 2 means FHA. Keys are fingerprints of each dimension's natural key, so they stay the same when the warehouse is rebuilt. The view `lar_prepared` works out the bands and keys once, and the dimensions and the fact table are all built from it.

**Geography is keyed on tract and metro area together.** The 2024 update to federal metro area definitions moved 843 of the 5,774 tracts into a different metro, so the same tract can sit in two metros in different years. County and state never change for a tract.

**Applicant bands.** Income: `<$50k`, `$50k-<$100k`, `$100k-<$150k`, `$150k-<$250k`, `$250k+`. Loan-to-value: `<=80%` (where mortgage insurance starts), `>80%-90%`, `>90%-95%`, `>95%`. Debt-to-income uses the bands from cleaning. Each has a `Not reported` band.

### The lender history (type 2 dimension)

Each year's filers file gives one name per lender (LEI). The build compares each lender year with the one before. A change in the normalised name (upper case, single spaces) or in the size tier opens a new version. The new version's `effective_from` is 1 January of that year, the previous version's `effective_to` is the day before, and `is_current` moves to the new row. The fact table binds each application to the version valid in its year, so Q2 reports market share under the name each lender filed under that year.

Size tier counts the lender's home-purchase applications across both states that year: `National` is 2,000 or more, `Regional` is 200 or more, and anything below is `Local`.

In the real data 14 lenders changed name and there are 83 tier changes, so no change had to be invented. Some name changes are a switch between a trade name and a legal name, not a new company. For example, the lender filed as United Wholesale Mortgage in 2023 and as United Shore Financial Services, its legal name, in 2024 and 2025.

**Lenders with no name that year.** 19 lenders filed 728 applications (0.07%) in years when they have no row in the filers file. Their applications are kept, and the lender is named `UNKNOWN LENDER (<lei>)` with `name_in_filers = FALSE`. A name from another year is never borrowed, because it could be wrong for that year. Q2 does not count a change to or from an unknown name as a rename.

### Build checks

`sql/build/08_checks.sql` stops the build if any of these fail:

- `fact_application` has exactly as many rows as `stg_lar`, so no application is lost or doubled by a join.
- Every dimension key is unique, and every fact key finds its dimension row.
- Every lender has exactly one current version.
- Every code has a label.
- (In `06_dim_lender.sql`) the per-state filers files never give the same lender two different names in one year.

## Analysis queries

One file per client question in `sql/`, each opening with the question and what the answer means for Lakeshore. "Decided" means the lender made a decision: approved (originated, or approved but not accepted) or denied. Withdrawn and incomplete files stay out of approval and denial rates.

| File | Question |
| --- | --- |
| `01_demand.sql` | Which counties have the most applications, and where are they growing fastest (2023 to 2025)? |
| `02_competition.sql` | Which lenders hold each state, under the name they filed under that year (uses the lender history)? |
| `03_approval.sql` | Denial rate and top denial reason by loan type and debt-to-income band |
| `04_pricing.sql` | Median rate spread on 2025 conventional originations by county, with the number of active lenders |
| `05_risk.sql` | Approval gap between Upper and Low/Moderate-income tracts by county, 2025 |
| `06_correlation.sql` | Correlation between county median loan-to-income and denial rate, 2025 |

### Manufactured homes

All six queries count **site-built homes only**. Manufactured homes stay in the warehouse but are left out of the analysis, because they are a specialist market that Lakeshore would not enter and they distort every county comparison:

- In 2025 they were denied about 51% of the time, against 7 to 8% for site-built homes.
- A county's share of manufactured homes tracks its denial rate almost exactly (r = 0.95 in North Carolina, 0.91 in Ohio).
- They cluster in lower-income tracts, so they inflated the neighbourhood approval gaps. Pitt County's gap was 27.9 points with them and is 10.0 without; Craven County's fell from 23.8 to 7.4.
- They are written by specialist lenders. Vanderbilt Mortgage, which lends only on manufactured homes, was North Carolina's largest lender by applications when they were included.

### The correlation

Across counties, how far buyers borrow against their income barely predicts how often they are turned down: Pearson r is 0.13 across both states (120 counties), 0.13 in North Carolina and −0.24 in Ohio. Before manufactured homes were left out, r was −0.72 in North Carolina, but that measured the share of manufactured homes, which have small loans and high denial rates, not borrower stretch.

Even a strong r would not show cause. HMDA has no credit scores, house prices push up loan-to-income and may also change who applies, and the product mix (FHA against conventional) differs by county.

## Charts

`charts/make_charts.py` pulls each chart's data from the warehouse with the BigQuery Python client and draws it with Matplotlib, as a 16:9 PNG for the deck. Every title is written from the numbers, so it stays true if the data changes. The data behind each chart is saved as a CSV in `charts/data/`, which doubles as a table version of the chart.

| File | Shows | Data |
| --- | --- | --- |
| `01_demand.png` | 2025 applications in the ten largest counties per state, coloured by growth or decline since 2023 | `01_demand.sql` |
| `02_competition.png` | 2025 market share of the ten largest lenders per state, under the name each filed under that year, with name changes footnoted | `02_competition.sql`, `dim_lender` |
| `03_denials_by_dti.png` | Denial rate by debt-to-income band for conventional, FHA and VA loans | `03_approval.sql` |
| `04_correlation.png` | One dot per county: median loan-to-income against denial rate, with r for each state | the county points behind `06_correlation.sql` |
| `05_approval_gap.png` | Approval rate in Low/Moderate against Upper-income tracts, for counties with a gap of 5 points or more | `05_risk.sql` |

Colours come from a palette checked for colour-blind readers. Lines and dots are also labelled directly, so no chart depends on colour alone.

## Team

Tristan Nguyen and Badr Al-Dhaibani. Tristan's repo: [2494-Gen-AI-CN/TristanNguyen](https://github.com/2494-Gen-AI-CN/TristanNguyen).
