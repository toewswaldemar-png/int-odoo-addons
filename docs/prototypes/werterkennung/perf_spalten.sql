\timing on
CREATE TABLE node (id serial primary key, parent_id int, name text, path text, size bigint, mtime timestamp, create_date timestamp default now(), write_date timestamp default now(), active bool default true, is_dir bool default false, current_revision_id int, status_id int, partner_id int, create_uid int default 1, write_uid int default 1);
INSERT INTO node (parent_id,name,path,size,mtime,current_revision_id,status_id,partner_id) SELECT (g%5000)+1, 'file_'||g||'.pdf', '/a/b/'||(g%5000)||'/file_'||g||'.pdf', g*10, now(), g, g%5, g%300 FROM generate_series(1,1000000) g;
CREATE INDEX ON node(parent_id); CREATE INDEX ON node(path text_pattern_ops);
CREATE TABLE fv (id serial primary key, node_id int, field_id int, value_text text, value_date date, value_date_to date, value_number float8, currency_id int, unit text);
-- 300k documents with 8 values each = 2.4M values
INSERT INTO fv (node_id,field_id,value_text,value_date,value_number,currency_id) SELECT n, f, 'v'||n||'_'||f, DATE '2020-01-01' + (n%2000), (n%9999)/7.0, 1 FROM generate_series(1,300000) n, generate_series(1,8) f;
CREATE UNIQUE INDEX ON fv(node_id, field_id);
ANALYZE;
SELECT pg_size_pretty(pg_table_size('node')) node_size, pg_size_pretty(pg_table_size('fv')) fv_size;
-- add 10 real columns
ALTER TABLE node ADD COLUMN x_a date, ADD COLUMN x_b float8, ADD COLUMN x_c int, ADD COLUMN x_d date, ADD COLUMN x_e float8, ADD COLUMN x_f date, ADD COLUMN x_g float8, ADD COLUMN x_h date, ADD COLUMN x_i float8, ADD COLUMN x_j date;
-- rebuild one column for the whole stock
UPDATE node SET x_a = v.value_date FROM fv v WHERE v.node_id = node.id AND v.field_id = 1;
SELECT pg_size_pretty(pg_table_size('node')) node_size_after_one_column;
VACUUM node;
-- rebuild all 8 columns in one statement (fresh copy of the effect)
UPDATE node SET x_b = a.value_number, x_c = 1, x_d = c.value_date, x_e = d.value_number, x_f = e.value_date, x_g = f.value_number, x_h = g.value_date, x_i = h.value_number
 FROM fv a, fv c, fv d, fv e, fv f, fv g, fv h WHERE a.node_id=node.id AND a.field_id=2 AND c.node_id=node.id AND c.field_id=3 AND d.node_id=node.id AND d.field_id=4 AND e.node_id=node.id AND e.field_id=5 AND f.node_id=node.id AND f.field_id=6 AND g.node_id=node.id AND g.field_id=7 AND h.node_id=node.id AND h.field_id=8;
SELECT pg_size_pretty(pg_table_size('node')) node_size_after_all;
-- one document save (single-row update by id) with 10 indexed-free columns
EXPLAIN ANALYZE UPDATE node SET x_a = DATE '2025-01-01', x_b = 12.5 WHERE id = 4242;
-- list filter + group by on real columns vs on the value table
EXPLAIN ANALYZE SELECT x_a, sum(x_b) FROM node WHERE x_a IS NOT NULL GROUP BY x_a ORDER BY 1 LIMIT 5;
EXPLAIN ANALYZE SELECT d.value_date, sum(a.value_number) FROM fv d JOIN fv a ON a.node_id=d.node_id AND a.field_id=2 WHERE d.field_id=1 GROUP BY 1 ORDER BY 1 LIMIT 5;
-- drop columns
ALTER TABLE node DROP COLUMN x_a, DROP COLUMN x_b;
