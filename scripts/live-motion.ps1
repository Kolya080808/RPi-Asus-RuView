param([ValidateRange(5, 600)][int]$Seconds = 60)

# Open the live window. Recording begins only after pressing Start.
& python (Join-Path $PSScriptRoot 'live_motion.py') --seconds $Seconds
exit $LASTEXITCODE
