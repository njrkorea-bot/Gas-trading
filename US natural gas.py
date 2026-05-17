import requests

API_KEY = 'tb5PBlfspIj7G3WJMBuvFvJNo2EhRBGeB9vzU6xx'
url = f'https://api.eia.gov/v2/natural-gas/pri/fut/data/?api_key={API_KEY}&frequency=daily&data[0]=value&start=2026-04-01&end=2026-05-08'

response = requests.get(url)
data = response.json()
print(data)  # 이 결과를 여기 paste 해줘