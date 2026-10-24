## General Rules

### Git Workflow

**Always integrate branches with rebase, never with merge.** Before bringing a branch into `main`, rebase it onto the latest `main` (`git rebase main`) and then fast-forward (`git merge --ff-only <branch>`), keeping history linear with no merge commits. When updating a branch with upstream changes, use `git pull --rebase` instead of a plain `git pull`.

**Every feature or refactor ends with a pushed branch and an open PR to `main`.** Develop on a dedicated branch (never directly on `main`); once the work is committed, push the branch to `origin` (`git push -u origin <branch>`) and open a pull request targeting `main` (`gh pr create --base main`). If a PR for the branch already exists, just push the new commits. Share the PR link when reporting back.
