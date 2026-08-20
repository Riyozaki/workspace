# GitHub Actions workflow template

`document-system.github-actions.yml` is the production CI workflow for this repository.
Copy it to `.github/workflows/document-system.yml` to activate it.

The workflow is stored as a template because the Arena GitHub App connection used for this branch does not currently have GitHub's separate `workflows` permission. Keeping the template outside `.github/workflows/` allows the implementation and generated examples to be pushed without weakening or omitting the CI definition.
