# Terminal half of docs/screenshots/autolineage-quickstart.gif:  vhs docs/quickstart.tape
# Browser half: python docs/quickstart_browser.py  (Playwright), then concat with ffmpeg.
Output docs/screenshots/quickstart-terminal.mp4
Set Shell "bash"
Set FontSize 14
Set Width 1000
Set Height 640
Set Theme "Dracula"
Set Padding 18
Set TypingSpeed 35ms

Hide
Type "export PATH=venv/bin:$PATH PIP_DISABLE_PIP_VERSION_CHECK=1 && rm -f trace.html && clear" Enter
Sleep 500ms
Show

Type 'pip install -q "autolineage[sklearn]"' Sleep 500ms Enter
Sleep 3500ms
Type "clear" Sleep 300ms Enter
Type "cat examples/pipeline.py" Sleep 400ms Enter
Sleep 3500ms
Type "python examples/pipeline.py" Sleep 500ms Enter
Sleep 3500ms
