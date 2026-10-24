## General Rules

### Git Workflow

**Always integrate branches with rebase, never with merge.** Before bringing a branch into `main`, rebase it onto the latest `main` (`git rebase main`) and then fast-forward (`git merge --ff-only <branch>`), keeping history linear with no merge commits. When updating a branch with upstream changes, use `git pull --rebase` instead of a plain `git pull`.
