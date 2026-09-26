#!/bin/bash
# snap.sh PREFIX [EVLINE|-]
P=$1; L=${2:-0}
docker exec -i fmtest_pg psql -U odoo -d fmtest -At -F' ' <<SQL
select 'ROW', f.id, f.path, coalesce(left(f.share_token,6),'-') tok, f.size, coalesce(f.revision::text,'∅'), coalesce(f.share_state,'∅'), f.hash_state,
       (select count(*) from int_filemanager_version v where v.file_id=f.id) vers
from int_filemanager_file f where f.path like '$P%' order by f.path;
SQL
if [ "$L" != "-" ]; then echo "EVENTS since line $L:"; tail -n +$((L+1)) /mnt/user/appdata/fmtest/data/events.log | grep -v "^#" | \
  awk '{n=split($2,t,"|"); keep=0; for(i=1;i<=n;i++) if(t[i]!="OPEN" && t[i]!="CLOSE_NOWRITE" && t[i]!="ISDIR") keep=1; if(keep) print}' | sed -E 's/\.::TMPNAME:[^ ]*:/<TMP>:/'; fi
echo "EVLINE $(wc -l < /mnt/user/appdata/fmtest/data/events.log)"
echo "LOG:"; docker logs --since ${SINCE:-30s} fmtest_odoo 2>&1 | grep -iE "int_filemanager|error|violation|serializ" | grep -viE "onlyoffice|werkzeug" | cut -c1-220 | tail -${LOGN:-8}
