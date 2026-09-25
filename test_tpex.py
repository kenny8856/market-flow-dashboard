import urllib.request
import re

req = urllib.request.urlopen('https://www.tpex.org.tw/zh-tw/mainboard/trading/quotes/daily.html')
html = req.read().decode('utf-8')
matches = re.findall(r'"(/[a-zA-Z0-9_\-\.\/]+(?:json|php)[a-zA-Z0-9_\-\.\/\?\=]*)"', html)
print(matches)
