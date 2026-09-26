# WebDAV-Prototyp: Tests ueber den Windows-WebClient (Netzlaufwerk). Aufruf auf dem Arbeitsrechner, dessen IP in
# FM_DAV_ANON_IPS steht (anonymer Testzugang, nur Testinstanz). Ergebnisse: Konzept int_filemanager 2, Abschnitt 19.4.
param([string]$Url = "http://192.168.188.67:8082/", [string]$Src = "$env:TEMP\davsrc")
net use W: $Url /persistent:no | Out-Null
New-Item -ItemType Directory "$Src\baum\unter\tief" -Force | Out-Null
1..50 | ForEach-Object { Set-Content -Path "$Src\baum\datei_$_.txt" -Value ("Inhalt $_ " * 100) -Encoding utf8 }
1..20 | ForEach-Object { Set-Content -Path "$Src\baum\unter\klein_$_.txt" -Value "x$_" -Encoding utf8 }
Set-Content -Path "$Src\baum\unter\tief\Größe_Übersicht äöü ß.txt" -Value "Umlaute" -Encoding utf8
$r = New-Object System.Random 42
foreach ($mb in 40, 60) { $b = New-Object byte[] ($mb*1MB); $r.NextBytes($b); [IO.File]::WriteAllBytes("$Src\zufall_$mb.bin", $b) }

# 1. Ordnerbaum, Ueberschreiben, Auflisten
$t = Measure-Command { Copy-Item "$Src\baum" W:\ -Recurse -Force }; "Baum 71 Dateien: {0:N1}s" -f $t.TotalSeconds
$t = Measure-Command { Copy-Item "$Src\baum" W:\ -Recurse -Force }; "Ueberschreiben: {0:N1}s" -f $t.TotalSeconds
$t = Measure-Command { Get-ChildItem W:\ -Recurse | Out-Null }; "Auflisten: {0:N2}s" -f $t.TotalSeconds
# 2. Grosse Dateien (FileSizeLimitInBytes, Standard 50 MB)
foreach ($mb in 40, 60) {
  try { $t = Measure-Command { Copy-Item "$Src\zufall_$mb.bin" W:\ -ErrorAction Stop }; "Upload $mb MB: {0:N1}s" -f $t.TotalSeconds } catch { "Upload $mb MB: $($_.Exception.Message)" }
  try { $t = Measure-Command { Copy-Item "W:\zufall_$mb.bin" "$Src\dl_$mb.bin" -ErrorAction Stop }; "Download $mb MB: {0:N1}s" -f $t.TotalSeconds } catch { "Download $mb MB: $($_.Exception.Message)" }
}
# 3. Speichermuster Word / Excel / "loeschen, dann umbenennen" (Identitaet in Odoo pruefen: 1 Knoten, n Revisionen)
$d = "W:\office"; New-Item -ItemType Directory $d -Force | Out-Null
[IO.File]::WriteAllText("$d\Bericht.docx", "Fassung 1")
foreach ($n in 2,3) {
  [IO.File]::WriteAllText("$d\~WRD0001.tmp", "Fassung $n")
  [IO.File]::Move("$d\Bericht.docx", "$d\~WRL0002.tmp")
  [IO.File]::Move("$d\~WRD0001.tmp", "$d\Bericht.docx")
  [IO.File]::Delete("$d\~WRL0002.tmp")
}
[IO.File]::WriteAllText("$d\Tabelle.xlsx", "Excel 1")
[IO.File]::WriteAllText("$d\8A3F2B10", "Excel 2")
[IO.File]::Move("$d\Tabelle.xlsx", "$d\8A3F2B10.tmp")
[IO.File]::Move("$d\8A3F2B10", "$d\Tabelle.xlsx")
[IO.File]::Delete("$d\8A3F2B10.tmp")
[IO.File]::WriteAllText("$d\Notiz.txt", "Notiz 1")
[IO.File]::WriteAllText("$d\Notiz.txt.new", "Notiz 2")
[IO.File]::Delete("$d\Notiz.txt")
[IO.File]::Move("$d\Notiz.txt.new", "$d\Notiz.txt")
# 4. Gross/Klein
[IO.File]::WriteAllText("$d\klein.txt", "k"); [IO.File]::Move("$d\klein.txt", "$d\KLEIN.txt"); [IO.File]::WriteAllText("$d\klein.txt", "zweite")
Get-ChildItem $d | ForEach-Object { "{0} = {1}" -f $_.Name, [IO.File]::ReadAllText($_.FullName) }
net use W: /delete /y | Out-Null
