# Release a new version of LAP

Bump the version and publish to PyPI + npm.

## Arguments

- $ARGUMENTS: The new version number (e.g. "0.5.0"). If empty, ask the user.

## Steps

1. **Validate version**: Ensure the version argument is a valid semver string (X.Y.Z). If not provided or invalid, ask the user for the version number.

2. **Run tests first**: Run `PYTHONUTF8=1 python -m pytest tests/ -q --timeout=30` from the project root. If any tests fail, STOP and report the failures. Do not proceed with a broken build.

3. **Bump version in all files**:
   - `lap/__init__.py` -- update `__version__`
   - `pyproject.toml` -- update `version`
   - `sdks/typescript/package.json` -- update `version`

4. **Update CHANGELOG.md**: Add a new `## [X.Y.Z] - YYYY-MM-DD` section at the top (below the header). Ask the user for a summary of changes, or generate one from recent git log if the user says to auto-generate.

5. **Commit**: Stage the 4 changed files and commit with message: `chore: bump to vX.Y.Z with changelog`

6. **Push**: Push to origin/main.

7. **Create GitHub Release**: Run `gh release create vX.Y.Z --title "vX.Y.Z" --notes-file CHANGELOG_SECTION` where CHANGELOG_SECTION contains only the new version's changelog section.

8. **Monitor publish workflows**: After the release is created, poll the two workflow runs:
   - `Publish to PyPI`
   - `Publish to npm`

   Use `gh run list --limit 4` to find the run IDs, then use `gh run watch <run-id>` to monitor each. Report the final status of each workflow to the user (success/failure). If a workflow fails, show the failure logs using `gh run view <run-id> --log-failed`.

## Important

- Never skip tests before releasing
- All three version files must be in sync
- The GitHub release triggers the publish workflows via `on: release: types: [published]`
- Do not publish manually -- always use the GitHub Actions workflows
