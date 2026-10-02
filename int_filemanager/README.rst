============
File Manager
============

File manager inside Odoo: folders and files with versions, trash, rights, preview,
search, OCR and links to business records. Office documents are edited in the
browser through ONLYOFFICE.

Odoo is the only writer of file contents: files live in a content-addressed blob
store, every change creates a new revision, and access is checked by Odoo's rights
system only. This is the design on branch ``feature/int-filemanager-v2``; ``master``
still holds the earlier state, which the branch is meant to replace.

Design documents (German):

* ``docs/int_filemanager_entscheidungen.md`` - rules, decisions and rejected alternatives
* ``docs/int_filemanager_stand.md`` - status, architecture and next steps
