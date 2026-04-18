# Contributing code changes to Wikimedia (Wikifunctions platform)

Durable reference for submitting changes to the two upstream repos
this project depends on:

- `gitlab.wikimedia.org/repos/abstract-wiki/wikifunctions/function-schemata`
- `gitlab.wikimedia.org/repos/abstract-wiki/wikifunctions/function-orchestrator`

Written after first-time submission on 2026-04-18 (see
`docs/session-notes/2026-04-18-submission.md` for the session-specific
record this distills from). Update this doc whenever the process
shifts.

## Where the code actually lives

Both repos are on **`gitlab.wikimedia.org`** under
`repos/abstract-wiki/wikifunctions/`. They used to be on Gerrit
(`gerrit.wikimedia.org/r/mediawiki/services/…`) but migrated — the
Gerrit paths are no longer submission targets for these two. Neither
repo has a `.gitreview` file; both ship `.gitlab-ci.yml` and a
GitLab-native MR flow.

The sibling `WikiLambda` MediaWiki extension **is** still on Gerrit.
Different flow (`git-review`, Change-Id footer). Out of scope here.

## Account prerequisites

One-time per contributor:

1. **Wikimedia developer LDAP account** — https://idm.wikimedia.org/signup/
   (successor to the old wikitech signup page). This is the master
   identity; Phabricator, GitLab, and a few other services all SSO
   against it.
2. **Phabricator** — log in once at https://phabricator.wikimedia.org/
   via MediaWiki SSO so your LDAP username propagates into the system.
   No additional registration.
3. **GitLab-Wikimedia** — sign up at
   https://gitlab.wikimedia.org/users/sign_up with the same username.
   Usually auto-approves within an hour.
4. **SSH key** — paste `~/.ssh/id_ed25519.pub` into
   https://gitlab.wikimedia.org/-/user_settings/ssh_keys

No CLA, no DCO. Not even a sign-off line in commits.

## One-time per machine: host keys

First contact with `gitlab.wikimedia.org` from any new machine:

```
ssh-keyscan gitlab.wikimedia.org | tee -a ~/.ssh/known_hosts
```

Without this, `git push` dies with "Host key verification failed"
because SSH can't prompt in non-interactive contexts. Cross-check the
keys against the published fingerprints at
`https://gitlab.wikimedia.org/help/instance_configuration` if the
machine is security-sensitive.

## Fork-vs-branch

