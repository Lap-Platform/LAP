# GitHub REST API API Documentation

Base URL: https://api.github.com

Version: 2022-11-28

## Authentication

Bearer bearer

## GET /repos/{owner}/{repo}

Get a repository

### Required Parameters

- **owner** (str):  - The account owner of the repository
- **repo** (str):  - The name of the repository

## GET /repos/{owner}/{repo}/issues

List repository issues

### Required Parameters

- **owner** (str):  - The account owner of the repository
- **repo** (str):  - The name of the repository

### Optional Parameters

- **state** (str):  - Filter by state
- **labels** (str):  - Comma-separated list of label names
- **sort** (str):  - What to sort results by
- **direction** (str):  - Sort direction
- **per_page** (int):  - Results per page (max 100)
- **page** (int):  - Page number

## POST /repos/{owner}/{repo}/issues

Create an issue

### Required Parameters

- **owner** (str):  - The account owner of the repository
- **repo** (str):  - The name of the repository
- **title** (str):  - The title of the issue

### Optional Parameters

- **body** (str):  - The contents of the issue
- **assignees** ([str]):  - Logins for users to assign to this issue
- **labels** ([str]):  - Labels to associate with this issue
- **milestone** (int):  - The number of the milestone to associate this issue with

## GET /repos/{owner}/{repo}/pulls

List pull requests

### Required Parameters

- **owner** (str):  - The account owner of the repository
- **repo** (str):  - The name of the repository

### Optional Parameters

- **state** (str):  - Filter by state
- **head** (str):  - Filter by head user or head organization and branch name (format: user:ref-name)
- **base** (str):  - Filter by base branch name
- **sort** (str):  - What to sort results by
- **direction** (str):  - Sort direction
- **per_page** (int):  - Results per page (max 100)
- **page** (int):  - Page number

## POST /repos/{owner}/{repo}/pulls

Create a pull request

### Required Parameters

- **owner** (str):  - The account owner of the repository
- **repo** (str):  - The name of the repository
- **title** (str):  - The title of the new pull request
- **head** (str):  - The name of the branch where your changes are implemented (format: username:branch)
- **base** (str):  - The name of the branch you want the changes pulled into

### Optional Parameters

- **body** (str):  - The contents of the pull request
- **draft** (bool):  - Indicates whether the pull request is a draft
- **maintainer_can_modify** (bool):  - Indicates whether maintainers can modify the pull request

## PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge

Merge a pull request

### Required Parameters

- **owner** (str):  - The account owner of the repository
- **repo** (str):  - The name of the repository
- **pull_number** (int):  - The number of the pull request

### Optional Parameters

- **commit_title** (str):  - Title for the automatic merge commit
- **commit_message** (str):  - Extra detail for the automatic merge commit
- **merge_method** (str):  - The merge method to use
- **sha** (str):  - SHA that pull request head must match to allow merge
