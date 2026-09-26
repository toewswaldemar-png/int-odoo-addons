#!/bin/bash
# usage: fmshell.sh DB  (script on stdin)
DB=$1; B=/mnt/user/appdata/fmtest
cat > /tmp/fmshell_script.py
if [ "$DB" = fmtest ]; then docker exec fmtest_pg psql -U odoo -d fmtest -qAtc "update ir_config_parameter set value='false' where key='int_filemanager.watcher_enabled'" ; fi
docker run --rm -i --network fmtest-net -v $B/addons:/mnt/extra-addons -v $B/config:/etc/odoo -v $B/data:/var/lib/odoo \
  -v /mnt/user/test/fmroot:/mnt/hm-daten -v /mnt/user/Daten:/mnt/live-ro:ro odoo:19.0-hm \
  odoo shell -c /etc/odoo/odoo.conf -d $DB --no-http --log-level=warn < /tmp/fmshell_script.py 2>&1 | grep -vE "onlyoffice|warnings.py|showwarning|traceback.extract|sw\(msg|^\s*$|config_utils|from odoo.addons.onlyoffice"
if [ "$DB" = fmtest ]; then docker exec fmtest_pg psql -U odoo -d fmtest -qAtc "insert into ir_config_parameter(key,value,create_date,write_date) values('int_filemanager.watcher_enabled','true',now(),now()) on conflict (key) do update set value='true'"; fi
