$ErrorActionPreference = 'SilentlyContinue'

Write-Host '== PlantUML local prerequisites =='

$java = Get-Command java
$dot = Get-Command dot

if ($java) {
  Write-Host ('java: OK -> ' + $java.Source)
  java -version
}
else {
  Write-Host 'java: MISSING (not found in PATH)'
}

Write-Host ''

if ($dot) {
  Write-Host ('dot: OK -> ' + $dot.Source)
  dot -V
}
else {
  Write-Host 'dot: MISSING (not found in PATH)'
}

Write-Host ''
if ($java -and $dot) {
  Write-Host 'RESULT: READY for PlantUML Local render.'
  exit 0
}

Write-Host 'RESULT: NOT READY for PlantUML Local render.'
Write-Host 'Hint: install Java + Graphviz and reopen VS Code.'
exit 1
