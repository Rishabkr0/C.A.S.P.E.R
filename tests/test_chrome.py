import subprocess, time, requests
proc = subprocess.Popen(['C:/Program Files/Google/Chrome/Application/chrome.exe', '--remote-debugging-port=9222', r'--user-data-dir=C:\Users\Rishab\AppData\Local\Google\Chrome\User Data', '--profile-directory=Profile 1', '--hide-crash-restore-bubble'])
end = time.time() + 10
opened=False
while time.time() < end:
  try:
    res=requests.get('http://127.0.0.1:9222/json/version', timeout=1)
    if res.status_code==200:
      opened=True
      print('PORT OPENED')
      break
  except Exception as e:
    pass
  time.sleep(2)
print('Did it open?', opened)
proc.kill()
