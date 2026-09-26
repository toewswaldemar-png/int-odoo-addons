import gevent.monkey; gevent.monkey.patch_all()
import gevent, os, time, hashlib, sys
D = sys.argv[1]
def heartbeat(stats, stop):
    last = time.monotonic()
    while not stop[0]:
        gevent.sleep(0.01)
        now = time.monotonic(); stats.append(now - last - 0.01); last = now
def writer(offload):
    p = os.path.join(D, "gevent_io_%d" % offload); buf = os.urandom(1024 * 1024); h = hashlib.sha256()
    t = time.monotonic()
    with open(p, "wb") as f:
        for _ in range(1024):
            h.update(buf); f.write(buf); gevent.sleep(0)     # kooperativ nach jedem MB
        f.flush()
        if offload:
            gevent.get_hub().threadpool.apply(os.fsync, (f.fileno(),))
        else:
            os.fsync(f.fileno())
    os.unlink(p)
    return time.monotonic() - t
for offload in (0, 1):
    stats, stop = [], [False]
    hb = gevent.spawn(heartbeat, stats, stop)
    dur = gevent.spawn(writer, offload).get()
    stop[0] = True; hb.join()
    print("%-38s Dauer %5.1fs  groesste Blockade anderer Greenlets: %6.0f ms" % (
        "fsync im Threadpool:" if offload else "fsync direkt (wie Odoo-Code es taete):", dur, max(stats) * 1000))
