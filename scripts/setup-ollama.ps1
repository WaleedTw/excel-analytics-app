$ErrorActionPreference = "Stop"
$Model = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "llama3.2" }

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama غير مثبت. نزّله من: https://ollama.com/download/windows" -ForegroundColor Yellow
    throw "ثبّت Ollama وافتحه، ثم أعد تشغيل هذا السكربت."
}

Write-Host "تنزيل/التحقق من النموذج المحلي $Model ..." -ForegroundColor Cyan
& ollama pull $Model
if ($LASTEXITCODE -ne 0) { throw "تعذر تنزيل النموذج $Model." }

& ollama show $Model | Out-Null
if ($LASTEXITCODE -ne 0) { throw "تم التنزيل لكن تعذر فتح النموذج $Model." }

Write-Host "Ollama والنموذج $Model جاهزان. شغّل الآن scripts\run-backend.ps1" -ForegroundColor Green
