param(
    [ValidateRange(5, 60)][int]$Seconds = 60,
    [ValidateRange(0, 300)][int]$Delay = 15
)

# Record on the Pi, download the session, render a PNG, and open it locally.
& python (Join-Path $PSScriptRoot 'capture_plot.py') --seconds $Seconds --delay $Delay --open
exit $LASTEXITCODE
