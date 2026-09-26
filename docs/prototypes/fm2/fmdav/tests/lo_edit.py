# Mit LibreOffice-Python ausfuehren: Dokument oeffnen, Text anhaengen, speichern (zweimal), schliessen.
import sys
import time

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
for _ in range(60):
    try:
        ctx = resolver.resolve("uno:socket,host=localhost,port=2083;urp;StarOffice.ComponentContext")
        break
    except Exception:
        time.sleep(1)
desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
for path in sys.argv[1:]:
    url = uno.systemPathToFileUrl(path)
    doc = desktop.loadComponentFromURL(url, "_blank", 0, (prop("Hidden", True),))
    for i in (1, 2):
        text = doc.getText()
        text.insertString(text.getEnd(), " Bearbeitung %d" % i, False)
        t = time.time()
        doc.store()
        print("%s: gespeichert %d in %.2fs" % (path, i, time.time() - t))
    doc.close(True)
desktop.terminate()