First-time contributors don't get push to
`repos/abstract-wiki/wikifunctions/*`. Fork via the GitLab UI's "Fork"
button, main-only (leave "fork all branches" off — upstream feature
branches are noise you don't need).

After forking, each local clone wants its remotes swapped so `origin`
is your fork and `upstream` is the canonical repo:

```
git remote rename origin upstream
git remote add origin git@gitlab.wikimedia.org:<your-user>/<repo>.git
git fetch upstream
git rebase upstream/main     # keep history linear
```

## Commit and MR conventions

- **Commit messages**: imperative mood, short subject line. Body lines
  wrapped at ~72 chars. Multi-paragraph bodies are welcome when they
  explain *why* — the orchestrator codebase uses them liberally.
- **The one unusual convention is `Bug: T######`** on its own line
  near the end of the commit message (and in the MR description).
  CodeReviewBot auto-links the Phab task from this, and the Phab
  task grows a GitLab-MR sidebar entry. Without it, the cross-link
  doesn't materialise.
- **MR target**: `repos/abstract-wiki/wikifunctions/<repo>:main`. The
  GitLab-provided "new MR" URL from `git push` output defaults to
  `<your-fork>:main` — switch the target project in the dropdown.
- **Merge method**: squash on merge (maintainer-chosen at click time
  via the MR page dropdown). Linear history preferred upstream.
  Rebase your branch on `upstream/main` before opening and before
  every re-push.

## Phabricator

The issue tracker. All non-trivial changes start with a task.

- **Project tag**: `#Abstract_Wikipedia` is the team's triage tag —
  use this, not `#Wikifunctions` (which is for on-wiki catalogue
  issues, not backend-service code).
- **New task URL**: https://phabricator.wikimedia.org/maniphest/task/edit/form/1/
- **Remarkup syntax**: mostly Markdown-compatible. Triple-backtick
  code blocks work. The one gotcha is table cells — the `|` character
  gets interpreted, so use `<table>…</table>` for anything tabular.
- **Automated bots that matter**:
  - `CodeReviewBot` — watches for `Bug: T#####` in MRs and auto-adds
    `Patch-For-Review` to the task plus a sidebar link.
  - `Maintenance_bot` — adds triage-team tags like
    `Abstract Wikipedia team` based on project membership.
- **Cross-linking pattern**: one comment per state change. "MR is
  up: <url>". "MR is merged: <url>". Keeps the task readable and
  makes it easy for a skimming reviewer to see where things stand.

## Paired schemata / orchestrator changes

Many Wikifunctions changes span both `function-schemata` (definition
JSON) and `function-orchestrator` (the code that backs it). The
orchestrator uses `function-schemata` as a git submodule, so MRs are
sequentially coupled: the orchestrator needs the schemata SHA to be
reachable from upstream before CI can succeed.

Submission shape for this case:

1. Push both feature branches to your forks.
2. Open the **schemata MR** against upstream (non-Draft).
3. Open the **orchestrator MR as Draft**, with its submodule pointer
   set to the schemata branch HEAD on **your fork**. The MR
   description says explicitly: "CI red until !<schemata-MR> merges,
   I will re-point the submodule and mark Ready then." Reviewers can
   read both sides in parallel; CI failure on the submodule clone is
   expected.
4. When the schemata MR squash-merges, note the new SHA on upstream
   `main` (shown on the MR page).
5. In the orchestrator clone:
   ```
   cd function-schemata
   git fetch upstream
   git checkout <merged-sha>
   cd ..
   git add function-schemata
   git commit --amend     # amend the existing submodule-bump commit
   git push --force-with-lease origin <branch>
   ```
6. Click **Mark as ready** on the orchestrator MR.

Keeping the submodule bump as its own commit (rather than folded into
the feature commit) makes the amend at step 5 a one-line delta in
review.

## Subtleties to remember

- **Rebasing a submodule branch changes its SHA.** If you rebase the
  schemata feature branch, the orchestrator's submodule pointer commit
  references the old SHA and needs updating. `git submodule status`
  shows the `+` prefix when the workdir SHA differs from the index
  SHA — treat that as a signal to realign with an explicit
  `git add function-schemata && git commit`.
- **`ssh-askpass: No such file or directory` on first push** means
  SSH wanted to prompt interactively (usually for a host key) and
  there's no UI available. Fix with `ssh-keyscan` as above.
- **`npm test` in the orchestrator repo runs lint under a
  zero-warnings policy.** An otherwise green test run can be rejected
  by a single `no-shadow` complaint. Run `npm test` (not just
  `npm run test:nolint`) locally before every push.
- **The post-quantum-crypto warning on push** (`connection is not
  using a post-quantum key exchange algorithm`) is cosmetic — upstream
  will get to it. Not a failure.

## Communication channels

For nudging reviewers, asking design questions, or flagging urgency:

- **IRC `#wikipedia-abstract-tech` on Libera** — dev channel, active
  during EU/US working hours. `#wikipedia-abstract` is for general
  project talk.
- **Telegram** — group linked from
  https://meta.wikimedia.org/wiki/Abstract_Wikipedia
- **Mailing list** — `abstract-wikipedia@lists.wikimedia.org`, better
  for design discussions than quick pings.

Nudging etiquette: one sentence in IRC with the MR link after ~3–5
days of silence. Don't re-ping daily; the maintainer bandwidth is
real and they see the task in their triage queue.

## AI-assisted contributions

No formal Wikimedia-wide policy on AI-assisted contributions exists
yet. Our practice, matching the light-touch norm on the Abstract
Wikipedia side:

- Disclose early, in the task description and/or PR description.
- Self-describe (which AI, what it did, e.g. "co-developed with
  Claude").
- Don't hide it inside normal-looking prose.

Full writeup in `docs/ai-disclosure.md` (this repo).

## When this doc is wrong

Wikimedia tooling evolves. If a step here fails and you find the
new process, update this doc as part of the same session rather
than writing it into a session note — session notes are dated
artifacts, this is the persistent reference. Keep the date at the
top of this file current so readers know how stale it might be.

_Last verified: 2026-04-18 (Sage + Claude, first-contact submission
of the Z6832 find-lexemes-by-lemma primitive)._
