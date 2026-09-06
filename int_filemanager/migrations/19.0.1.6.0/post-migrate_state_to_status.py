def migrate(cr, version):
    """state (Selection, fest verdrahtete Werte normal/blocked/done) wurde durch
    status_id (Many2one auf das neu frei konfigurierbare int_filemanager.status)
    ersetzt - siehe filemanager_file.py. Odoos eigenes _auto_init backfillt einen
    dynamischen (Lambda-)Default fuer eine neue Many2one-Spalte nicht zuverlaessig
    auf Bestandszeilen (anders als beim statischen Default, den state selbst beim
    eigenen Baustein-4-Rollout bekam) - deshalb hier explizit per SQL gemappt,
    nicht auf automatisches Backfill verlassen.

    post-migrate (nicht pre-): laeuft erst NACH dem Laden von data/filemanager_status.xml,
    die drei Standard-Status-Records (Offen/Rueckfrage/Freigegeben) existieren an
    dieser Stelle also bereits mit fester External ID.
    """
    cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'int_filemanager_file' AND column_name = 'state'"
    )
    if not cr.fetchone():
        # Frische Installation ohne Vorgeschichte - status_id bekommt seinen
        # Default (filemanager_status_normal) ganz normal ueber den Python-Default
        # bei jeder Neuanlage, hier gibt es nichts zu migrieren.
        return

    cr.execute(
        "SELECT name, res_id FROM ir_model_data "
        "WHERE module = 'int_filemanager' AND name IN "
        "('filemanager_status_normal', 'filemanager_status_blocked', 'filemanager_status_done')"
    )
    status_ids = dict(cr.fetchall())
    mapping = {
        "normal": status_ids.get("filemanager_status_normal"),
        "blocked": status_ids.get("filemanager_status_blocked"),
        "done": status_ids.get("filemanager_status_done"),
    }
    for state_value, status_id in mapping.items():
        if not status_id:
            continue
        cr.execute(
            "UPDATE int_filemanager_file SET status_id = %s "
            "WHERE state = %s AND status_id IS NULL",
            (status_id, state_value),
        )
