Filemanager
===========

Folders and documents as plain Odoo records.

Optional programs on the server
-------------------------------

The module installs and runs without the programs below. Each one adds a function; without it, only
that function is missing, and the settings page of the filemanager (block "Office files") says so.

* **LibreOffice** (``soffice``) together with **nice** and **timeout** (GNU coreutils): the preview of
  Word, Excel, PowerPoint and OpenDocument files as PDF. These programs exist on Linux only, so the
  preview does not run on Windows.
* **pypdfium2** (Python package): the small picture of the first page of a PDF, in the lists and the
  kanban.

Further notes for the operator (space for uploads, uninstalling) are in ``docs/int_filemanager/betrieb.md``
of the repository.
