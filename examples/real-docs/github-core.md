# GitHub Repositories API Documentation

Source: https://docs.github.com/en/rest/repos/repos (fetched 2026-02-08)

Use the REST API to manage repositories on GitHub.

## List organization repositories

`GET /orgs/{org}/repos`

Lists repositories for the specified organization.

### Parameters

**Headers:**
- accept (string): Setting to application/vnd.github+json is recommended.

**Path parameters:**
- org (string, Required): The organization name. The name is not case sensitive.

**Query parameters:**
- type (string): Specifies the types of repositories you want returned. Default: all. Can be one of: all, public, private, forks, sources, member
- sort (string): The property to sort the results by. Default: created. Can be one of: created, updated, pushed, full_name
- direction (string): The order to sort by. Default: asc when using full_name, otherwise desc. Can be one of: asc, desc
- per_page (integer): The number of results per page (max 100). Default: 30
- page (integer): The page number of the results to fetch. Default: 1

### Response: 200 OK

## Create an organization repository

`POST /orgs/{org}/repos`

Creates a new repository in the specified organization. The authenticated user must be a member of the organization.

### Parameters

**Path parameters:**
- org (string, Required): The organization name.

**Body parameters:**
- name (string, Required): The name of the repository.
- description (string): A short description of the repository.
- homepage (string): A URL with more information about the repository.
- private (boolean): Whether the repository is private. Default: false
- visibility (string): The visibility of the repository. Can be one of: public, private
- has_issues (boolean): Either true to enable issues for this repository or false to disable them. Default: true
- has_projects (boolean): Either true to enable projects for this repository or false to disable them. Default: true
- has_wiki (boolean): Either true to enable the wiki for this repository or false to disable it. Default: true
- has_downloads (boolean): Whether downloads are enabled. Default: true
- is_template (boolean): Either true to make this repo available as a template repository or false to prevent it. Default: false
- team_id (integer): The id of the team that will be granted access to this repository.
- auto_init (boolean): Pass true to create an initial commit with empty README. Default: false
- gitignore_template (string): Desired language or platform .gitignore template to apply.
- license_template (string): Choose an open source license template that best suits your needs.
- allow_squash_merge (boolean): Either true to allow squash-merging pull requests, or false to prevent squash-merging. Default: true
- allow_merge_commit (boolean): Either true to allow merging pull requests with a merge commit. Default: true
- allow_rebase_merge (boolean): Either true to allow rebase-merging pull requests. Default: true
- allow_auto_merge (boolean): Either true to allow auto-merge on pull requests. Default: false
- delete_branch_on_merge (boolean): Either true to allow automatically deleting head branches when pull requests are merged. Default: false
- squash_merge_commit_title (string): Can be one of: PR_TITLE, COMMIT_OR_PR_TITLE
- squash_merge_commit_message (string): Can be one of: PR_BODY, COMMIT_MESSAGES, BLANK
- merge_commit_title (string): Can be one of: PR_TITLE, MERGE_MESSAGE
- merge_commit_message (string): Can be one of: PR_BODY, PR_TITLE, BLANK
- custom_properties (object): The custom properties for the new repository.

### Response: 201 Created, 403 Forbidden, 422 Validation failed

## Get a repository

`GET /repos/{owner}/{repo}`

Get detailed information about a repository.

### Parameters

- owner (string, Required): The account owner of the repository.
- repo (string, Required): The name of the repository.

### Response: 200 OK, 301 Moved permanently, 403 Forbidden, 404 Not found

## Update a repository

`PATCH /repos/{owner}/{repo}`

Updates the specified repository.

### Parameters

- owner (string, Required): The account owner of the repository.
- repo (string, Required): The name of the repository.
- name (string): The name of the repository.
- description (string): A short description of the repository.
- homepage (string): A URL with more information about the repository.
- private (boolean): Whether the repository is private or public.
- visibility (string): The visibility of the repository.
- security_and_analysis (object or null): Specify which security and analysis features to enable or disable for the repository.
- has_issues (boolean): Either true to enable issues or false to disable them. Default: true
- has_projects (boolean): Either true to enable projects or false to disable them. Default: true
- has_wiki (boolean): Either true to enable the wiki or false to disable it. Default: true
- is_template (boolean): Either true to make this repo available as a template. Default: false
- default_branch (string): Updates the default branch for this repository.
- allow_squash_merge (boolean): Either true to allow squash-merging pull requests. Default: true
- allow_merge_commit (boolean): Either true to allow merging pull requests with a merge commit. Default: true
- allow_rebase_merge (boolean): Either true to allow rebase-merging pull requests. Default: true
- allow_auto_merge (boolean): Either true to allow auto-merge on pull requests. Default: false
- delete_branch_on_merge (boolean): Either true to allow automatically deleting head branches. Default: false
- allow_update_branch (boolean): Either true to always allow a pull request head branch that is behind its base branch to be updated. Default: false
- squash_merge_commit_title (string): Default: PR_TITLE
- squash_merge_commit_message (string): Default: COMMIT_MESSAGES
- merge_commit_title (string): Default: MERGE_MESSAGE
- merge_commit_message (string): Default: PR_TITLE
- archived (boolean): Whether to archive this repository. Default: false
- allow_forking (boolean): Either true to allow private forks. Default: false
- web_commit_signoff_required (boolean): Either true to require contributors to sign off on web-based commits. Default: false

### Response: 200 OK, 307 Temporary redirect, 403 Forbidden, 404 Not found, 422 Validation failed

## Delete a repository

`DELETE /repos/{owner}/{repo}`

Deleting a repository requires admin access.

### Parameters

- owner (string, Required): The account owner of the repository.
- repo (string, Required): The name of the repository.

### Response: 204 No content, 307 Temporary redirect, 403 Forbidden, 404 Not found

## List repositories for the authenticated user

`GET /user/repos`

Lists repositories that the authenticated user has explicit permission to access.

### Parameters

- visibility (string): Limit results to repositories with the specified visibility. Default: all. Can be one of: all, public, private
- affiliation (string): Comma-separated list of values. Default: owner,collaborator,organization_member
- type (string): Limit results to repositories of the specified type. Default: all. Can be one of: all, owner, public, private, member
- sort (string): The property to sort the results by. Default: full_name. Can be one of: created, updated, pushed, full_name
- direction (string): The order to sort by. Can be one of: asc, desc
- per_page (integer): The number of results per page (max 100). Default: 30
- page (integer): The page number of the results to fetch. Default: 1
- since (string): Only show repositories updated after the given time (ISO 8601 format).
- before (string): Only show repositories updated before the given time (ISO 8601 format).

### Response: 200 OK, 304 Not modified, 401 Unauthorized, 403 Forbidden, 422 Validation failed
