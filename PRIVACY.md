# SpecWeft Privacy Policy

_Last updated: 19 November 2026_

SpecWeft is an Atlassian Forge app for Bitbucket. It shows which other files a pull request may also need to change,
and offers an optional merge check. This policy explains what data the app accesses and what it does with it.

## Data the app accesses

When you open a pull request that shows the SpecWeft panel, or when the merge check runs, the app reads through the
Bitbucket API, with read-only permissions (`read:repository:bitbucket`, `read:pullrequest:bitbucket`):

- repository metadata: workspace, repository name and identifier, and whether the repository is public or private
- the pull request's identifier and its diff (the list of changed files and the changed lines)

The app does **not** request or store personal information such as names, email addresses, account IDs, passwords
or payment details. It cannot write to your repositories.

## How the data is used

The app sends this pull request information over HTTPS to the SpecWeft backend server, which is hosted on Render.
Each request is authenticated with an Atlassian-signed token. The backend uses the data only to compute the
recommendations shown in the panel and the result of the merge check.

- **Public repositories:** the first time a pull request is analyzed, the backend clones the repository's public
  source code and builds an index (file names and the configuration keys, routes, table names and similar tokens they
  share). The index is stored in the backend's database so later requests are faster.
- **Private repositories:** the backend does not clone or index them automatically.

## Storage and retention

Indexes are kept in a database on the backend server for as long as the service runs. Diffs are processed to answer
a request and are not kept as a separate record. Standard server logs from the hosting provider may record request
metadata, such as time and URL path, for a limited period.

## Sharing

SpecWeft does not sell, rent or share your data with third parties, and does not use it for advertising or for
training machine-learning models. Data is processed only by Atlassian (which runs Forge) and Render (which hosts the
backend), as needed to run the service.

## Your choices

You can uninstall the app from your Bitbucket workspace at any time, and it stops accessing your data immediately.
To have a repository's index deleted, open an issue at
<https://github.com/Disha-1610/SpecWeft/issues>.

## Changes

If this policy changes, the updated version will be published at this URL with a new "Last updated" date.

## Contact

Questions about this policy: <https://github.com/Disha-1610/SpecWeft/issues>
