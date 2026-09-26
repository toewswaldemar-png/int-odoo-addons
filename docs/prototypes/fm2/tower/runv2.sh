#!/bin/bash
B=/mnt/user/appdata/fmtest; mkdir -p /mnt/user/test/v2src; chmod 777 /mnt/user/test/v2src
docker run --rm -i --network fmtest-net -u 100:101 -v $B/tests:/tests -v $B/config_v2:/etc/odoo -v $B/data_v2:/var/lib/odoo \
  -v /mnt/user/test/v2src:/src -v /mnt/user/fmv2blobs:/blobs:ro odoo:19.0-hm python3 -u /tests/t_v2.py "$@" 2>&1 | grep -vE "DeprecationWarning|warnings.warn"
