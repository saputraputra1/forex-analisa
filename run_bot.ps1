$logFile = "C:\Users\izmet\Downloads\forexx\bot_monitor.log"
$botScript = "C:\Users\izmet\Downloads\forexx\main.py"
$retryDelay = 10

function Write-Log {
    param([string]$msg)
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$time - $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
    Write-Host "$time - $msg"
}

Write-Log "=== XAUUSD Bot Monitor Started ==="

while ($true) {
    try {
        Write-Log "Starting bot..."
        $process = Start-Process -FilePath "python" -ArgumentList $botScript -NoNewWindow -PassThru
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        Write-Log "Bot exited with code $exitCode"
        
        if ($exitCode -eq 0) {
            Write-Log "Bot exited normally, restarting in ${retryDelay}s..."
        } else {
            Write-Log "Bot crashed! Restarting in ${retryDelay}s..."
        }
    } catch {
        Write-Log "Error launching bot: $_"
    }
    
    Start-Sleep -Seconds $retryDelay
}
