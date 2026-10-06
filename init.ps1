param(
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"

Write-Output "=== 史鉴推演环境检查 ==="
if (-not (Test-Path -LiteralPath "SKILL.md") -or -not (Test-Path -LiteralPath "scripts" -PathType Container)) {
    throw "请从项目根目录运行 init.ps1。"
}
Write-Output "项目目录：$((Get-Location).Path)"

& $PythonPath -c 'import sys; print("Python:", sys.version.split()[0]); sys.exit(0 if sys.version_info >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) { throw "需要 Python 3.10 或更新版本。" }

& $PythonPath scripts/check_plain.py
if ($LASTEXITCODE -ne 0) { throw "说人话检查失败。" }
& $PythonPath scripts/find_cases.py --list | Out-Null
if ($LASTEXITCODE -ne 0) { throw "案例索引读取失败。" }
Write-Output "案例索引读取正常。"

if (Test-Path -LiteralPath ".git" -PathType Container) {
    git log --oneline -5
    if ($LASTEXITCODE -ne 0) { Write-Warning "读取 Git 历史失败。" }
} else {
    Write-Output "提示：当前是源码压缩包，没有 Git 历史。"
}

$shijiCorpus = Get-ChildItem -LiteralPath "corpus/shiji" -Filter "*.txt" -ErrorAction SilentlyContinue | Select-Object -First 1
$tongjianCorpus = Get-ChildItem -LiteralPath "corpus/tongjian" -Filter "*.txt" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($shijiCorpus -and $tongjianCorpus) {
    Write-Output "检测到原文语料；如需全量引文核验，运行：$PythonPath scripts/verify_quotes.py"
} else {
    Write-Output "未检测到完整原文语料；全量引文核验需联网运行：$PythonPath scripts/fetch_corpus.py"
}
Write-Output "=== 环境检查完成 ==="
