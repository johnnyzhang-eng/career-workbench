# Interview evidence in the expanded goal Workbench

Issue #71 connects the private interview event store from #68 to recruiting
goals. A recruiting goal's expanded view shows linked observations, their
source and transcription fidelity, the user's own answer or problem, a
separate optional hypothesis, and a concrete next practice step. No such
cards appear in the compact room view. Creating or correcting a note uses the
existing loopback host, same-origin, and CSRF controls. The server checks that
the goal exists, belongs to recruiting, and owns any corrected record. A
correction appends a version and keeps old versions in the event store.

The form asks for an existing file *inside the current private workspace* or
a plain HTTPS source URL. It does not fetch external content or read file
contents. The UI marks ability as unassessed and does not make a résumé claim,
schedule a practice task, or change an application status. The next practice
step is text for user review until a subsequent planning flow is accepted.

Verification uses fictional files and names:

- HTTP test creates a note, rejects a write without CSRF, corrects the note,
  restarts the server, checks the new version and retained old version, then
  confirms a second goal does not see it.
- Browser QA on a fictional local workspace: expanded the add form, used its
  accessible labels to enter a note, saw separate observation and hypothesis,
  corrected a question, and reloaded to see version 2. Compact view is not
  given the interview card by the renderer.
- The complete local suite, JavaScript syntax check, privacy scan, and staged
  diff review are recorded in the PR body.

Real audio/transcripts require manual checking before a user marks a source
`user_checked`; this feature does not infer interview outcome or mastery.
