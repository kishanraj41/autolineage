# Re-record the README hero GIF from the repo root:  vhs docs/hero.tape
# Needs charmbracelet/vhs, ttyd, ffmpeg, and a venv with autolineage[sklearn] installed.
Output docs/screenshots/autolineage-hero.gif
Set Shell "bash"
Set FontSize 15
Set Width 1000
Set Height 985
Set Theme "Dracula"
Set Padding 18
Set TypingSpeed 40ms

Hide
Type "source venv/bin/activate 2>/dev/null; rm -f examples/anomaly_demo_baseline.json; clear" Enter
Sleep 500ms
Show

Type "python examples/anomaly_demo.py" Sleep 700ms Enter
Sleep 5500ms
