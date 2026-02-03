# Simple AutoLineage Test Script
# Avoids complex quoting issues

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "AUTOLINEAGE - SIMPLE TEST SUITE" -ForegroundColor Cyan  
Write-Host "========================================`n" -ForegroundColor Cyan

$passed = 0
$failed = 0

function Test-Step {
    param($Name, $Command)
    
    Write-Host "`nTesting: $Name..." -ForegroundColor Yellow
    
    try {
        Invoke-Expression $Command
        if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
            Write-Host "✓ PASSED" -ForegroundColor Green
            $script:passed++
            return $true
        } else {
            Write-Host "✗ FAILED (exit code: $LASTEXITCODE)" -ForegroundColor Red
            $script:failed++
            return $false
        }
    } catch {
        Write-Host "✗ FAILED: $_" -ForegroundColor Red
        $script:failed++
        return $false
    }
}

# Clean up
Write-Host "Cleaning old files..." -ForegroundColor Cyan
Remove-Item -Force -ErrorAction SilentlyContinue *.db, *.csv, *.png, *.html, final_*, test_*, cli_*, compliance_report.*
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue test_env

# Build package
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "BUILDING PACKAGE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist, build, *.egg-info
Test-Step "Build package" "python -m build --quiet"
Test-Step "Validate package" "twine check dist/*"

# Test examples
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "TESTING EXAMPLES" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Test-Step "Quickstart" "python examples\quickstart.py"
Test-Step "Auto tracking" "python examples\auto_tracking_test.py"  
Test-Step "Auto operations" "python examples\auto_operations_test.py"
Test-Step "Graph visualization" "python examples\graph_visualization_test.py"
Test-Step "Compliance report" "python examples\compliance_report_test.py"

# Test integration
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "INTEGRATION TESTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Test-Step "Integration suite" "python tests\test_integration.py"
Test-Step "Magic module" "python tests\test_magic.py"

# Test CLI
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "CLI TESTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Remove-Item -Force -ErrorAction SilentlyContinue lineage.db

Test-Step "lineage track" "lineage track examples\test_pipeline.py"
Test-Step "lineage summary" "lineage summary"
Test-Step "lineage show PNG" "lineage show --output cli_graph.png"
Test-Step "lineage show HTML" "lineage show --format html --output cli_graph.html"
Test-Step "lineage report MD" "lineage report --format markdown --output cli_report.md"
Test-Step "lineage report JSON" "lineage report --format json --output cli_report.json"

# Final demo
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "FINAL DEMO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Test-Step "Final demo" "python examples\final_demo.py"

# Check files
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "VERIFYING OUTPUT FILES" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$files = @(
    "final_graph.png",
    "final_graph.html", 
    "final_compliance_report.md",
    "final_compliance_report.json",
    "lineage.db"
)

foreach ($f in $files) {
    if (Test-Path $f) {
        Write-Host "✓ $f exists" -ForegroundColor Green
    } else {
        Write-Host "✗ $f missing" -ForegroundColor Red
        $script:failed++
    }
}

# Results
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "RESULTS" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$total = $passed + $failed
Write-Host "Total: $total tests"
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })

if ($failed -eq 0) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "🎉 ALL TESTS PASSED! 🎉" -ForegroundColor Green
    Write-Host "========================================`n" -ForegroundColor Green
    
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. View: start final_graph.html"
    Write-Host "  2. Push: git push origin main --tags"
    Write-Host "  3. PyPI: twine upload dist/*`n"
    
    # Auto-open results
    Write-Host "Opening results..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    Start-Process final_graph.html
    
    exit 0
} else {
    Write-Host "`n❌ Some tests failed. Please review above.`n" -ForegroundColor Red
    exit 1
}