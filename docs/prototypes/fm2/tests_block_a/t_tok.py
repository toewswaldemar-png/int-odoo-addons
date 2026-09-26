from tlib import *
for k in ('Geheim', 'Offen'):
    rid, t = open('/var/lib/odoo/tok_%s.txt' % k).read().split()
    for label, qs in (('ohne Token', ''), ('mit Token', '?access_token=' + t), ('Token fuer falsches Feld (preview)', '?access_token=' + t)):
        fld = 'preview' if 'falsches' in label else 'thumbnail'
        st, h, b = anon('GET', '/web/image/int_filemanager.file/%s/%s%s' % (rid, fld, qs))
        out('%-7s anonym %-34s -> %s %s %d Bytes' % (k, label, st, h.get('Content-Type'), len(b)))
