# Data-licensing checklist

Engineering checklist. **Not legal advice.** Before enabling any real
provider in a non-demo environment, walk through this list and file the
answer in this document (or a per-provider sub-doc).

- [ ] Do we have a written contract / accepted click-through ToS for this
      provider?
- [ ] Do those terms permit our intended use (research, watchlist,
      research chat, backtesting)?
- [ ] Do they permit **display** of the data to end users, or only
      internal use?
- [ ] Do they permit **caching** to Postgres? For how long?
- [ ] Do they permit **redistribution** through our public API?
- [ ] What is the **required attribution** text and placement?
- [ ] Are there symbol coverage restrictions or per-symbol fees?
- [ ] Are there rate limits we must not exceed?
- [ ] Is there an audit right we must honor (e.g. exchange usage
      reporting)?
- [ ] Is real-time / delayed status of the feed clearly displayed?

## Phase 1 status

The only enabled adapter is the deterministic mock provider. It
generates its own values from a hash and carries no third-party data —
so no licensing question applies.
