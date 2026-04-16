## v0.7.1 (2026-04-16)

### Fix

- Fix scraper URLs, ICA scraper WAF loop, subcategory paths, and type errors.

## v0.7.0 (2026-04-12)

### Feat

- Fix ICA scraper, product variant deduplication, and added a README file.

## v0.6.0 (2026-04-01)

### Feat

- Added tests for shelfwatch, modified matval_core tests.

## v0.5.1 (2026-03-19)

### Fix

- Observed several bugs that I've done when I've switched from stores to supermarkets. I've also forgotten to modify from stores to supermarkets in one instance and I've written supermarket instead of supermarkets which would cause errors. This was observed when I wanted to start writing tests.

## v0.5.0 (2026-03-16)

### Feat

- Migrated the build toolchain from hatchling to uv_build. Required python 3.13 across all pyproject.toml files. Consolidated all the tests inside one single folder named tests. Upgraded DockerFiles to use a slim version of Python 3.13 and switch from importing the entire matval_pipeline to matval_core (should probably switch it to db only).

## v0.4.1 (2026-03-15)

### Fix

- Added integration tests for connector.py, dev_ops.py and pipelines.py.

## v0.4.0 (2026-03-12)

### Feat

- Modified the mathem scraper as json structure was modified.

## v0.3.2 (2026-03-11)

### Fix

- Refactored the redundant PostgresConfig class from connector.py and switched the PipelineConfig class to the PostgresConfig one. Modified pipeline.py as well to use only one Config class.

## v0.3.1 (2026-03-11)

### Fix

- Refactored config.py from matval_pipeline for testing purposes. Added tests for config.py under test_config.py

## v0.3.0 (2026-03-09)

### Feat

- Unit tests for normalizers.py are added. The currency map from normalizers was moved to a config folder in currency_aliases.json as that will undoutebly grow in time. seed_database.sql was removed, because the pipeline creates or retrieves a new supermarket when a spider is run. It was also removed from docker-compose.yml. All the type hints were fixed. Next steps: Figure out how to test the pipeline.py, db_ops.py, and connector.py (docker with postgress possibly, but I'll have to see how I deal with the coverage in this case), test the crawlers with contracts, but custom contracts are needed in this case.

## v0.2.6 (2026-03-08)

### Fix

- Finalized fixing type hints.

## v0.2.5 (2026-03-04)

### Fix

- Fixed multiple type hints, no untyped definitions, wrong argument types: 14 remaining.

## v0.2.4 (2026-03-04)

### Fix

- Fixed multiple type hints errors: 54 left.

## v0.2.3 (2026-03-02)

### Fix

- Resolved multiple missing type hints, 115 to go.

## v0.2.2 (2026-03-01)

### Fix

- Fixed several type hint issues, 156 left to go. Added workspaces to connect the isolated pyproject.toml to the main one.

## v0.2.1 (2026-03-01)

### Fix

- Performed linting and formating checks and fixes on all files.

## v0.2.0 (2026-02-25)

### Feat

- Replaced requirements.txt with pyproject.toml. Added a root manifest.
- Modified server.py to use supermarkets table and supermarkets_id column (matval_pipeline will be modified as well). The change from stores to supermarkets comes from the fact that there can be multiple store_locations for a supermarket. Noticed that tests are missing for everything which I will add, starting with normalizers (pytest and pytest-cov will be added). Noticed that format, lint and type hint checks are missing (ruff, mypy and pre-commit hooks shall be added).
- Removed one update SQL Schema as it was redundant. Inside schema.sql the stores table is renamed to supermarkets, because a supermarket can have multiple store locations with their unqiue store_id (ex: ica, willys, hemkop) if they are not online stores such as mathem. Modified 02-seed-stores.sqlto seed-supermarkets.sql due to the table name change. Refactored the sql query to perform INSERTS with auto-incrementing id.
- Added price/availability history trigger and MCP tool.
- First commit.

### Fix

- Starting deslopification
- Corrected the price extraction for the COOP scraper
- Noticed that the DOWNLOAD_DELAY for willys and hemkop were set at 0.5 so I switched it at 10 for compliance with robots.txt
