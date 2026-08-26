# Review automation

Pull requests in this repository use two independent quality gates:

1. `repository-validation` runs the repository policy tests.
2. Greptile reviews the change and publishes a confidence check.

Greptile is configured to review every new commit, require a confidence score
of 5/5 for its status check to pass, and auto-approve a pull request at 5/5.
When a review is below 5/5, address the findings and push another commit so the
review loop runs again.

Automatic merging is intentionally controlled by the `AUTO_MERGE_ENABLED`
repository variable. Keep it set to `false` until the default branch has rules
that require both quality gates. Once those protections are active, setting the
variable to `true` allows the guarded workflow to request a squash auto-merge
for eligible, non-draft pull requests from branches in this repository.
