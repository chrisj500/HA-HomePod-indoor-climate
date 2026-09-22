# Release process

HomePod Indoor Climate uses published GitHub Releases as the authoritative versions exposed to HACS.

## Rules

1. Any change under `custom_components/homepod_indoor_climate/` must use a manifest version that has not already been released.
2. Update `custom_components/homepod_indoor_climate/manifest.json` as part of the same pull request as the integration change.
3. Pull requests must pass HACS validation, hassfest, tests, and the version gate.
4. After a validated change reaches `main`, GitHub Actions publishes the manifest version as a GitHub Release automatically.
5. Published release tags are immutable historical points. Never move or reuse a released version.
6. Documentation or workflow-only changes do not create a new integration release.

## Historical releases

The release workflow backfills the original stable versions using release-snapshot commits:

- `v0.1.0` -> `75caa2748c141401209a2473eec0d6085feccfa2`
- `v0.1.1` -> `be220ff4163f76c255cfda6e542d8aa154b5b7c7`
- `v0.1.2` -> the current validated `main` snapshot used for the backfill.

The v0.1.0 and v0.1.1 snapshot branches preserve the exact historical integration contents under `custom_components/homepod_indoor_climate/`. Their workflow file is aligned with current `main` only to satisfy GitHub's release-token restrictions for historical commits. This does not change the integration payload HACS installs.

The backfill is idempotent: if a release already exists, the workflow leaves it untouched.

## HACS rollback

HACS reads published GitHub Releases and exposes them in the repository's version selector. To roll back an installed integration:

1. In HACS, open the repository menu and choose **Redownload**.
2. Under **Need a different version?**, choose the desired published release.
3. Download it and restart Home Assistant.

A manifest version alone is not a HACS release. Publishing the GitHub Release is therefore part of the release definition, not an optional follow-up step.
