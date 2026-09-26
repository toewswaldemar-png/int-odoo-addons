#!/bin/bash
# runt.sh TESTFILE  -> Hilfscontainer im Testnetz, als uid 100 (wie Odoo)
B=/mnt/user/appdata/fmtest
docker run --rm -i --network fmtest-net -u 100:101 -e PYTHONPATH=/tests -v $B/tests:/tests -v $B/config:/etc/odoo -v $B/data:/var/lib/odoo \
  -v /mnt/user/test/fmroot:/mnt/hm-daten odoo:19.0-hm python3 -u /tests/$@ 2>&1 | grep -vE "DeprecationWarning|warnings.warn"
