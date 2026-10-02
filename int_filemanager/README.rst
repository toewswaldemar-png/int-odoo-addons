============
File Manager
============

File manager inside Odoo: folders and files with versions, trash, rights, preview,
search, OCR and links to business records. Office documents are edited in the
browser through ONLYOFFICE.

Version 2 (in progress on branch ``feature/int-filemanager-v2``) makes Odoo the
only writer of file contents: files live in a content-addressed blob store, every
change creates a new revision, and access is checked by Odoo's rights system only.

Design documents (German):

* ``docs/int_filemanager_v2_kern_2026-09-26.md`` - rules and architecture
* ``docs/int_filemanager_v2_entscheidungen.md`` - decisions and rejected alternatives
* ``docs/int_filemanager_v2_stand.md`` - status and next steps
