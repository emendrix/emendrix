# emendrix-service

The account service beside emendrix: email watchlists over the published change record. It
filters what the record already states and never re-derives it. It reads the record only
through `emendrix-record`, and the pipeline imports nothing of it.

> Not legal advice: this output is machine-computed from published texts, carries no lawyer's
> review, and is engineering assistance only.

`emendrix-service --help` lists its commands. Every setting is an `EMENDRIX_SERVICE_*`
environment variable, declared in `src/emendrix_service/settings.py`.
