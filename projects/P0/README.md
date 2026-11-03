# P0 — Mortgage Market Entry: HMDA Data Warehouse

## Business Case
**Lakeshore Bank USA** is the US arm of a fictional Canadian bank. It writes home-purchase mortgages in New York today, and its board has approved a push into one new state in 2027. The two candidates are **Ohio** and **North Carolina**.

The Chief Lending Officer needs three things before choosing a state: where buyers are applying, who Lakeshore would be competing against, and what it would take to win business. The Fair Lending Officer adds a fourth condition. Lakeshore must not walk into a market where approval gaps between neighbourhoods would expose it to regulatory risk.

**What that means.** US fair lending law (the Fair Housing Act, the Equal Credit Opportunity Act and the Community Reinvestment Act) bars lenders from treating neighbourhoods differently because of who lives there. Regulators check for this with the same HMDA data used here: they compare a bank's approval rates and application volumes in lower-income and majority-minority census tracts against richer ones, and against what other lenders in the same area achieve. A large unexplained gap can lead to a redlining investigation, fines, and a poor CRA rating that blocks future mergers and branch openings. 

So the county shortlist must weigh fair lending exposure alongside demand and pricing. A county with strong demand but a severe neighbourhood approval gap is not automatically ruled out, but it carries a compliance cost that Question 5 is meant to measure.

The answer comes from three years of public federal mortgage data (HMDA, 2023 to 2025), covering every home-purchase application made in both states.

**The five questions**

1. **Demand:** Which counties have the most home-purchase applications, and where are they growing fastest?
2. **Competition:** Which lenders hold each market, and how has the competitive field changed as lenders merged, renamed or switched regulators?
3. **Approval:** Why are applications denied, and how does that differ by loan product (conventional, FHA, VA)?
4. **Pricing:** Where are borrowers paying the most above the benchmark rate, signalling room for a competitive new entrant?
5. **Risk:** Where do approval rates differ sharply between lower- and higher-income neighbourhoods, which Lakeshore would need to plan around?

**The deliverable** is a recommendation: which state to enter, the five counties to start in, and the loan products to lead with.

## Getting the data

The raw files are not in the repository. Download them with the script below; it fetches the HMDA loan application CSVs and filer JSONs for Ohio and North Carolina, 2023 to 2025, plus the Census county reference, into `data/raw/` (about 1.1 GB).

```bash
cd projects/P0
./scripts/download.sh            # skips files that already exist
./scripts/download.sh --force    # re-download everything
```

Then check the downloads against the HMDA API and see how many rows pass the ingest filter (Python 3 standard library only, takes about 30 seconds):

```bash
python3 scripts/row_counts.py
```

Every `match` column should read `yes`.
