def migrate(cr, version):
    """share_state/revision auf der grossen Indextabelle (live ~1,39 Mio. breite Zeilen) mit
    Metadaten-Default anlegen: ab PostgreSQL 11 schreibt ADD COLUMN ... DEFAULT <konstante> die
    Zeilen nicht neu. Odoos eigener _auto_init wuerde bei einem statischen Default sonst jede
    Bestandszeile per UPDATE anfassen (siehe auch migrations/19.0.1.6.0). Sind die Spalten
    schon da, legt Odoo sie nicht erneut an und backfillt nicht.

    Frische Installation (Tabelle existiert noch nicht): nichts zu tun."""
    cr.execute("SELECT to_regclass('int_filemanager_file')")
    if not cr.fetchone()[0]:
        return
    cr.execute("ALTER TABLE int_filemanager_file ADD COLUMN IF NOT EXISTS share_state varchar DEFAULT 'synced'")
    cr.execute("ALTER TABLE int_filemanager_file ADD COLUMN IF NOT EXISTS revision integer DEFAULT 0")
