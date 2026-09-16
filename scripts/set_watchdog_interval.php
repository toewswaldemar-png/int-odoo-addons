<?php
$p = '/boot/config/plugins/user.scripts/schedule.json';
$data = json_decode(file_get_contents($p), true);
$key = '/boot/config/plugins/user.scripts/scripts/int_filemanager_smb_watchdog/script';
$data[$key]['custom'] = '*/1 * * * *';
file_put_contents($p, json_encode($data, JSON_PRETTY_PRINT));
echo "OK\n";
